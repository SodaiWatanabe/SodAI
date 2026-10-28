"""use Asuka for threads whose default model has been retired

Revision ID: 20261028_0019
Revises: 20260902_0018
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261028_0019"
down_revision: str | None = "20260902_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Historical requests and result authors remain immutable audit records.
    op.execute(
        sa.text(
            """
            UPDATE app.threads
            SET default_answerer = 'asuka-1.1'
            WHERE default_answerer = 'hina'
            """
        )
    )


def downgrade() -> None:
    # Asuka was already a valid default before this migration. The previous
    # per-thread choice cannot be reconstructed without rewriting history.
    pass
