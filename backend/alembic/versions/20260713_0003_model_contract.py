"""Hina・Asuka 1モデル契約への完全移行

Revision ID: 20260713_0003
Revises: 20260712_0002
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260713_0003"
down_revision: str | None = "20260712_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "app"


def _assert_legacy_contract_is_known() -> None:
    connection = op.get_bind()
    unknown_conversations = connection.scalar(
        sa.text(
            f"SELECT count(*) FROM {SCHEMA}.conversations "
            "WHERE default_model NOT IN ('archive', 'flagship')"
        )
    )
    unknown_requests = connection.scalar(
        sa.text(
            f"SELECT count(*) FROM {SCHEMA}.inference_runs "
            "WHERE requested_model NOT IN ('archive', 'flagship')"
        )
    )
    unknown_resolutions = connection.scalar(
        sa.text(
            f"SELECT count(*) FROM {SCHEMA}.inference_runs "
            "WHERE resolved_model NOT IN "
            "('pseudo-sodai-archive-v1', 'pseudo-sodai-flagship-v1')"
        )
    )
    if unknown_conversations or unknown_requests or unknown_resolutions:
        raise RuntimeError("Unknown model identifiers prevent model contract migration")


def upgrade() -> None:
    _assert_legacy_contract_is_known()
    op.execute(
        sa.text(
            f"UPDATE {SCHEMA}.conversations SET default_model = CASE default_model "
            "WHEN 'archive' THEN 'hina' WHEN 'flagship' THEN 'asuka-1' END"
        )
    )
    op.execute(
        sa.text(
            f"UPDATE {SCHEMA}.inference_runs SET requested_model = CASE requested_model "
            "WHEN 'archive' THEN 'hina' WHEN 'flagship' THEN 'asuka-1' END, "
            "resolved_model = CASE resolved_model "
            "WHEN 'pseudo-sodai-archive-v1' THEN 'pseudo-sodai-hina-v1' "
            "WHEN 'pseudo-sodai-flagship-v1' THEN 'pseudo-sodai-asuka-1-v1' END"
        )
    )
    op.alter_column(
        "conversations",
        "default_model",
        schema=SCHEMA,
        existing_type=sa.String(length=64),
        server_default="hina",
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "conversations",
        "default_model",
        schema=SCHEMA,
        existing_type=sa.String(length=64),
        server_default="archive",
        existing_nullable=False,
    )
    op.execute(
        sa.text(
            f"UPDATE {SCHEMA}.inference_runs SET requested_model = CASE requested_model "
            "WHEN 'hina' THEN 'archive' WHEN 'asuka-1' THEN 'flagship' END, "
            "resolved_model = CASE resolved_model "
            "WHEN 'pseudo-sodai-hina-v1' THEN 'pseudo-sodai-archive-v1' "
            "WHEN 'pseudo-sodai-asuka-1-v1' THEN 'pseudo-sodai-flagship-v1' END"
        )
    )
    op.execute(
        sa.text(
            f"UPDATE {SCHEMA}.conversations SET default_model = CASE default_model "
            "WHEN 'hina' THEN 'archive' WHEN 'asuka-1' THEN 'flagship' END"
        )
    )
