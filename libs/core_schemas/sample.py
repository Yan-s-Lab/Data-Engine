# libs/core_schemas/sample.py
from datetime import datetime
from typing import Literal, Dict, Any, Optional
from pydantic import BaseModel, Field
from libs.core_schemas.collection import SourceType




# ============ meta 记录 类型定义==========
# meta：前请求的“详细说明书”。 这次 run 的“说明书 / 身份证”，但不是数据本身，是描述 如何来的、是什么场景、在流水线里的位置 的那坨上下文信息。
# 会针对性的设计延伸，例如机器人数据，例如更复杂的数据
class SampleDataInfo(BaseModel):
    modality: str
    width: Optional[int] = None
    height: Optional[int] = None
    channels: Optional[int] = None
    format: Optional[str] = None
    duration_sec: Optional[float] = None
    hash: Optional[str] = None

class SampleSemanticInfo(BaseModel):
    split_hint: Optional[str] = None
    category_hint: Optional[str] = None
    prompt: Optional[str] = None
    language: Optional[str] = None

class SamplePipelineInfo(BaseModel):
    is_filtered_in: Optional[bool] = None
    filter_scores: Dict[str, float] = {}
    label_status: Optional[str] = None

class RawSampleMeta(BaseModel):
    collection_run_id: int
    data: SampleDataInfo
    semantic: SampleSemanticInfo = SampleSemanticInfo()
    pipeline: SamplePipelineInfo = SamplePipelineInfo()
    external: Dict[str, Any] = {}
# ==========================


class RawSampleCreate(BaseModel):
    collection_run_id: int
    source_type: SourceType
    file_name: str
    file_path: str
    timestamp: datetime
    meta: Dict[str, Any] = Field(default_factory=dict) # 暂时用用
    # meta: RawSampleMeta # TODO 后面正式的要求需要更严格类型约束