from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from typing_extensions import Literal


SourceType = Literal["manual", "spider", "robot", "video"]



# ============ meta 记录 类型定义==========
# meta：前请求的“详细说明书”。 这次 run 的“说明书 / 身份证”，但不是数据本身，是描述 如何来的、是什么场景、在流水线里的位置 的那坨上下文信息。
# 会针对性的设计延伸，例如机器人数据收集任务，例如更复杂的数据收集任务
class MethodInfo(BaseModel):
    family: Literal["collector", "filter", "synthetic", "importer"]
    name: str
    origin: str              # 可以先用 str，后面再收紧
    interaction_mode: Optional[Literal["manual", "automatic", "semi_auto"]] = None
    tool: Optional[str] = None
    operator: Optional[str] = None
    notes: Optional[str] = None

class DataInfo(BaseModel):
    modalities: List[str]
    domain: Optional[str] = None
    approx_samples: Optional[int] = None
    license: Optional[str] = None
    sensitive_level: Optional[str] = None

class PipelineInfo(BaseModel):
    tags: List[str] = []
    version: Optional[str] = None
    upstream_run_ids: List[int] = []
    collection_label: Optional[str] = None

class CollectionMeta(BaseModel):
    method: MethodInfo
    data: DataInfo
    pipeline: PipelineInfo = PipelineInfo()
    external: Dict[str, Any] = {}

# ==========================



# ==========================
# 业务接口中直接引用的类型
class CollectionRunBase(BaseModel):
    name: str
    description: Optional[str] = None
    source_type: SourceType = "manual"
    # run 级别的自由扩展字段
    meta: Dict[str, Any] = Field(default_factory=dict) # 暂时用用
    # meta: CollectionMeta # TODO 后面正式的要求需要更严格类型约束


# API 输入
class CollectionRunCreate(CollectionRunBase):
    pass


# API 输出
class CollectionRunOut(BaseModel):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True   # SQLAlchemy → Pydantic ：直接让 FastAPI 帮忙“从 ORM 转 schema”，不用担心类型报错
# ==========================