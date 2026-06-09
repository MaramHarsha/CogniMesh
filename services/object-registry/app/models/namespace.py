from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdTimestampMixin


class Namespace(IdTimestampMixin, Base):
    __tablename__ = "namespaces"
    __table_args__ = (UniqueConstraint("workspace_id", "api_name", name="uq_namespaces_workspace_api_name"),)

    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    api_name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    workspace = relationship("Workspace", back_populates="namespaces")
    source_systems = relationship("SourceSystem", back_populates="namespace")
    dataset_tables = relationship("DatasetTable", back_populates="namespace")
    object_types = relationship("ObjectType", back_populates="namespace")
    link_types = relationship("LinkType", back_populates="namespace")

