from __future__ import annotations

from pathlib import Path
from typing import Any, List

import torch
from PIL import Image
from transformers import AutoModel, AutoProcessor


def resolve_device(device_cfg: str) -> str:
    requested = str(device_cfg).strip().lower()
    if requested in {"cpu", "cuda"}:
        if requested == "cuda" and not torch.cuda.is_available():
            return "cpu"
        return requested
    return "cuda" if torch.cuda.is_available() else "cpu"


def load_siglip2_runtime(model_id: str, device_cfg: str) -> tuple[Any, Any, str]:
    device = resolve_device(device_cfg)
    model = AutoModel.from_pretrained(str(model_id).strip(), dtype=torch.float32).to(device).eval()
    processor = AutoProcessor.from_pretrained(str(model_id).strip(), use_fast=True)
    return model, processor, device


def compute_siglip2_logits_for_image(
    *,
    model: Any,
    processor: Any,
    image_path: Path,
    prompts: List[str],
    device: str,
) -> List[float]:
    image = Image.open(image_path).convert("RGB")
    inputs = processor(text=prompts, images=image, padding="max_length", return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        logits = model(**inputs).logits_per_image.float().cpu()[0]
    return [float(v.item()) for v in logits]
