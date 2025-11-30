from datetime import datetime
from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel


SourceType = Literal["manual", "spider", "robot", "video"]


# API 输入
class CollectionRunCreate(BaseModel):
    name: str
    description: Optional[str] = None
    source_type: SourceType = "manual"


# API 输出
class CollectionRunOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    source_type: SourceType
    created_at: datetime
    class Config:
        from_attributes = True   # SQLAlchemy → Pydantic ：直接让 FastAPI 帮忙“从 ORM 转 schema”，不用担心类型报错
