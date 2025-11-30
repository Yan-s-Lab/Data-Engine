# libs/ingestion/file_filters.py
from __future__ import annotations

import io
import os
import re
import zipfile
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

from PIL import Image  # 如果不想依赖 PIL，可换成 cv2.imdecode

# === 可配置常量 ===

# 允许的图片扩展名（小写）
ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg"}

# 不接受的扩展名（可执行等）
BLOCKED_EXTS = {
    ".exe",
    ".dll",
    ".bat",
    ".sh",
    ".ps1",
    ".cmd",
    ".so",
}

# 要忽略的文件名（完全匹配）
IGNORED_NAMES = {
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
}

# 要忽略的前缀
IGNORED_PREFIXES = {
    "._",          # macOS 资源分叉
}

# 要忽略的目录名（例如 __MACOSX）
IGNORED_DIR_NAMES = {
    "__MACOSX",
}

# 临时/编辑器文件后缀
IGNORED_SUFFIXES = {
    ".swp",
    ".tmp",
}

# 单文件最大大小（字节）
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100MB，可按需调整


@dataclass
class SafeFile:
    """通过预清洗的安全文件描述."""
    logical_name: str          # 逻辑文件名（不含危险路径）
    rel_path: str              # 归一化后的相对路径（用于存储分类）
    ext: str                   # 扩展名（小写）
    content: bytes             # 文件二进制
    mime_hint: str             # 简单 MIME 类型提示（例如 "image" / "unknown"）


# === 工具函数 ===

def _normalize_rel_path(path: str) -> Optional[str]:
    """
    归一化 zip 内部或上传时的相对路径，避免 Zip Slip / 路径逃逸。
    返回 None 表示不安全，应该丢弃。
    """
    # 去掉前导的 / 或 \
    path = path.lstrip("/\\")
    # 使用 normpath 规范化
    norm = os.path.normpath(path)

    # 任何包含 .. 的都拒绝（防止跳出目标目录）
    if norm.startswith("..") or "/../" in norm or "\\..\\" in norm:
        return None

    # 防止奇怪控制字符
    if re.search(r"[\x00-\x1f]", norm):
        return None

    return norm.replace("\\", "/")


def _is_ignored_name(name: str) -> bool:
    if name in IGNORED_NAMES:
        return True
    if any(name.startswith(p) for p in IGNORED_PREFIXES):
        return True
    if any(name.endswith(s) for s in IGNORED_SUFFIXES):
        return True
    return False


def _is_ignored_dir(name: str) -> bool:
    return name in IGNORED_DIR_NAMES


def _is_blocked_ext(ext: str) -> bool:
    return ext in BLOCKED_EXTS


def _is_allowed_image_ext(ext: str) -> bool:
    return ext in ALLOWED_IMAGE_EXTS


def _detect_mime_hint(ext: str) -> str:
    if ext in {".png", ".jpg", ".jpeg"}:
        return "image"
    return "unknown"


def _validate_image_bytes(content: bytes) -> bool:
    """简单尝试解码为图片，防止坏图或伪装格式."""
    try:
        with Image.open(io.BytesIO(content)) as img:
            img.verify()  # 只校验，不解压整图
        return True
    except Exception:
        return False


# === 对“单个上传文件”的清洗 ===

def sanitize_single_image_file(
    file_name: str,
    content: bytes,
    max_size_bytes: int = MAX_FILE_SIZE_BYTES,
) -> SafeFile:
    """
    用于 /samples 单文件上传的预清洗：
    - 过滤垃圾文件名
    - 检查扩展名 + 大小
    - 做一次基本图片解码校验
    """
    base_name = os.path.basename(file_name)
    if _is_ignored_name(base_name):
        raise ValueError(f"ignored file name: {base_name}")

    if len(content) == 0:
        raise ValueError("empty file")

    if len(content) > max_size_bytes:
        raise ValueError(f"file too large: {len(content)} bytes")

    _, ext = os.path.splitext(base_name)
    ext = ext.lower()

    if _is_blocked_ext(ext):
        raise ValueError(f"blocked extension: {ext}")

    if not _is_allowed_image_ext(ext):
        raise ValueError(f"extension not allowed for image upload: {ext}")

    # 内容校验（可选，但工业界通常会做）
    if not _validate_image_bytes(content):
        raise ValueError("invalid image content")

    rel_path = base_name
    mime_hint = _detect_mime_hint(ext)

    return SafeFile(
        logical_name=base_name,
        rel_path=rel_path,
        ext=ext,
        content=content,
        mime_hint=mime_hint,
    )


# === 针对 zip 批量导入的清洗 ===

def iter_safe_images_from_zip(
    zip_bytes: bytes,
    include_patterns: Optional[Iterable[str]] = None,
    max_size_bytes: int = MAX_FILE_SIZE_BYTES,
) -> List[SafeFile]:
    """
    从 zip bytes 里迭代出“通过预清洗的图片文件”：
    - 忽略目录 / OS 垃圾文件 / __MACOSX
    - 路径归一化，防 Zip Slip
    - 扩展名 + include_patterns 双重过滤
    - 大小限制 + 图片内容校验
    """
    patterns = [p.strip() for p in (include_patterns or []) if p.strip()]
    result: List[SafeFile] = []

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            # 目录直接跳过
            if name.endswith("/"):
                continue

            norm = _normalize_rel_path(name)
            if norm is None:
                continue

            # 拿到文件名和上层目录名
            base_name = os.path.basename(norm)
            dir_name = os.path.dirname(norm)

            # 忽略特定目录（__MACOSX 等）
            if dir_name and any(_is_ignored_dir(part) for part in dir_name.split("/")):
                continue

            # 忽略 OS 垃圾文件
            if _is_ignored_name(base_name):
                continue

            # 按通配符过滤（如果有的话）
            if patterns:
                from fnmatch import fnmatch
                if not any(fnmatch(base_name, pat) for pat in patterns):
                    continue

            # 检查扩展名
            _, ext = os.path.splitext(base_name)
            ext = ext.lower()

            if _is_blocked_ext(ext):
                continue

            if not _is_allowed_image_ext(ext):
                continue

            content = zf.read(name)
            if len(content) == 0 or len(content) > max_size_bytes:
                continue

            if not _validate_image_bytes(content):
                continue

            mime_hint = _detect_mime_hint(ext)

            result.append(
                SafeFile(
                    logical_name=base_name,
                    rel_path=norm,
                    ext=ext,
                    content=content,
                    mime_hint=mime_hint,
                )
            )

    return result
