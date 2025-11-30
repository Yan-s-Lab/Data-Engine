# collectors/common/client.py
import json
from pathlib import Path
from typing import Any, Dict, Optional
import os
import requests

GATEWAY_URL = os.getenv("COLLECTION_GATEWAY_URL", "http://localhost:8001")


def create_collection_run(
    name: str,
    source_type: str = "manual",
    description: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    调用 collection-gateway 的创建 collection_run 接口。

    对应后端 Pydantic:

        class CollectionRunCreate(BaseModel):
            name: str
            description: Optional[str] = None
            source_type: SourceType = "manual"
            meta: Dict[str, Any] = {}

    返回整个 JSON（包含 id），上层可以拿 data["id"] 用。
    """
    payload: Dict[str, Any] = {
        "name": name,
        "description": description,
        "source_type": source_type,
        "meta": meta or {},
    }

    resp = requests.post(f"{GATEWAY_URL}/collections/", json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data  # 或者直接 return data，看你习惯



def upload_archive_to_collection(
    collection_run_id: int,
    archive_path: Path,
    source_type: str = "spider",
    extra_meta: Optional[Dict[str, Any]] = None,
):
    """
    调用 /samples/from_archive 上传一个 zip 压缩包。

    假设 FastAPI 接口是（大致）：

        @router.post("/samples/from_archive")
        async def upload_from_archive(
            collection_run_id: int = Form(...),
            source_type: SourceType = Form(...),
            meta: Optional[str] = Form(None),
            archive: UploadFile = File(...),
        )
    """
    archive_path = Path(archive_path)
    files = {
        "archive": (archive_path.name, archive_path.read_bytes(), "application/zip"),
    }
    data = {
        "collection_run_id": str(collection_run_id),
        "source_type": source_type,
        "meta": json.dumps(extra_meta or {}),
    }
    resp = requests.post(
        f"{GATEWAY_URL}/samples/from_archive",
        data=data,
        files=files,
        timeout=60*10,
    )
    resp.raise_for_status()
    return resp.json()