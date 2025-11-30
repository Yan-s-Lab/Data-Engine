from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List

class GenerationBackend(ABC):
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config

    @abstractmethod
    def generate_one(self, idx: int, out_dir: Path) -> Dict[str, Any]:
        """
        生成一张图片，保存到 out_dir。
        返回 meta，比如: {
          "backend": self.name,
          "filename": "xxx.png",
          "prompt": "...",
          "seed": 123,
          ...
        }
        """
        raise NotImplementedError
