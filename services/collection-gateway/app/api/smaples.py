#samples API（上传文件）
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session

from libs.core_db import models
from libs.core_schemas.collections import SourceType
from ..deps import get_db
from ..storage.local_storage import save_file

router = APIRouter(prefix="/samples", tags=["samples"])


@router.post("/")
async def upload_sample(
    collection_run_id: int = Form(...),
    source_type: SourceType = Form("manual"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # 保存文件
    stored_path = save_file(collection_run_id, file.filename, await file.read())

    sample = models.RawSample(
        collection_run_id=collection_run_id,
        source_type=source_type,
        file_name=file.filename,
        file_path=stored_path,
        timestamp=datetime.utcnow(),
        meta={},
    )
    db.add(sample)
    db.commit()
    db.refresh(sample)

    return {"id": sample.id, "file_path": stored_path}
