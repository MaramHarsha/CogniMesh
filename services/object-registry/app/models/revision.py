from __future__ import annotations

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdTimestampMixin


class Revision(IdTimestampMixin, Base):
    __tablename__ = "object_type_revisions"

    asset_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    asset_id: Mapped[str] = mapped_column(String(80), nullable=False)
    revision_number: Mapped[int] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    actor: Mapped[str] = mapped_column(String(160), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

