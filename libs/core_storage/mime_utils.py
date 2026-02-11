# libs/core_storage/mime_utils.py
import mimetypes

# 可以在这里补充一些常见但系统没默认配置好的类型
_EXTRA_TYPES = {
    ".json": "application/json",
    ".yml": "application/x-yaml",
    ".yaml": "application/x-yaml",
    ".md": "text/markdown",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".csv": "text/csv",
}

for ext, mime in _EXTRA_TYPES.items():
    mimetypes.add_type(mime, ext, strict=False)


def guess_mime_type(filename: str, default: str = "application/octet-stream") -> str:
    """
    通用 MIME 类型推断:
      1. 优先用 mimetypes.guess_type
      2. 猜不到就返回 default
    """
    mime, _ = mimetypes.guess_type(filename)
    return mime or default
