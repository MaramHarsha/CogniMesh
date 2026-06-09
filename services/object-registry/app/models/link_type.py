from __future__ import annotations

from sqlalchemy import ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdTimestampMixin


class LinkType(IdTimestampMixin, Base):
    __tablename__ = "link_types"
    __table_args__ = (UniqueConstraint("namespace_id", "api_name", name="uq_link_types_namespace_api_name"),)

    namespace_id: Mapped[str] = mapped_column(ForeignKey("namespaces.id", ondelete="CASCADE"), nullable=False)
    api_name: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_object_type_id: Mapped[str] = mapped_column(ForeignKey("object_types.id", ondelete="CASCADE"), nullable=False)
    target_object_type_id: Mapped[str] = mapped_column(ForeignKey("object_types.id", ondelete="CASCADE"), nullable=False)
    cardinality: Mapped[str] = mapped_column(String(80), nullable=False)
    join_type: Mapped[str] = mapped_column(String(80), default="foreign_key", nullable=False)
    source_property_api_name: Mapped[str | None] = mapped_column(String(120))
    target_property_api_name: Mapped[str | None] = mapped_column(String(120))
    backing_dataset_table_id: Mapped[str | None] = mapped_column(ForeignKey("dataset_tables.id", ondelete="SET NULL"))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    classification_tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    allowed_purposes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    owner_group: Mapped[str | None] = mapped_column(String(160))
    steward_group: Mapped[str | None] = mapped_column(String(160))
    default_access: Mapped[str] = mapped_column(String(40), default="read_metadata", nullable=False)

    namespace = relationship("Namespace", back_populates="link_types")
    source_object_type = relationship("ObjectType", foreign_keys=[source_object_type_id])
    target_object_type = relationship("ObjectType", foreign_keys=[target_object_type_id])
    backing_dataset_table = relationship("DatasetTable")

