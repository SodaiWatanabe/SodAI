"""add Asuka 1.1 model actor

Revision ID: 20260902_0018
Revises: 20260807_0017
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260902_0018"
down_revision: str | None = "20260807_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO app.actors (id, kind, key, name)
            VALUES (
                '00000000-0000-4000-8000-000000000006',
                'model',
                'model:asuka-1.1',
                'Asuka 1.1'
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE app.threads
            SET default_answerer = 'asuka-1.1'
            WHERE default_answerer = 'asuka-1'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM app.response_requests
                    WHERE requested_answerer = 'asuka-1.1'
                ) THEN
                    RAISE EXCEPTION
                        'cannot remove Asuka 1.1 while application data uses it';
                END IF;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE app.threads
            SET default_answerer = 'asuka-1'
            WHERE default_answerer = 'asuka-1.1'
            """
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM app.actors
            WHERE id = '00000000-0000-4000-8000-000000000006'
            """
        )
    )
