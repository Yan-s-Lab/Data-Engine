from datetime import datetime
from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel


SourceType = Literal["manual", "spider", "robot", "video"]


class CollectionRunCreate(BaseModel):
    name: str
    description: Optional[str] = None
    source_type: SourceType = "manual"


class CollectionRun(BaseModel):
    id: int
    name: str
    description: Optional[str]
    source_type: SourceType
    created_at: datetime


class RawSampleCreate(BaseModel):
    collection_run_id: int
    source_type: SourceType
    file_name: str
    file_path: str
    timestamp: datetime
    meta: Dict[str, Any] = {}
