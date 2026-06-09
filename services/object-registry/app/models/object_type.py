from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdTimestampMixin, utc_now


class ObjectType(IdTimestampMixin, Base):
    __tablename__ = "object_types"
    __table_args__ = (UniqueConstraint("namespace_id", "api_name", name="uq_object_types_namespace_api_name"),)

    namespace_id: Mapped[str] = mapped_column(ForeignKey("namespaces.id", ondelete="CASCADE"), nullable=False)
    dataset_table_id: Mapped[str | None] = mapped_column(ForeignKey("dataset_tables.id", ondelete="SET NULL"))
    api_name: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    primary_key_property: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    classification_tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    allowed_purposes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    owner_group: Mapped[str | None] = mapped_column(String(160))
    steward_group: Mapped[str | None] = mapped_column(String(160))
    default_access: Mapped[str] = mapped_column(String(40), default="read_metadata", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    namespace = relationship("Namespace", back_populates="object_types")
    dataset_table = relationship("DatasetTable", back_populates="object_types")
    properties = relationship("ObjectProperty", back_populates="object_type", cascade="all, delete-orphan")

