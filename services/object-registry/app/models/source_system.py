from __future__ import annotations

from sqlalchemy import ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdTimestampMixin


class SourceSystem(IdTimestampMixin, Base):
    __tablename__ = "source_systems"
    __table_args__ = (UniqueConstraint("namespace_id", "api_name", name="uq_source_systems_namespace_api_name"),)

    namespace_id: Mapped[str] = mapped_column(ForeignKey("namespaces.id", ondelete="CASCADE"), nullable=False)
    api_name: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    connection_uri: Mapped[str | None] = mapped_column(String(512))
    connection_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    classification_tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    allowed_purposes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    owner_group: Mapped[str | None] = mapped_column(String(160))
    steward_group: Mapped[str | None] = mapped_column(String(160))
    default_access: Mapped[str] = mapped_column(String(40), default="read_metadata", nullable=False)

    namespace = relationship("Namespace", back_populates="source_systems")
    dataset_tables = relationship("DatasetTable", back_populates="source_system")

