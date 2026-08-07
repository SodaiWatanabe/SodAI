"""persist model thinking separately from answer output

Revision ID: 20260807_0017
Revises: 20260801_0016
Create Date: 2026-08-07 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260807_0017"
down_revision: str | None = "20260801_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "executions",
        sa.Column("thinking_output", sa.Text(), nullable=True),
        schema="app",
    )
    op.add_column(
        "executions",
        sa.Column("thinking_tokens", sa.Integer(), nullable=True),
        schema="app",
    )
    op.add_column(
        "executions",
        sa.Column("answer_tokens", sa.Integer(), nullable=True),
        schema="app",
    )
    op.add_column(
        "executions",
        sa.Column("generation_phase", sa.String(length=16), nullable=True),
        schema="app",
    )
    op.create_check_constraint(
        op.f("ck_executions_thinking_tokens_nonnegative"),
        "executions",
        "thinking_tokens IS NULL OR thinking_tokens >= 0",
        schema="app",
    )
    op.create_check_constraint(
        op.f("ck_executions_answer_tokens_nonnegative"),
        "executions",
        "answer_tokens IS NULL OR answer_tokens >= 0",
        schema="app",
    )
    op.create_check_constraint(
        op.f("ck_executions_channel_tokens_within_output"),
        "executions",
        "thinking_tokens IS NULL OR answer_tokens IS NULL OR output_tokens IS NULL OR "
        "thinking_tokens + answer_tokens <= output_tokens",
        schema="app",
    )
    op.create_check_constraint(
        op.f("ck_executions_generation_phase"),
        "executions",
        "generation_phase IS NULL OR (status = 'running' AND "
        "generation_phase IN ('thinking', 'answering'))",
        schema="app",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_executions_generation_phase"),
        "executions",
        schema="app",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_executions_channel_tokens_within_output"),
        "executions",
        schema="app",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_executions_answer_tokens_nonnegative"),
        "executions",
        schema="app",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_executions_thinking_tokens_nonnegative"),
        "executions",
        schema="app",
        type_="check",
    )
    op.drop_column("executions", "generation_phase", schema="app")
    op.drop_column("executions", "answer_tokens", schema="app")
    op.drop_column("executions", "thinking_tokens", schema="app")
    op.drop_column("executions", "thinking_output", schema="app")
