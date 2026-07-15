"""add Human answerers and realtime matching tables

Revision ID: 20260715_0005
Revises: 20260714_0004
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260715_0005"
down_revision: str | None = "20260714_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "executions",
        "deadline_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        schema="app",
    )
    op.execute(
        sa.text(
            """
            INSERT INTO app.actors (id, kind, key, name)
            VALUES
                ('00000000-0000-4000-8000-000000000003', 'model',
                 'model:human-lite', 'Human Lite'),
                ('00000000-0000-4000-8000-000000000004', 'model',
                 'model:human-pro', 'Human Pro')
            """
        )
    )

    op.create_table(
        "human_profiles",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("rank_level", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("rank_level >= 1", name=op.f("ck_human_profiles_rank_level")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app.users.id"],
            name=op.f("fk_human_profiles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_human_profiles")),
        schema="app",
    )

    op.create_table(
        "human_tasks",
        sa.Column("execution_id", sa.UUID(), nullable=False),
        sa.Column("required_rank_level", sa.Integer(), nullable=False),
        sa.Column(
            "queued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "required_rank_level >= 1", name=op.f("ck_human_tasks_required_rank_level")
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["app.executions.id"],
            name=op.f("fk_human_tasks_execution_id_executions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("execution_id", name=op.f("pk_human_tasks")),
        schema="app",
    )
    op.create_index(
        op.f("ix_human_tasks_queued_at"),
        "human_tasks",
        ["queued_at"],
        unique=False,
        schema="app",
    )

    op.create_table(
        "human_wait_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("performer_user_id", sa.UUID(), nullable=False),
        sa.Column("rank_level", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="waiting", nullable=False),
        sa.Column(
            "ready_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("rank_level >= 1", name=op.f("ck_human_wait_entries_rank_level")),
        sa.CheckConstraint(
            "status IN ('waiting', 'matched', 'stopped', 'stale')",
            name=op.f("ck_human_wait_entries_status"),
        ),
        sa.CheckConstraint(
            "(status = 'waiting' AND ended_at IS NULL) OR "
            "(status != 'waiting' AND ended_at IS NOT NULL)",
            name=op.f("ck_human_wait_entries_state"),
        ),
        sa.ForeignKeyConstraint(
            ["performer_user_id"],
            ["app.users.id"],
            name=op.f("fk_human_wait_entries_performer_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_human_wait_entries")),
        sa.UniqueConstraint(
            "id",
            "performer_user_id",
            name="uq_human_wait_entries_id_performer",
        ),
        schema="app",
    )
    op.create_index(
        op.f("ix_human_wait_entries_performer_user_id"),
        "human_wait_entries",
        ["performer_user_id"],
        unique=False,
        schema="app",
    )
    op.create_index(
        "ix_human_wait_entries_fifo",
        "human_wait_entries",
        ["status", "ready_at"],
        unique=False,
        schema="app",
    )
    op.create_index(
        "uq_human_wait_entries_active_user",
        "human_wait_entries",
        ["performer_user_id"],
        unique=True,
        schema="app",
        postgresql_where=sa.text("status = 'waiting'"),
    )

    op.create_table(
        "human_claims",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("execution_id", sa.UUID(), nullable=False),
        sa.Column("wait_entry_id", sa.UUID(), nullable=False),
        sa.Column("performer_user_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column(
            "claimed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'answered', 'skipped', 'expired')",
            name=op.f("ck_human_claims_status"),
        ),
        sa.CheckConstraint(
            "(status = 'active' AND finished_at IS NULL) OR "
            "(status != 'active' AND finished_at IS NOT NULL)",
            name=op.f("ck_human_claims_state"),
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["app.human_tasks.execution_id"],
            name=op.f("fk_human_claims_execution_id_human_tasks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["performer_user_id"],
            ["app.users.id"],
            name=op.f("fk_human_claims_performer_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["wait_entry_id", "performer_user_id"],
            [
                "app.human_wait_entries.id",
                "app.human_wait_entries.performer_user_id",
            ],
            name="fk_human_claims_wait_entry_performer",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_human_claims")),
        sa.UniqueConstraint(
            "execution_id",
            "performer_user_id",
            name="uq_human_claims_execution_performer",
        ),
        sa.UniqueConstraint("wait_entry_id", name="uq_human_claims_wait_entry"),
        schema="app",
    )
    op.create_index(
        op.f("ix_human_claims_execution_id"),
        "human_claims",
        ["execution_id"],
        unique=False,
        schema="app",
    )
    op.create_index(
        op.f("ix_human_claims_performer_user_id"),
        "human_claims",
        ["performer_user_id"],
        unique=False,
        schema="app",
    )
    op.create_index(
        "uq_human_claims_active_execution",
        "human_claims",
        ["execution_id"],
        unique=True,
        schema="app",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "uq_human_claims_active_performer",
        "human_claims",
        ["performer_user_id"],
        unique=True,
        schema="app",
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM app.response_requests
            WHERE requested_answerer IN ('human-lite', 'human-pro')
            """
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM app.thread_entries
            WHERE author_actor_id IN (
                '00000000-0000-4000-8000-000000000003',
                '00000000-0000-4000-8000-000000000004'
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM app.thread_participants
            WHERE actor_id IN (
                '00000000-0000-4000-8000-000000000003',
                '00000000-0000-4000-8000-000000000004'
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE app.threads
            SET default_answerer = 'hina'
            WHERE default_answerer IN ('human-lite', 'human-pro')
            """
        )
    )
    op.drop_table("human_claims", schema="app")
    op.drop_table("human_wait_entries", schema="app")
    op.drop_table("human_tasks", schema="app")
    op.drop_table("human_profiles", schema="app")
    op.alter_column(
        "executions",
        "deadline_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        schema="app",
    )
    op.execute(
        sa.text(
            """
            DELETE FROM app.actors
            WHERE id IN (
                '00000000-0000-4000-8000-000000000003',
                '00000000-0000-4000-8000-000000000004'
            )
            """
        )
    )
