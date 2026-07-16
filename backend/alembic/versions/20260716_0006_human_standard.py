"""add Human Standard and normalize Human ranks

Revision ID: 20260716_0006
Revises: 20260715_0005
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260716_0006"
down_revision: str | None = "20260715_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO app.actors (id, kind, key, name)
            VALUES (
                '00000000-0000-4000-8000-000000000005',
                'model',
                'model:human-standard',
                'Human Standard'
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE app.human_tasks AS task
            SET required_rank_level = 3
            FROM app.executions AS execution
            JOIN app.response_requests AS request
              ON request.id = execution.response_request_id
            WHERE task.execution_id = execution.id
              AND request.requested_answerer = 'human-pro'
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
                    WHERE requested_answerer = 'human-standard'
                ) OR EXISTS (
                    SELECT 1
                    FROM app.threads
                    WHERE default_answerer = 'human-standard'
                ) THEN
                    RAISE EXCEPTION
                        'cannot remove Human Standard while application data uses it';
                END IF;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE app.human_tasks AS task
            SET required_rank_level = 2
            FROM app.executions AS execution
            JOIN app.response_requests AS request
              ON request.id = execution.response_request_id
            WHERE task.execution_id = execution.id
              AND request.requested_answerer = 'human-pro'
            """
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM app.actors
            WHERE id = '00000000-0000-4000-8000-000000000005'
            """
        )
    )
