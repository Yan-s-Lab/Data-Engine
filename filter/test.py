from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import requests
import torch
from PIL import Image
from transformers import AutoModel, AutoProcessor, BitsAndBytesConfig

CKPT = "google/siglip2-so400m-patch16-naflex"
DEFAULT_IMAGE = Path(__file__).with_name("image.png")
DEFAULT_LABELS = [
    "a photo of a person",
    "a close-up photo of the deltoid muscle",
    "a photo of human",
    "an image showing a human",
    "a photo of a human shoulder",
    "a green tree",
    "a photo of a car"
]


def preferred_dtype() -> torch.dtype:
    return torch.float16 if torch.cuda.is_available() else torch.float32


def resolve_quantization_mode(requested_mode: str, ckpt: str, has_cuda: bool) -> str:
    mode = requested_mode.lower()
    if mode not in {"auto", "off", "on"}:
        raise ValueError(f"Unsupported quantization mode: {requested_mode}")

    if mode == "off":
        return "off"
    if mode == "on":
        return "on"

    if not has_cuda:
        return "off"
    if "siglip2" in ckpt.lower():
        return "off"
    return "on"


def _is_http_image_source(image_source: str) -> bool:
    parsed = urlparse(image_source)
    return parsed.scheme in {"http", "https"}


def load_image_source(image_source: str) -> Image.Image:
    if _is_http_image_source(image_source):
        response = requests.get(image_source, timeout=30)
        response.raise_for_status()
        with Image.open(BytesIO(response.content)) as img:
            return img.convert("RGB")

    image_path = Path(image_source).expanduser()
    if not image_path.is_file():
        raise FileNotFoundError(f"Local image not found: {image_path}")

    with Image.open(image_path) as img:
        return img.convert("RGB")


def load_model_non_quantized(ckpt: str):
    return AutoModel.from_pretrained(
        ckpt,
        device_map="auto",
        dtype=preferred_dtype(),
        attn_implementation="sdpa",
    )


def load_model(ckpt: str, quantization_mode: str):
    if quantization_mode == "off":
        print("[info] quantization=off; loading non-quantized model")
        return load_model_non_quantized(ckpt)

    try:
        bnb_config = BitsAndBytesConfig(load_in_4bit=True)
        return AutoModel.from_pretrained(
            ckpt,
            quantization_config=bnb_config,
            device_map="auto",
            attn_implementation="sdpa",
        )
    except Exception as exc:
        print(f"[warn] 4-bit load failed, fallback to non-quantized model: {exc}")
        return load_model_non_quantized(ckpt)


def _to_model_device(inputs, model):
    target_device = next(model.parameters()).device
    moved = inputs.to(target_device)
    for key, value in moved.items():
        if torch.is_floating_point(value):
            moved[key] = value.to(dtype=preferred_dtype())
    return moved


def run_inference(image_source: str, candidate_labels: list[str], requested_quantization: str = "auto") -> None:
    effective_mode = resolve_quantization_mode(requested_quantization, CKPT, torch.cuda.is_available())
    if effective_mode != requested_quantization.lower():
        print(f"[info] quantization={requested_quantization} resolved to {effective_mode} for checkpoint {CKPT}")

    model = load_model(CKPT, effective_mode)
    processor = AutoProcessor.from_pretrained(CKPT)
    image = load_image_source(image_source)
    
    print(processor.image_processor.size)

    inputs = processor(
        text=candidate_labels,
        images=image,
        padding="max_length",
        max_length=64,
        truncation=True,
        return_tensors="pt",
    )
    inputs = _to_model_device(inputs, model)

    with torch.no_grad():
        try:
            outputs = model(**inputs)
        except RuntimeError as exc:
            if "same dtype" not in str(exc):
                raise
            print(f"[warn] quantized forward failed, retrying in non-quantized mode: {exc}")
            model = load_model_non_quantized(CKPT)
            inputs = _to_model_device(inputs, model)
            outputs = model(**inputs)

    logits_per_image = outputs.logits_per_image
    probs = torch.sigmoid(logits_per_image)

    image0_probs = probs[0]
    for label, score in zip(candidate_labels, image0_probs):
        print(f"{label:25s} -> {score.item():.4f}")
    print(f"{image0_probs[0]:.1%} that image 0 is '{candidate_labels[0]}'")


def main() -> None:
    parser = argparse.ArgumentParser(description="SigLIP2 local prompt score smoke script")
    parser.add_argument(
        "--image",
        default=str(DEFAULT_IMAGE),
        help="Image source path or HTTP/HTTPS URL.",
    )
    parser.add_argument(
        "--quantization",
        default="auto",
        choices=["auto", "off", "on"],
        help="Quantization mode: auto resolves by environment/model; off forces non-quantized; on forces 4-bit attempt.",
    )
    args = parser.parse_args()
    run_inference(args.image, DEFAULT_LABELS, requested_quantization=args.quantization)


if __name__ == "__main__":
    main()
