from datetime import datetime
from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field


SourceType = Literal["manual", "spider", "robot", "video"]

class CollectionRunBase(BaseModel):
    name: str
    description: Optional[str] = None
    source_type: SourceType = "manual"
    # run 级别的自由扩展字段
    meta: Dict[str, Any] = Field(default_factory=dict)


# API 输入
class CollectionRunCreate(CollectionRunBase):
    name: str
    description: Optional[str] = None
    source_type: SourceType = "manual"
    # run 级别的自由扩展字段，尤其针对多种任务复杂任务的收集动作，例如从爬虫到 Robotic 人工演示数据
    meta: Dict[str, Any] = Field(default_factory=dict)

    pass



# API 输出
class CollectionRunOut(BaseModel):
    id: int
    # name: str
    # description: Optional[str]
    # source_type: SourceType
    created_at: datetime
    class Config:
        from_attributes = True   # SQLAlchemy → Pydantic ：直接让 FastAPI 帮忙“从 ORM 转 schema”，不用担心类型报错

