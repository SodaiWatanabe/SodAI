"""persist Human answer conditions

Revision ID: 20260801_0015
Revises: 20260801_0014
Create Date: 2026-08-01 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260801_0015"
down_revision: str | None = "20260801_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "human_profiles",
        sa.Column(
            "accepted_answerer_ids",
            postgresql.ARRAY(sa.String(length=64)),
            server_default=sa.text("ARRAY['human-lite']::varchar[]"),
            nullable=False,
        ),
        schema="app",
    )
    op.add_column(
        "human_profiles",
        sa.Column(
            "accepted_reasoning_efforts",
            postgresql.ARRAY(sa.String(length=16)),
            server_default=sa.text("ARRAY['low']::varchar[]"),
            nullable=False,
        ),
        schema="app",
    )
    op.create_check_constraint(
        op.f("ck_human_profiles_accepted_answerer_ids"),
        "human_profiles",
        "cardinality(accepted_answerer_ids) > 0 AND "
        "accepted_answerer_ids <@ "
        "ARRAY['human-lite', 'human-standard', 'human-pro']::varchar[]",
        schema="app",
    )
    op.create_check_constraint(
        op.f("ck_human_profiles_accepted_reasoning_efforts"),
        "human_profiles",
        "cardinality(accepted_reasoning_efforts) > 0 AND "
        "accepted_reasoning_efforts <@ "
        "ARRAY['low', 'medium', 'high', 'xhigh']::varchar[]",
        schema="app",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_human_profiles_accepted_reasoning_efforts"),
        "human_profiles",
        schema="app",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_human_profiles_accepted_answerer_ids"),
        "human_profiles",
        schema="app",
        type_="check",
    )
    op.drop_column("human_profiles", "accepted_reasoning_efforts", schema="app")
    op.drop_column("human_profiles", "accepted_answerer_ids", schema="app")
