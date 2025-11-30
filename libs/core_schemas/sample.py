from datetime import datetime
from typing import Literal, Dict, Any
from pydantic import BaseModel
from libs.core_schemas.collection import SourceType


class RawSampleCreate(BaseModel):
    collection_run_id: int
    source_type: SourceType
    file_name: str
    file_path: str
    timestamp: datetime
    meta: Dict[str, Any] = {}
