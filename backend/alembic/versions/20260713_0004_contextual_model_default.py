"""主体別モデルデフォルトの強制

Revision ID: 20260713_0004
Revises: 20260713_0003
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260713_0004"
down_revision: str | None = "20260713_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "app"


def upgrade() -> None:
    op.alter_column(
        "conversations",
        "default_model",
        schema=SCHEMA,
        existing_type=sa.String(length=64),
        server_default=None,
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "conversations",
        "default_model",
        schema=SCHEMA,
        existing_type=sa.String(length=64),
        server_default="hina",
        existing_nullable=False,
    )
