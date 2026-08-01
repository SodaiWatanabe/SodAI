"""persist Human answer drafts

Revision ID: 20260801_0012
Revises: 20260731_0011
Create Date: 2026-08-01 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260801_0012"
down_revision: str | None = "20260731_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "human_claims",
        sa.Column("draft_content", sa.Text(), server_default="", nullable=False),
        schema="app",
    )
    op.add_column(
        "human_claims",
        sa.Column(
            "draft_revision",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        schema="app",
    )
    op.add_column(
        "human_claims",
        sa.Column("draft_updated_at", sa.DateTime(timezone=True), nullable=True),
        schema="app",
    )
    op.create_check_constraint(
        op.f("ck_human_claims_draft_content_length"),
        "human_claims",
        "char_length(draft_content) <= 32000",
        schema="app",
    )
    op.create_check_constraint(
        op.f("ck_human_claims_draft_revision"),
        "human_claims",
        "draft_revision >= 0",
        schema="app",
    )
    op.create_check_constraint(
        op.f("ck_human_claims_draft_state"),
        "human_claims",
        "status = 'active' OR (draft_content = '' AND draft_updated_at IS NULL)",
        schema="app",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_human_claims_draft_state"),
        "human_claims",
        schema="app",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_human_claims_draft_revision"),
        "human_claims",
        schema="app",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_human_claims_draft_content_length"),
        "human_claims",
        schema="app",
        type_="check",
    )
    op.drop_column("human_claims", "draft_updated_at", schema="app")
    op.drop_column("human_claims", "draft_revision", schema="app")
    op.drop_column("human_claims", "draft_content", schema="app")
