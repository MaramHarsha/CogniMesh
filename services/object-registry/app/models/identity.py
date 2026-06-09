from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdTimestampMixin


class Principal(IdTimestampMixin, Base):
    __tablename__ = "principals"
    __table_args__ = (UniqueConstraint("subject", name="uq_principals_subject"),)

    subject: Mapped[str] = mapped_column(String(240), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    principal_type: Mapped[str] = mapped_column(String(40), default="user", nullable=False)
    email: Mapped[str | None] = mapped_column(String(240))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    memberships = relationship("WorkspaceMembership", back_populates="principal", cascade="all, delete-orphan")
    service_accounts = relationship("ServiceAccount", back_populates="principal")


class WorkspaceMembership(IdTimestampMixin, Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "principal_id", "role", name="uq_workspace_memberships_member_role"),
    )

    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    principal_id: Mapped[str] = mapped_column(ForeignKey("principals.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(80), nullable=False)
    groups: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    workspace = relationship("Workspace")
    principal = relationship("Principal", back_populates="memberships")


class ServiceAccount(IdTimestampMixin, Base):
    __tablename__ = "service_accounts"
    __table_args__ = (UniqueConstraint("client_id", name="uq_service_accounts_client_id"),)

    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    principal_id: Mapped[str] = mapped_column(ForeignKey("principals.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    client_id: Mapped[str] = mapped_column(String(160), nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    workspace = relationship("Workspace")
    principal = relationship("Principal", back_populates="service_accounts")


class Purpose(IdTimestampMixin, Base):
    __tablename__ = "purposes"
    __table_args__ = (UniqueConstraint("workspace_id", "api_name", name="uq_purposes_workspace_api_name"),)

    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    api_name: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    allowed_roles: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    classification_tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    workspace = relationship("Workspace")


class PolicyDecisionLog(IdTimestampMixin, Base):
    __tablename__ = "policy_decision_logs"

    actor: Mapped[str] = mapped_column(String(240), nullable=False)
    principal_id: Mapped[str | None] = mapped_column(String(80))
    workspace_id: Mapped[str | None] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(120), nullable=False)
    purpose: Mapped[str] = mapped_column(String(120), nullable=False)
    result: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

