# collectors/comfy-collector/backends/__init__.py
from typing import Dict, Type

from .base import GenerationBackend, GenerationRequest, GenerationMeta
from .comfyui import ComfyUIBackend
from .diffusers_local import DiffusersLocalBackend  # 如果暂时不用，可以先注释掉


BACKEND_REGISTRY: Dict[str, Type[GenerationBackend]] = {
    "comfyui": ComfyUIBackend,
    "diffusers_local": DiffusersLocalBackend,
}


def get_backend(name: str, config: Dict) -> GenerationBackend:
    try:
        backend_cls = BACKEND_REGISTRY[name]
    except KeyError as e:
        raise ValueError(f"Unknown generation backend: {name!r}") from e
    return backend_cls(name=name, config=config)
