"""derive Human ranks from answer quality and reliability

Revision ID: 20260801_0014
Revises: 20260801_0013
Create Date: 2026-08-01 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260801_0014"
down_revision: str | None = "20260801_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "human_profiles",
        sa.Column("rank_changed_at", sa.DateTime(timezone=True), nullable=True),
        schema="app",
    )
    op.execute(
        sa.text(
            """
            UPDATE app.human_profiles
            SET rank_changed_at = updated_at
            """
        )
    )
    op.alter_column(
        "human_profiles",
        "rank_changed_at",
        nullable=False,
        server_default=sa.text("now()"),
        schema="app",
    )

    _replace_rank_check(
        "human_profiles",
        "rank_level",
        "rank_level BETWEEN 1 AND 3",
    )
    _replace_rank_check(
        "human_tasks",
        "required_rank_level",
        "required_rank_level BETWEEN 1 AND 3",
    )
    _replace_rank_check(
        "human_wait_entries",
        "rank_level",
        "rank_level BETWEEN 1 AND 3",
    )

    op.create_table(
        "human_rank_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("performer_user_id", sa.UUID(), nullable=False),
        sa.Column("previous_rank_level", sa.Integer(), nullable=False),
        sa.Column("rank_level", sa.Integer(), nullable=False),
        sa.Column("policy_revision", sa.String(length=32), nullable=False),
        sa.Column("trigger_kind", sa.String(length=32), nullable=False),
        sa.Column("trigger_execution_id", sa.UUID(), nullable=True),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "previous_rank_level BETWEEN 1 AND 3",
            name=op.f("ck_human_rank_events_previous_rank_level"),
        ),
        sa.CheckConstraint(
            "rank_level BETWEEN 1 AND 3",
            name=op.f("ck_human_rank_events_rank_level"),
        ),
        sa.CheckConstraint(
            "previous_rank_level != rank_level",
            name=op.f("ck_human_rank_events_rank_changed"),
        ),
        sa.CheckConstraint(
            "trigger_kind IN "
            "('answer_completed', 'answer_expired', 'evaluation_set', "
            "'evaluation_cleared', 'manual')",
            name=op.f("ck_human_rank_events_trigger_kind"),
        ),
        sa.CheckConstraint(
            "reason IN ('promotion', 'quality', 'reliability', 'manual')",
            name=op.f("ck_human_rank_events_reason"),
        ),
        sa.ForeignKeyConstraint(
            ["performer_user_id"],
            ["app.users.id"],
            name=op.f("fk_human_rank_events_performer_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["trigger_execution_id"],
            ["app.executions.id"],
            name=op.f("fk_human_rank_events_trigger_execution_id_executions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_human_rank_events")),
        schema="app",
    )
    op.create_index(
        "ix_human_rank_events_performer_created",
        "human_rank_events",
        ["performer_user_id", "created_at"],
        schema="app",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_human_rank_events_performer_created",
        table_name="human_rank_events",
        schema="app",
    )
    op.drop_table("human_rank_events", schema="app")

    _replace_rank_check("human_wait_entries", "rank_level", "rank_level >= 1")
    _replace_rank_check("human_tasks", "required_rank_level", "required_rank_level >= 1")
    _replace_rank_check("human_profiles", "rank_level", "rank_level >= 1")
    op.drop_column("human_profiles", "rank_changed_at", schema="app")


def _replace_rank_check(table_name: str, constraint: str, condition: str) -> None:
    constraint_name = op.f(f"ck_{table_name}_{constraint}")
    op.drop_constraint(
        constraint_name,
        table_name,
        schema="app",
        type_="check",
    )
    op.create_check_constraint(
        constraint_name,
        table_name,
        condition,
        schema="app",
    )
