# collectors/comfy-collector/backends/diffusers_local.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import torch
from diffusers import StableDiffusionPipeline

from .base import GenerationBackend, GenerationRequest, GenerationMeta


class DiffusersLocalBackend(GenerationBackend):
    """
    使用 diffusers 在本机生成图片的 backend.

    预期 config:
      - model_id: huggingface 模型名称或本地路径
      - device: "cuda" / "cpu"
      - generator_id: str
    """

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.generator_id: str = config["generator_id"]
        model_id = config.get("model_id", "runwayml/stable-diffusion-v1-5")
        device = config.get("device", "cuda")

        self.pipe = StableDiffusionPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16 if device.startswith("cuda") else torch.float32,
        )
        self.pipe = self.pipe.to(device)
        self.device = device

    def generate_one(
        self,
        req: GenerationRequest,
        out_dir: Path,
    ) -> GenerationMeta:
        out_dir.mkdir(parents=True, exist_ok=True)

        generator = None
        if req.seed is not None:
            generator = torch.Generator(device=self.device).manual_seed(req.seed)

        width = req.width or 512
        height = req.height or 512

        image = self.pipe(
            prompt=req.prompt,
            negative_prompt=req.negative_prompt,
            width=width,
            height=height,
            generator=generator,
        ).images[0]

        filename = f"img_{req.idx:06d}.png"
        out_path = out_dir / filename
        image.save(out_path)

        backend_params: Dict[str, Any] = {
            "device": self.device,
            "model_id": self.config.get("model_id"),
        }

        return GenerationMeta(
            backend=self.name,
            generator_id=self.generator_id,
            idx=req.idx,
            filename=filename,
            prompt=req.prompt,
            negative_prompt=req.negative_prompt,
            seed=req.seed,
            width=width,
            height=height,
            backend_params=backend_params,
        )
