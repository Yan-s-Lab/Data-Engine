# libs/core_db/models/collection.py
from __future__ import annotations  # 建议加上，前向引用更稳
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING
from libs.core_db.db import Base



if TYPE_CHECKING:
    # 防止环形依赖
    from libs.core_db.models.sample import RawSample

class CollectionRun(Base):
    __tablename__ = "collection_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now
    )

    # 外键依赖
    # samples: Mapped[list["RawSample"]] = relationship(back_populates="collection") 
    samples: Mapped[list["RawSample"]] = relationship(
        "RawSample",
        back_populates="collection",
        cascade="all, delete-orphan",
    )
