from pathlib import Path
from typing import Dict, Any
import torch
from diffusers import StableDiffusionXLPipeline
from .base import GenerationBackend

class DiffusersBackend(GenerationBackend):
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        model_id = config["model_id"]
        device = config.get("device", "cuda:0")

        self.pipe = StableDiffusionXLPipeline.from_pretrained(
            model_id, torch_dtype=torch.float16
        ).to(device)
        self.device = device

    def _build_prompt(self, idx: int) -> str:
        tpl = self.config.get("prompt_template", "image {idx}")
        seed_base = int(self.config.get("seed_start", 1))
        return tpl.format(idx=idx, seed=seed_base + idx)

    def generate_one(self, idx: int, out_dir: Path) -> Dict[str, Any]:
        out_dir.mkdir(parents=True, exist_ok=True)
        prompt = self._build_prompt(idx)
        seed = int(self.config.get("seed_start", 1)) + idx

        generator = torch.Generator(device=self.device).manual_seed(seed)
        image = self.pipe(prompt, generator=generator).images[0]

        filename = f"{self.name}_{idx:04d}.png"
        out_path = out_dir / filename
        image.save(out_path)

        return {
            "backend": self.name,
            "type": "diffusers",
            "filename": filename,
            "prompt": prompt,
            "seed": seed,
            "idx": idx,
            "config_snapshot": self.config,
        }
