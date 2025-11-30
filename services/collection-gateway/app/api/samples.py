#samples API（上传文件）
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from libs.core_db.models import RawSample
from libs.core_db.deps import get_session
from ..storage.local_storage import save_file

router = APIRouter(prefix="/samples", tags=["samples"])


@router.post("/")
async def upload_sample(
    collection_run_id: int = Form(...),
    source_type: str = Form("manual"),
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
):
    # ① 读取上传内容（bytes）
    content = await file.read()
    filename = file.filename or "unknown"
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
    db.add(sample)
    db.commit()
    db.refresh(sample)

    return {"id": sample.id, "file_path": stored_path}
