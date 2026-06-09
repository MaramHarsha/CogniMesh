from __future__ import annotations

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdTimestampMixin


class Policy(IdTimestampMixin, Base):
    __tablename__ = "policies"

    resource_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(80), nullable=False)
    purpose: Mapped[str | None] = mapped_column(String(120))
    effect: Mapped[str] = mapped_column(String(40), default="allow", nullable=False)
    rule: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

