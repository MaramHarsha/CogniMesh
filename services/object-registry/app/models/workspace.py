from __future__ import annotations

from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdTimestampMixin


class Workspace(IdTimestampMixin, Base):
    __tablename__ = "workspaces"
    __table_args__ = (UniqueConstraint("slug", name="uq_workspaces_slug"),)

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    namespaces = relationship("Namespace", back_populates="workspace", cascade="all, delete-orphan")

