from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func as sql_func

from app.db.base import APPLICATION_SCHEMA, Base


class HumanProfileModel(Base):
    __tablename__ = "human_profiles"
    __table_args__ = (CheckConstraint("rank_level >= 1", name="rank_level"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    rank_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )


class HumanTaskModel(Base):
    __tablename__ = "human_tasks"
    __table_args__ = (CheckConstraint("required_rank_level >= 1", name="required_rank_level"),)

    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.executions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    required_rank_level: Mapped[int] = mapped_column(Integer, nullable=False)
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now(), index=True
    )

    execution: Mapped[ExecutionModel] = relationship(back_populates="human_task")


class HumanWaitEntryModel(Base):
    __tablename__ = "human_wait_entries"
    __table_args__ = (
        CheckConstraint("rank_level >= 1", name="rank_level"),
        CheckConstraint("status IN ('waiting', 'matched', 'stopped', 'stale')", name="status"),
        CheckConstraint(
            "(status = 'waiting' AND ended_at IS NULL) OR "
            "(status != 'waiting' AND ended_at IS NOT NULL)",
            name="state",
        ),
        Index(
            "uq_human_wait_entries_active_user",
            "performer_user_id",
            unique=True,
            postgresql_where=text("status = 'waiting'"),
        ),
        Index("ix_human_wait_entries_fifo", "status", "ready_at"),
        UniqueConstraint(
            "id",
            "performer_user_id",
            name="uq_human_wait_entries_id_performer",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    performer_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rank_level: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="waiting", server_default="waiting"
    )
    ready_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HumanClaimModel(Base):
    __tablename__ = "human_claims"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'answered', 'skipped', 'expired', 'cancelled')",
            name="status",
        ),
        CheckConstraint(
            "(status = 'active' AND finished_at IS NULL) OR "
            "(status != 'active' AND finished_at IS NOT NULL)",
            name="state",
        ),
        UniqueConstraint(
            "execution_id", "performer_user_id", name="uq_human_claims_execution_performer"
        ),
        UniqueConstraint("wait_entry_id", name="uq_human_claims_wait_entry"),
        ForeignKeyConstraint(
            ["wait_entry_id", "performer_user_id"],
            [
                f"{APPLICATION_SCHEMA}.human_wait_entries.id",
                f"{APPLICATION_SCHEMA}.human_wait_entries.performer_user_id",
            ],
            name="fk_human_claims_wait_entry_performer",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_human_claims_active_execution",
            "execution_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "uq_human_claims_active_performer",
            "performer_user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.human_tasks.execution_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    wait_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    performer_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", server_default="active"
    )
    claimed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


from app.models.platform import ExecutionModel  # noqa: E402
