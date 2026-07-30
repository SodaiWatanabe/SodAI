"""add shared reasoning effort to response requests

Revision ID: 20260730_0008
Revises: 20260716_0007
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260730_0008"
down_revision: str | None = "20260716_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "response_requests",
        sa.Column(
            "reasoning_effort",
            sa.String(length=16),
            server_default="none",
            nullable=False,
        ),
        schema="app",
    )
    op.execute(
        sa.text(
            """
            UPDATE app.response_requests
               SET reasoning_effort = 'medium'
             WHERE requested_answerer IN (
                 'human-lite',
                 'human-standard',
                 'human-pro'
             )
            """
        )
    )
    op.create_check_constraint(
        op.f("ck_response_requests_reasoning_effort"),
        "response_requests",
        "reasoning_effort IN ('none', 'low', 'medium', 'high', 'xhigh')",
        schema="app",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_response_requests_reasoning_effort"),
        "response_requests",
        schema="app",
        type_="check",
    )
    op.drop_column("response_requests", "reasoning_effort", schema="app")
