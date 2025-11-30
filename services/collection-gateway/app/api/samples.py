#samples API（上传文件）
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from libs.core_db.models import RawSample
from libs.core_db.deps import get_session
from libs.core_db.models.collection import CollectionRun
from ..storage.local_storage import save_file
from libs.ingestion.file_filters import iter_safe_images_from_zip, sanitize_single_image_file


router = APIRouter(prefix="/samples", tags=["samples"])


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
            detail=f"collection_run_id={collection_run_id} does not exist. Please use collection api create id firstly",
        )


    # ① 读取上传内容（bytes）
    content = await file.read()
    filename = file.filename or "unknown"
     # 预清洗 + 安全封装
    safe = sanitize_single_image_file(filename,content)

    # ② 保存文件
    stored_path = save_file(collection_run_id, filename, content)

    # ③ 写入数据库
    sample = RawSample(
        collection_run_id=collection_run_id,
        source_type=source_type,
        file_name=file.filename,
        file_path=stored_path,
        timestamp=datetime.now(),
        meta={},
    )
    # SQLAlchemy ORM 的标准三连操作
    db.add(sample) # 把对象加入事务，即将准备“插入”
    db.commit() # 提交事务，把“更改”正式写入数据库——真正的落库操作
    db.refresh(sample) # 刷新数据库，拿到数据库生成的字段，例如id，刷新之后，后面 return 的数据才是索引更新的 id 或者 content

    return {"id": sample.id, "file_path": stored_path}


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
            detail=f"collection_run_id={collection_run_id} does not exist. Please use collection api create id firstly",
        )

    # 解析通配符列表
    raw_patterns = [p.strip() for p in include_patterns.split(";") if p.strip()]
    patterns = raw_patterns or ["*"]  # 如果为空，就不过滤

    
    data = await archive.read()
    
    safe_files = iter_safe_images_from_zip(data, patterns)
    
    created_items = []

    for sf in safe_files:
        stored_path = save_file(collection_run_id, sf.logical_name, sf.content)
        sample = RawSample(
            collection_run_id=collection_run_id,
            source_type=source_type,
            file_name=sf.logical_name,
            file_path=stored_path,
            timestamp=datetime.now(),
            meta={},
        )
        db.add(sample)
        db.flush() # 先拿 ID，不用每个都 commit，此刻任然可以 rollback 回滚，非阻塞的！不反复开启/提交事务！

        created_items.append(
            {
                "id": sample.id,
                "file_name": sf.logical_name,
                "file_path": stored_path,
            }
        )

    db.commit()

    return {
        "count": len(created_items),
        "items": created_items,
    }