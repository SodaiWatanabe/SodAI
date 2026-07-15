import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import func as sql_func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import APPLICATION_SCHEMA, Base

if TYPE_CHECKING:
    from app.models.humans import HumanTaskModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GuestSessionModel(Base):
    __tablename__ = "guest_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ActorModel(Base):
    __tablename__ = "actors"
    __table_args__ = (
        CheckConstraint(
            "(kind = 'human' AND NOT (owner_user_id IS NOT NULL AND "
            "guest_session_id IS NOT NULL)) OR "
            "(kind IN ('model', 'agent', 'tool', 'system') AND "
            "owner_user_id IS NULL AND guest_session_id IS NULL)",
            name="ownership",
        ),
        CheckConstraint(
            "kind IN ('human', 'model', 'agent', 'tool', 'system')",
            name="kind",
        ),
        Index(
            "uq_actors_owner_user_id",
            "owner_user_id",
            unique=True,
            postgresql_where=text("owner_user_id IS NOT NULL"),
        ),
        Index(
            "uq_actors_guest_session_id",
            "guest_session_id",
            unique=True,
            postgresql_where=text("guest_session_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.users.id", ondelete="SET NULL"),
    )
    guest_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.guest_sessions.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )


class SpaceModel(Base):
    __tablename__ = "spaces"
    __table_args__ = (
        CheckConstraint(
            "(kind = 'personal' AND ((owner_user_id IS NOT NULL) <> "
            "(guest_session_id IS NOT NULL))) OR "
            "(kind = 'shared' AND owner_user_id IS NULL AND guest_session_id IS NULL)",
            name="ownership",
        ),
        CheckConstraint("kind IN ('personal', 'shared')", name="kind"),
        CheckConstraint("status IN ('active', 'archived')", name="status"),
        Index(
            "uq_spaces_owner_user_id",
            "owner_user_id",
            unique=True,
            postgresql_where=text("owner_user_id IS NOT NULL"),
        ),
        Index(
            "uq_spaces_guest_session_id",
            "guest_session_id",
            unique=True,
            postgresql_where=text("guest_session_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default="personal", server_default="personal"
    )
    name: Mapped[str | None] = mapped_column(String(200))
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.users.id", ondelete="CASCADE"),
    )
    guest_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.guest_sessions.id", ondelete="CASCADE"),
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", server_default="active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=sql_func.now(),
        onupdate=utc_now,
    )

    memberships: Mapped[list["SpaceMembershipModel"]] = relationship(
        back_populates="space", cascade="all, delete-orphan", passive_deletes=True
    )
    threads: Mapped[list["ThreadModel"]] = relationship(
        back_populates="space", cascade="all, delete-orphan", passive_deletes=True
    )


class SpaceMembershipModel(Base):
    __tablename__ = "space_memberships"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'member')", name="role"),
        CheckConstraint("status IN ('active', 'removed')", name="status"),
    )

    space_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.spaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.actors.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", server_default="active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )

    space: Mapped[SpaceModel] = relationship(back_populates="memberships")


class ThreadModel(Base):
    __tablename__ = "threads"
    __table_args__ = (CheckConstraint("status IN ('active', 'archived')", name="status"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    space_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.spaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{APPLICATION_SCHEMA}.actors.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    default_answerer: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", server_default="active"
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=sql_func.now(),
        onupdate=utc_now,
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now(), index=True
    )

    space: Mapped[SpaceModel] = relationship(back_populates="threads")
    entries: Mapped[list["ThreadEntryModel"]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ThreadEntryModel.ordinal",
    )
    response_requests: Mapped[list["ResponseRequestModel"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan", passive_deletes=True
    )


class ThreadParticipantModel(Base):
    __tablename__ = "thread_participants"
    __table_args__ = (CheckConstraint("role IN ('participant', 'answerer')", name="role"),)

    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.threads.id", ondelete="CASCADE"),
        primary_key=True,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.actors.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )


class ThreadEntryModel(Base):
    __tablename__ = "thread_entries"
    __table_args__ = (
        CheckConstraint("kind IN ('message')", name="kind"),
        ForeignKeyConstraint(
            ["thread_id", "author_actor_id"],
            [
                f"{APPLICATION_SCHEMA}.thread_participants.thread_id",
                f"{APPLICATION_SCHEMA}.thread_participants.actor_id",
            ],
            name="fk_thread_entries_author_is_participant",
            ondelete="CASCADE",
        ),
        UniqueConstraint("thread_id", "ordinal", name="uq_thread_entries_thread_ordinal"),
        UniqueConstraint("thread_id", "id", name="uq_thread_entries_thread_id"),
        UniqueConstraint(
            "thread_id",
            "id",
            "author_actor_id",
            name="uq_thread_entries_thread_id_author",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{APPLICATION_SCHEMA}.actors.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default="message", server_default="message"
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )

    thread: Mapped[ThreadModel] = relationship(back_populates="entries")
    author: Mapped[ActorModel] = relationship()
    text: Mapped["EntryTextContentModel"] = relationship(
        back_populates="entry", cascade="all, delete-orphan", uselist=False
    )


class EntryTextContentModel(Base):
    __tablename__ = "entry_text_contents"
    __table_args__ = (CheckConstraint("length(btrim(content)) > 0", name="content_not_blank"),)

    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.thread_entries.id", ondelete="CASCADE"),
        primary_key=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    entry: Mapped[ThreadEntryModel] = relationship(back_populates="text")


class ResponseRequestModel(Base):
    __tablename__ = "response_requests"
    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'completed', 'failed')", name="status"),
        CheckConstraint(
            "(status = 'queued' AND finished_at IS NULL) OR "
            "(status = 'running' AND started_at IS NOT NULL AND finished_at IS NULL) OR "
            "(status IN ('completed', 'failed') AND finished_at IS NOT NULL)",
            name="state",
        ),
        ForeignKeyConstraint(
            ["thread_id", "input_entry_id", "requester_actor_id"],
            [
                f"{APPLICATION_SCHEMA}.thread_entries.thread_id",
                f"{APPLICATION_SCHEMA}.thread_entries.id",
                f"{APPLICATION_SCHEMA}.thread_entries.author_actor_id",
            ],
            name="fk_response_requests_input_entry_author",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["thread_id", "target_actor_id"],
            [
                f"{APPLICATION_SCHEMA}.thread_participants.thread_id",
                f"{APPLICATION_SCHEMA}.thread_participants.actor_id",
            ],
            name="fk_response_requests_target_is_participant",
            ondelete="CASCADE",
        ),
        Index(
            "uq_response_requests_active_thread",
            "thread_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
        UniqueConstraint("id", "thread_id", name="uq_response_requests_id_thread"),
        UniqueConstraint(
            "id",
            "thread_id",
            "target_actor_id",
            name="uq_response_requests_id_thread_target",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requester_actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{APPLICATION_SCHEMA}.actors.id"), nullable=False
    )
    target_actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{APPLICATION_SCHEMA}.actors.id"), nullable=False
    )
    input_entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requested_answerer: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="queued", server_default="queued"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    thread: Mapped[ThreadModel] = relationship(back_populates="response_requests")
    requester_actor: Mapped[ActorModel] = relationship(foreign_keys=[requester_actor_id])
    target_actor: Mapped[ActorModel] = relationship(foreign_keys=[target_actor_id])
    executions: Mapped[list["ExecutionModel"]] = relationship(
        back_populates="response_request",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ExecutionModel.attempt_no",
    )


class ExecutionModel(Base):
    __tablename__ = "executions"
    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'completed', 'failed')", name="status"),
        CheckConstraint("attempt_no >= 1", name="attempt_no"),
        CheckConstraint(
            "idempotency_key_hash IS NULL OR length(idempotency_key_hash) = 64",
            name="idempotency_key_hash",
        ),
        CheckConstraint(
            "(status = 'queued' AND started_at IS NULL AND finished_at IS NULL "
            "AND result_entry_id IS NULL AND error_code IS NULL) OR "
            "(status = 'running' AND started_at IS NOT NULL AND finished_at IS NULL "
            "AND lease_expires_at IS NOT NULL AND result_entry_id IS NULL "
            "AND error_code IS NULL) OR "
            "(status = 'completed' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
            "AND result_entry_id IS NOT NULL AND error_code IS NULL "
            "AND lease_expires_at IS NULL) OR "
            "(status = 'failed' AND finished_at IS NOT NULL AND result_entry_id IS NULL "
            "AND error_code IS NOT NULL AND lease_expires_at IS NULL)",
            name="state",
        ),
        ForeignKeyConstraint(
            ["response_request_id", "thread_id", "target_actor_id"],
            [
                f"{APPLICATION_SCHEMA}.response_requests.id",
                f"{APPLICATION_SCHEMA}.response_requests.thread_id",
                f"{APPLICATION_SCHEMA}.response_requests.target_actor_id",
            ],
            name="fk_executions_request_target",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["thread_id", "result_entry_id", "target_actor_id"],
            [
                f"{APPLICATION_SCHEMA}.thread_entries.thread_id",
                f"{APPLICATION_SCHEMA}.thread_entries.id",
                f"{APPLICATION_SCHEMA}.thread_entries.author_actor_id",
            ],
            name="fk_executions_result_entry_author",
            ondelete="CASCADE",
        ),
        UniqueConstraint("result_entry_id", name="uq_executions_result_entry_id"),
        UniqueConstraint("response_request_id", "attempt_no", name="uq_executions_request_attempt"),
        UniqueConstraint(
            "response_request_id",
            "idempotency_key_hash",
            name="uq_executions_request_idempotency",
        ),
        Index(
            "uq_executions_active_request",
            "response_request_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
        Index(
            "uq_executions_completed_request",
            "response_request_id",
            unique=True,
            postgresql_where=text("status = 'completed'"),
        ),
        Index("ix_executions_status_lease_expires_at", "status", "lease_expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    response_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    target_actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, default=uuid.uuid4, unique=True
    )
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(64))
    execution_target: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="queued", server_default="queued"
    )
    partial_output: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    result_entry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    last_event_sequence: Mapped[int] = mapped_column(
        Integer, nullable=False, default=-1, server_default="-1"
    )
    last_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    last_event_type: Mapped[str | None] = mapped_column(String(32))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    finish_reason: Mapped[str | None] = mapped_column(String(32))
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    response_request: Mapped[ResponseRequestModel] = relationship(back_populates="executions")
    model_execution: Mapped["ModelExecutionModel | None"] = relationship(
        back_populates="execution", cascade="all, delete-orphan", uselist=False
    )
    human_task: Mapped["HumanTaskModel | None"] = relationship(
        back_populates="execution", cascade="all, delete-orphan", uselist=False
    )


class ModelExecutionModel(Base):
    __tablename__ = "model_executions"

    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.executions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    requested_model: Mapped[str] = mapped_column(String(64), nullable=False)
    resolved_model: Mapped[str | None] = mapped_column(String(128))
    artifact_id: Mapped[str] = mapped_column(String(64), nullable=False)

    execution: Mapped[ExecutionModel] = relationship(back_populates="model_execution")


class ResponseContextItemModel(Base):
    __tablename__ = "response_context_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["response_request_id", "thread_id"],
            [
                f"{APPLICATION_SCHEMA}.response_requests.id",
                f"{APPLICATION_SCHEMA}.response_requests.thread_id",
            ],
            name="fk_response_context_items_request_same_thread",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["thread_id", "entry_id"],
            [
                f"{APPLICATION_SCHEMA}.thread_entries.thread_id",
                f"{APPLICATION_SCHEMA}.thread_entries.id",
            ],
            name="fk_response_context_items_entry_same_thread",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "response_request_id", "ordinal", name="uq_response_context_items_request_ordinal"
        ),
    )

    response_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    thread_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)


class OutboxEventModel(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        CheckConstraint(
            "NOT (published_at IS NOT NULL AND discarded_at IS NOT NULL)",
            name="delivery_outcome",
        ),
        UniqueConstraint("topic", "aggregate_id", name="uq_outbox_events_topic_aggregate"),
        Index(
            "ix_outbox_events_pending",
            "created_at",
            postgresql_where=text("published_at IS NULL AND discarded_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    publish_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
