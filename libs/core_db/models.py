from datetime import datetime
from sqlalchemy import Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .session import Base


class CollectionRun(Base):
    __tablename__ = "collection_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    samples: Mapped[list["RawSample"]] = relationship(back_populates="collection")


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

    collection: Mapped[CollectionRun] = relationship(back_populates="samples")
