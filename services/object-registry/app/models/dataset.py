from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdTimestampMixin


class DatasetTable(IdTimestampMixin, Base):
    __tablename__ = "dataset_tables"
    __table_args__ = (
        UniqueConstraint("namespace_id", "physical_name", name="uq_dataset_tables_namespace_physical_name"),
    )

    namespace_id: Mapped[str] = mapped_column(ForeignKey("namespaces.id", ondelete="CASCADE"), nullable=False)
    source_system_id: Mapped[str] = mapped_column(ForeignKey("source_systems.id", ondelete="CASCADE"), nullable=False)
    api_name: Mapped[str] = mapped_column(String(120), nullable=False)
    catalog_name: Mapped[str | None] = mapped_column(String(120))
    schema_name: Mapped[str | None] = mapped_column(String(120))
    table_name: Mapped[str] = mapped_column(String(160), nullable=False)
    physical_name: Mapped[str] = mapped_column(String(320), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    primary_key_columns: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    classification_tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    allowed_purposes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    owner_group: Mapped[str | None] = mapped_column(String(160))
    steward_group: Mapped[str | None] = mapped_column(String(160))
    default_access: Mapped[str] = mapped_column(String(40), default="read_metadata", nullable=False)

    namespace = relationship("Namespace", back_populates="dataset_tables")
    source_system = relationship("SourceSystem", back_populates="dataset_tables")
    columns = relationship("DatasetColumn", back_populates="dataset_table", cascade="all, delete-orphan")
    object_types = relationship("ObjectType", back_populates="dataset_table")


class DatasetColumn(IdTimestampMixin, Base):
    __tablename__ = "dataset_columns"
    __table_args__ = (UniqueConstraint("dataset_table_id", "column_name", name="uq_dataset_columns_table_column"),)

    dataset_table_id: Mapped[str] = mapped_column(ForeignKey("dataset_tables.id", ondelete="CASCADE"), nullable=False)
    column_name: Mapped[str] = mapped_column(String(160), nullable=False)
    data_type: Mapped[str] = mapped_column(String(80), nullable=False)
    nullable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ordinal_position: Mapped[int | None]
    description: Mapped[str | None] = mapped_column(Text)
    classification_tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    dataset_table = relationship("DatasetTable", back_populates="columns")

