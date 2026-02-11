# libs/core_storage/minio_client.py
import os
from functools import lru_cache
from io import BytesIO
from minio import Minio
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


@lru_cache(maxsize=1)
def get_minio_client() -> Minio:
    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    access_key = os.getenv("MINIO_ACCESS_KEY", "admin")
    secret_key = os.getenv("MINIO_SECRET_KEY", "admin123456")
    secure = os.getenv("MINIO_SECURE", "false").lower() == "true"

    return Minio(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure,
    )


def ensure_bucket(bucket_name: str) -> None:
    client = get_minio_client()
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)


def upload_bytes(
    bucket: str,
    object_name: str,
    data: bytes,
    content_type: str | None = None,
) -> str:
    """
    上传内存中的 bytes 到 MinIO，返回 s3://bucket/object_name URI
    """
    client = get_minio_client()
    ensure_bucket(bucket)

    length = len(data)
    extra = {}
    if content_type:
        extra["content_type"] = content_type

    client.put_object(
        bucket_name=bucket,
        object_name=object_name,
        data=BytesIO(data),
        length=length,
        **extra,
    )
    return f"s3://{bucket}/{object_name}"
