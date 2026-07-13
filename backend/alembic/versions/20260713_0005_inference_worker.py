"""add durable inference dispatch and event projection state

Revision ID: 20260713_0005
Revises: 20260713_0004
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.db.base import APPLICATION_SCHEMA

revision: str = "20260713_0005"
down_revision: str | None = "20260713_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "inference_runs",
        sa.Column(
            "attempt_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        schema=APPLICATION_SCHEMA,
    )
    op.add_column(
        "inference_runs",
        sa.Column("last_event_sequence", sa.Integer(), nullable=False, server_default="-1"),
        schema=APPLICATION_SCHEMA,
    )
    op.add_column(
        "inference_runs",
        sa.Column("last_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=APPLICATION_SCHEMA,
    )
    op.add_column(
        "inference_runs",
        sa.Column("last_event_type", sa.String(length=32), nullable=True),
        schema=APPLICATION_SCHEMA,
    )
    op.add_column(
        "inference_runs",
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        schema=APPLICATION_SCHEMA,
    )
    op.add_column(
        "inference_runs",
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        schema=APPLICATION_SCHEMA,
    )
    op.add_column(
        "inference_runs",
        sa.Column("finish_reason", sa.String(length=32), nullable=True),
        schema=APPLICATION_SCHEMA,
    )
    op.add_column(
        "inference_runs",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        schema=APPLICATION_SCHEMA,
    )
    op.create_index(
        "ix_inference_runs_status_lease_expires_at",
        "inference_runs",
        ["status", "lease_expires_at"],
        unique=False,
        schema=APPLICATION_SCHEMA,
    )
    op.execute(
        sa.text(
            f"""
            UPDATE {APPLICATION_SCHEMA}.messages AS messages
            SET status = 'failed', updated_at = now()
            FROM {APPLICATION_SCHEMA}.inference_runs AS runs
            WHERE messages.id = runs.output_message_id
              AND runs.status IN ('queued', 'running')
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            UPDATE {APPLICATION_SCHEMA}.inference_runs
            SET status = 'failed',
                error_code = 'runtime_reinitialized',
                finish_reason = 'error',
                finished_at = now(),
                lease_expires_at = NULL
            WHERE status IN ('queued', 'running')
            """
        )
    )
    op.create_table(
        "inference_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("publish_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"],
            [f"{APPLICATION_SCHEMA}.inference_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
        schema=APPLICATION_SCHEMA,
    )
    op.create_index(
        "ix_inference_outbox_published_at",
        "inference_outbox",
        ["published_at"],
        unique=False,
        schema=APPLICATION_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inference_outbox_published_at",
        table_name="inference_outbox",
        schema=APPLICATION_SCHEMA,
    )
    op.drop_table("inference_outbox", schema=APPLICATION_SCHEMA)
    op.drop_index(
        "ix_inference_runs_status_lease_expires_at",
        table_name="inference_runs",
        schema=APPLICATION_SCHEMA,
    )
    for column in (
        "lease_expires_at",
        "finish_reason",
        "output_tokens",
        "input_tokens",
        "last_event_type",
        "last_event_id",
        "last_event_sequence",
        "attempt_id",
    ):
        op.drop_column("inference_runs", column, schema=APPLICATION_SCHEMA)
