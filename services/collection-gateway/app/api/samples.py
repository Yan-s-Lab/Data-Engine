# samples API（上传文件）
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from libs.core_db.models import RawSample
from libs.core_db.deps import get_session
from libs.core_db.models.collection import CollectionRun
from libs.ingestion.file_filters import (
    iter_safe_images_from_zip,
    sanitize_single_image_file,
)
from libs.core_storage.minio_client import upload_bytes
from libs.core_storage.mime_utils import guess_mime_type


router = APIRouter(prefix="/samples", tags=["samples"])


# 统一一个 RAW bucket 名称（可通过环境变量覆盖）
MINIO_BUCKET_RAW = os.getenv("MINIO_BUCKET_RAW", "raw")

@router.post("/")
async def upload_sample(
    collection_run_id: int = Form(...),
    source_type: str = Form("manual"),
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
):
    # 先验证 collection_run 是否存在（防止外键错误）
    run = db.get(CollectionRun, collection_run_id)
    if run is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"collection_run_id={collection_run_id} does not exist. "
                "Please use collection api create id firstly"
            ),
        )

    # ① 读取上传内容（bytes）
    raw_bytes = await file.read()
    orig_filename = file.filename or "unknown"

    # ② 预清洗 + 安全封装（得到安全文件名 & 内容）
    safe = sanitize_single_image_file(orig_filename, raw_bytes)
    filename = safe.logical_name
    content = safe.content

    # ③ 上传到 MinIO
    object_name = f"collection_{collection_run_id}/{filename}"
    content_type = guess_mime_type(filename)

    s3_uri = upload_bytes(
        bucket=MINIO_BUCKET_RAW,
        object_name=object_name,
        data=content,
        content_type=content_type,
    )

    # ④ 写入数据库（file_path 现在是 s3://...）
    sample = RawSample(
        collection_run_id=collection_run_id,
        source_type=source_type,
        file_name=filename,
        file_path=s3_uri,
        timestamp=datetime.now(),
        meta={},
    )
    db.add(sample)
    db.commit()
    db.refresh(sample)

    return {"id": sample.id, "file_path": s3_uri}


# 支持上传压缩文件夹，批量上传
@router.post("/from_archive")
async def upload_samples_from_archive(
    collection_run_id: int = Form(...),
    source_type: str = Form("manual"),
    # 支持通配：例如 "*.png;*.jpg" 或 "*.png"，！！！推荐保持数据格式一致性！！！
    meta: Optional[str] = Form(None),
    include_patterns: str = Form("*.png;*.jpg"),
    archive: UploadFile = File(...),
    db: Session = Depends(get_session),
):
    # 先验证 collection_run 是否存在（防止外键错误）
    run = db.get(CollectionRun, collection_run_id)
    if run is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"collection_run_id={collection_run_id} does not exist. "
                "Please use collection api create id firstly"
            ),
        )

    # 解析通配符列表
    raw_patterns = [p.strip() for p in include_patterns.split(";") if p.strip()]
    patterns = raw_patterns or ["*"]  # 如果为空，就不过滤

    # ① 读取 zip 原始数据
    data = await archive.read()

    # ② 预清洗 + 筛选出安全图片
    safe_files = iter_safe_images_from_zip(data, patterns)

    created_items = []

    for sf in safe_files:
        filename = sf.logical_name
        content = sf.content

        object_name = f"collection_{collection_run_id}/{filename}"
        content_type = guess_mime_type(filename)

        # 上传到 MinIO
        s3_uri = upload_bytes(
            bucket=MINIO_BUCKET_RAW,
            object_name=object_name,
            data=content,
            content_type=content_type,
        )

        # ③ 写入数据库
        sample = RawSample(
            collection_run_id=collection_run_id,
            source_type=source_type,
            file_name=filename,
            file_path=s3_uri,
            timestamp=datetime.now(),
            meta={},
        )
        db.add(sample)
        db.flush()  # 拿 ID，不用每个都 commit

        created_items.append(
            {
                "id": sample.id,
                "file_name": filename,
                "file_path": s3_uri,
            }
        )

    db.commit()

    return {
        "count": len(created_items),
        "items": created_items,
    }
