"""add response regeneration lineage

Revision ID: 20260801_0016
Revises: 20260801_0015
Create Date: 2026-08-01 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260801_0016"
down_revision: str | None = "20260801_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "response_requests",
        sa.Column(
            "regenerated_from_response_request_id",
            sa.UUID(),
            nullable=True,
        ),
        schema="app",
    )
    op.create_check_constraint(
        op.f("ck_response_requests_regenerated_from_other_request"),
        "response_requests",
        "regenerated_from_response_request_id IS NULL OR "
        "regenerated_from_response_request_id <> id",
        schema="app",
    )
    op.create_unique_constraint(
        op.f("uq_response_requests_regenerated_from"),
        "response_requests",
        ["regenerated_from_response_request_id"],
        schema="app",
    )
    op.create_foreign_key(
        op.f("fk_response_requests_regenerated_from_same_thread"),
        "response_requests",
        "response_requests",
        ["regenerated_from_response_request_id", "thread_id"],
        ["id", "thread_id"],
        source_schema="app",
        referent_schema="app",
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_response_requests_regenerated_from_same_thread"),
        "response_requests",
        schema="app",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("uq_response_requests_regenerated_from"),
        "response_requests",
        schema="app",
        type_="unique",
    )
    op.drop_constraint(
        op.f("ck_response_requests_regenerated_from_other_request"),
        "response_requests",
        schema="app",
        type_="check",
    )
    op.drop_column(
        "response_requests",
        "regenerated_from_response_request_id",
        schema="app",
    )
