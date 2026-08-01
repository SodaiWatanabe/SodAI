"""persist Human skip boundaries and declines

Revision ID: 20260801_0013
Revises: 20260801_0012
Create Date: 2026-08-01 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260801_0013"
down_revision: str | None = "20260801_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "human_claims",
        sa.Column("skip_allowed_until", sa.DateTime(timezone=True), nullable=True),
        schema="app",
    )
    op.execute(
        sa.text(
            """
            UPDATE app.human_claims
            SET skip_allowed_until = claimed_at + INTERVAL '20 seconds'
            """
        )
    )
    op.alter_column(
        "human_claims",
        "skip_allowed_until",
        nullable=False,
        schema="app",
    )
    _replace_status_check(
        "status IN ('active', 'answered', 'skipped', 'declined', 'expired', 'cancelled')"
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM app.human_claims WHERE status = 'declined'
                ) THEN
                    RAISE EXCEPTION
                        'cannot remove Human declines while application data uses them';
                END IF;
            END
            $$;
            """
        )
    )
    _replace_status_check("status IN ('active', 'answered', 'skipped', 'expired', 'cancelled')")
    op.drop_column("human_claims", "skip_allowed_until", schema="app")


def _replace_status_check(condition: str) -> None:
    constraint_name = op.f("ck_human_claims_status")
    op.drop_constraint(
        constraint_name,
        "human_claims",
        schema="app",
        type_="check",
    )
    op.create_check_constraint(
        constraint_name,
        "human_claims",
        condition,
        schema="app",
    )
