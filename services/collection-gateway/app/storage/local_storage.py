# 简单本地存储实现
import os
from pathlib import Path
from typing import BinaryIO

STORAGE_ROOT = Path(os.getenv("STORAGE_ROOT", "/data/raw"))


def save_file(collection_id: int, filename: str, file: BinaryIO) -> str:
    """
    保存文件到本地目录，返回相对路径字符串
    """
    target_dir = STORAGE_ROOT / f"collection_{collection_id}"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename

    with open(target_path, "wb") as f:
        f.write(file.read())

    return str(target_path)
