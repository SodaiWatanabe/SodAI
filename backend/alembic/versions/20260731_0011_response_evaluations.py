"""add generic response evaluations

Revision ID: 20260731_0011
Revises: 20260731_0010
Create Date: 2026-07-31 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_0011"
down_revision: str | None = "20260731_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "response_evaluations",
        sa.Column("execution_id", sa.UUID(), nullable=False),
        sa.Column("value", sa.String(length=16), nullable=False),
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
        sa.CheckConstraint(
            "value IN ('positive', 'negative')",
            name=op.f("ck_response_evaluations_value"),
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["app.executions.id"],
            name=op.f("fk_response_evaluations_execution_id_executions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "execution_id",
            name=op.f("pk_response_evaluations"),
        ),
        schema="app",
    )


def downgrade() -> None:
    op.drop_table("response_evaluations", schema="app")
