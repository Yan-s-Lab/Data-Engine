from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import requests

GATEWAY_URL = os.getenv("COLLECTION_GATEWAY_URL", "http://localhost:8001")


def create_collection_run(
    name: str,
    source_type: str = "manual",
    description: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "name": name,
        "description": description,
        "source_type": source_type,
        "meta": meta or {},
    }
    resp = requests.post(f"{GATEWAY_URL}/collections/", json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def upload_archive_to_collection(
    collection_run_id: int,
    archive_path: Path,
    source_type: str = "manual",
    extra_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
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
        timeout=60 * 10,
    )
    resp.raise_for_status()
    return resp.json()
