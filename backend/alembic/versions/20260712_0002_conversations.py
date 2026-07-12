"""会話、匿名セッション、疑似推論run

Revision ID: 20260712_0002
Revises: 20260712_0001
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260712_0002"
down_revision: str | None = "20260712_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "app"


def upgrade() -> None:
    op.create_table(
        "guest_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_guest_sessions"),
        sa.UniqueConstraint("token_hash", name="uq_guest_sessions_token_hash"),
        schema=SCHEMA,
    )
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("guest_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("default_model", sa.String(length=64), server_default="archive", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(owner_user_id IS NOT NULL) <> (guest_session_id IS NOT NULL)",
            name="ck_conversations_exactly_one_owner",
        ),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_conversations_status"),
        sa.ForeignKeyConstraint(
            ["guest_session_id"],
            [f"{SCHEMA}.guest_sessions.id"],
            name="fk_conversations_guest_session_id_guest_sessions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            [f"{SCHEMA}.users.id"],
            name="fk_conversations_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_conversations"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_conversations_owner_user_id", "conversations", ["owner_user_id"], schema=SCHEMA
    )
    op.create_index(
        "ix_conversations_guest_session_id", "conversations", ["guest_session_id"], schema=SCHEMA
    )
    op.create_index(
        "ix_conversations_last_activity_at", "conversations", ["last_activity_at"], schema=SCHEMA
    )
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("speaker", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("speaker IN ('sodai', 'partner')", name="ck_messages_speaker"),
        sa.CheckConstraint(
            "status IN ('streaming', 'completed', 'failed')", name="ck_messages_status"
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            [f"{SCHEMA}.conversations.id"],
            name="fk_messages_conversation_id_conversations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_messages"),
        sa.UniqueConstraint("conversation_id", "ordinal", name="uq_messages_conversation_ordinal"),
        schema=SCHEMA,
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"], schema=SCHEMA)
    op.create_table(
        "inference_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("input_message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("output_message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_model", sa.String(length=64), nullable=False),
        sa.Column("resolved_model", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("partial_output", sa.Text(), server_default="", nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_inference_runs_status",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            [f"{SCHEMA}.conversations.id"],
            name="fk_inference_runs_conversation_id_conversations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["input_message_id"],
            [f"{SCHEMA}.messages.id"],
            name="fk_inference_runs_input_message_id_messages",
        ),
        sa.ForeignKeyConstraint(
            ["output_message_id"],
            [f"{SCHEMA}.messages.id"],
            name="fk_inference_runs_output_message_id_messages",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_inference_runs"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_inference_runs_conversation_id", "inference_runs", ["conversation_id"], schema=SCHEMA
    )


def downgrade() -> None:
    op.drop_index("ix_inference_runs_conversation_id", table_name="inference_runs", schema=SCHEMA)
    op.drop_table("inference_runs", schema=SCHEMA)
    op.drop_index("ix_messages_conversation_id", table_name="messages", schema=SCHEMA)
    op.drop_table("messages", schema=SCHEMA)
    op.drop_index("ix_conversations_last_activity_at", table_name="conversations", schema=SCHEMA)
    op.drop_index("ix_conversations_guest_session_id", table_name="conversations", schema=SCHEMA)
    op.drop_index("ix_conversations_owner_user_id", table_name="conversations", schema=SCHEMA)
    op.drop_table("conversations", schema=SCHEMA)
    op.drop_table("guest_sessions", schema=SCHEMA)
