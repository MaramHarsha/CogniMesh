from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdTimestampMixin


class ObjectProperty(IdTimestampMixin, Base):
    __tablename__ = "object_properties"
    __table_args__ = (UniqueConstraint("object_type_id", "api_name", name="uq_object_properties_object_api_name"),)

    object_type_id: Mapped[str] = mapped_column(ForeignKey("object_types.id", ondelete="CASCADE"), nullable=False)
    api_name: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    data_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_column_name: Mapped[str | None] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_primary_key: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    classification_tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    allowed_purposes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    owner_group: Mapped[str | None] = mapped_column(String(160))
    steward_group: Mapped[str | None] = mapped_column(String(160))
    default_access: Mapped[str] = mapped_column(String(40), default="read_metadata", nullable=False)

    object_type = relationship("ObjectType", back_populates="properties")

