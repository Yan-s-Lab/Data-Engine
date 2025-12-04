import os
from functools import lru_cache
from minio import Minio
from minio.error import S3Error


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
    found = client.bucket_exists(bucket_name)
    if not found:
        client.make_bucket(bucket_name)


def upload_file(
    bucket: str,
    object_name: str,
    file_path: str,
    content_type: str | None = None,
) -> str:
    """
    上传本地文件到 MinIO，返回 s3://bucket/object_name URI
    """
    client = get_minio_client()
    ensure_bucket(bucket)

    extra = {}
    if content_type:
        extra["content_type"] = content_type

    client.fput_object(
        bucket_name=bucket,
        object_name=object_name,
        file_path=file_path,
        **extra,
    )
    return f"s3://{bucket}/{object_name}"


def presigned_get_url(bucket: str, object_name: str, expires_seconds: int = 3600) -> str:
    client = get_minio_client()
    return client.presigned_get_object(bucket, object_name, expires=expires_seconds)
