# libs/core_db/models/sample.py
from __future__ import annotations  # 建议加上，前向引用更稳
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from libs.core_db.db import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # 防止环形依赖
    from libs.core_db.models.collection import CollectionRun
    
class RawSample(Base):
    __tablename__ = "raw_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    collection_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("collection_runs.id", ondelete="CASCADE")
    )
    source_type: Mapped[str] = mapped_column(String(32))
    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(1024))
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # 外键依赖
    collection: Mapped[CollectionRun] = relationship("CollectionRun",back_populates="samples")
