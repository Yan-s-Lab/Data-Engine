# collectors/comfy-collector/backends/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class GenerationRequest:
    """
    一次生成任务的逻辑参数（和具体 backend 解耦，只描述“我要什么图”）.
    """
    idx: int
    prompt: str
    negative_prompt: Optional[str] = None
    seed: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    extra: Optional[Dict[str, Any]] = None # backend 专用参数，随用随加


@dataclass
class GenerationMeta:
    """
    写入 raw_samples.meta 的统一结构（Data Engine 只依赖这一层）.
    """
    backend: str           # comfyui / diffusers_local / 其他
    generator_id: str      # generators.yml 里的 id
    idx: int               # 当前图片是第几张
    filename: str          # 文件名，相对于 out_dir
    prompt: str
    negative_prompt: Optional[str]
    seed: Optional[int]
    width: Optional[int]
    height: Optional[int]
    backend_params: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GenerationBackend(ABC):
    """
    所有生成后端的抽象基类.
    """

    def __init__(self, name: str, config: Dict[str, Any]):
        """
        :param name: backend 名称（例如 'comfyui'）
        :param config: 来自 generators.yml 的配置（后端自己解释）
        """
        self.name = name
        self.config = config

    @abstractmethod
    def generate_one(
        self,
        req: GenerationRequest,
        out_dir: Path,
    ) -> GenerationMeta:
        """
        根据请求生成一张图片，保存到 out_dir，并返回标准化的 meta.
        """
        raise NotImplementedError
