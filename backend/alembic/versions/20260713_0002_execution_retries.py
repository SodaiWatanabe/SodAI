"""normalize response execution retries

Revision ID: 20260713_0002
Revises: 20260713_0001
Create Date: 2026-07-13 19:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260713_0002"
down_revision: str | None = "20260713_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_response_requests_state"),
        "response_requests",
        schema="app",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_response_requests_state"),
        "response_requests",
        "(status = 'queued' AND finished_at IS NULL) OR "
        "(status = 'running' AND started_at IS NOT NULL AND finished_at IS NULL) OR "
        "(status IN ('completed', 'failed') AND finished_at IS NOT NULL)",
        schema="app",
    )
    op.add_column(
        "executions",
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=True),
        schema="app",
    )
    op.create_check_constraint(
        op.f("ck_executions_attempt_no"),
        "executions",
        "attempt_no >= 1",
        schema="app",
    )
    op.create_check_constraint(
        op.f("ck_executions_idempotency_key_hash"),
        "executions",
        "idempotency_key_hash IS NULL OR length(idempotency_key_hash) = 64",
        schema="app",
    )
    op.create_unique_constraint(
        op.f("uq_executions_request_idempotency"),
        "executions",
        ["response_request_id", "idempotency_key_hash"],
        schema="app",
    )
    op.create_index(
        op.f("uq_executions_completed_request"),
        "executions",
        ["response_request_id"],
        unique=True,
        schema="app",
        postgresql_where=sa.text("status = 'completed'"),
    )


def downgrade() -> None:
    op.drop_index(
        op.f("uq_executions_completed_request"),
        table_name="executions",
        schema="app",
    )
    op.drop_constraint(
        op.f("uq_executions_request_idempotency"),
        "executions",
        schema="app",
        type_="unique",
    )
    op.drop_constraint(
        op.f("ck_executions_idempotency_key_hash"),
        "executions",
        schema="app",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_executions_attempt_no"),
        "executions",
        schema="app",
        type_="check",
    )
    op.drop_column("executions", "idempotency_key_hash", schema="app")
    op.drop_constraint(
        op.f("ck_response_requests_state"),
        "response_requests",
        schema="app",
        type_="check",
    )
    op.execute(
        "UPDATE app.response_requests SET started_at = NULL "
        "WHERE status = 'queued'"
    )
    op.create_check_constraint(
        op.f("ck_response_requests_state"),
        "response_requests",
        "(status = 'queued' AND started_at IS NULL AND finished_at IS NULL) OR "
        "(status = 'running' AND started_at IS NOT NULL AND finished_at IS NULL) OR "
        "(status IN ('completed', 'failed') AND finished_at IS NOT NULL)",
        schema="app",
    )
