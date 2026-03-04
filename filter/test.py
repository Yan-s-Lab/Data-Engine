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
DEFAULT_IMAGE = Path(__file__).with_name("yk003__body_pose__prompt__1_00001_.png")
DEFAULT_LABELS = [
    "this is a photo of a human",
    "a person in the image",
    "human body",
]


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


def load_model(ckpt: str):
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
        return AutoModel.from_pretrained(
            ckpt,
            device_map="auto",
            dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            attn_implementation="sdpa",
        )


def run_inference(image_source: str, candidate_labels: list[str]) -> None:
    model = load_model(CKPT)
    processor = AutoProcessor.from_pretrained(CKPT)
    image = load_image_source(image_source)

    inputs = processor(
        text=candidate_labels,
        images=image,
        padding="max_length",
        max_length=64,
        return_tensors="pt",
    ).to(model.device)

    with torch.no_grad():
        try:
            outputs = model(**inputs)
        except RuntimeError as exc:
            if "same dtype" not in str(exc):
                raise
            print(f"[warn] quantized forward failed, retrying in non-quantized mode: {exc}")
            model = AutoModel.from_pretrained(
                CKPT,
                device_map="auto",
                dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                attn_implementation="sdpa",
            )
            inputs = inputs.to(model.device)
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
    args = parser.parse_args()

    run_inference(args.image, DEFAULT_LABELS)


if __name__ == "__main__":
    main()
