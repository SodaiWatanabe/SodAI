"""identify on-demand free-credit allowance grants

Revision ID: 20260714_0004
Revises: 20260713_0003
Create Date: 2026-07-14 18:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260714_0004"
down_revision: str | None = "20260713_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _replace_grant_guard(*, allow_free_allowance: bool) -> None:
    reference_check = (
        "transaction_reference_type NOT IN "
        "('user_credit_grant', 'free_credit_allowance')"
        if allow_free_allowance
        else "transaction_reference_type IS DISTINCT FROM 'user_credit_grant'"
    )
    allowance_shape_check = (
        "(transaction_reference_type = 'free_credit_allowance' AND ("
        "lot_source_kind IS DISTINCT FROM 'promotional' "
        "OR lot_expires_at IS NULL "
        "OR lot_expires_at - lot_issued_at IS DISTINCT FROM interval '168 hours'))"
        if allow_free_allowance
        else "FALSE"
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION app.assert_credit_grant_consistent()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            target_transaction_id uuid;
            transaction_kind text;
            transaction_reference_type text;
            transaction_reference_id uuid;
            transaction_effective_at timestamptz;
            lot_owner_id uuid;
            lot_owner_kind text;
            lot_owner_user_id uuid;
            lot_owner_asset text;
            lot_amount bigint;
            lot_source_kind text;
            lot_issued_at timestamptz;
            lot_expires_at timestamptz;
            issuance_posting bigint;
            owner_posting bigint;
            unexpected_postings bigint;
        BEGIN
            IF TG_TABLE_NAME = 'credit_lots' THEN
                target_transaction_id := NEW.issuance_transaction_id;
            ELSIF TG_TABLE_NAME = 'credit_postings' THEN
                target_transaction_id := NEW.transaction_id;
            ELSE
                target_transaction_id := NEW.id;
            END IF;

            SELECT kind, reference_type, reference_id, effective_at
            INTO transaction_kind, transaction_reference_type,
                 transaction_reference_id, transaction_effective_at
            FROM app.credit_transactions
            WHERE id = target_transaction_id;

            IF transaction_kind IS DISTINCT FROM 'grant' THEN
                IF TG_TABLE_NAME = 'credit_lots' THEN
                    RAISE EXCEPTION 'credit lots require a grant transaction';
                END IF;
                RETURN NULL;
            END IF;

            SELECT owner_account_id, original_amount, source_kind, issued_at, expires_at
            INTO lot_owner_id, lot_amount, lot_source_kind, lot_issued_at,
                 lot_expires_at
            FROM app.credit_lots
            WHERE issuance_transaction_id = target_transaction_id;

            SELECT kind, owner_user_id, asset_code
            INTO lot_owner_kind, lot_owner_user_id, lot_owner_asset
            FROM app.credit_accounts
            WHERE id = lot_owner_id;

            SELECT
                COALESCE(sum(amount) FILTER (
                    WHERE account_id = '00000000-0000-4000-9000-000000000001'
                ), 0),
                COALESCE(sum(amount) FILTER (WHERE account_id = lot_owner_id), 0),
                count(*) FILTER (
                    WHERE account_id NOT IN (
                        lot_owner_id,
                        '00000000-0000-4000-9000-000000000001'
                    )
                )
            INTO issuance_posting, owner_posting, unexpected_postings
            FROM app.credit_postings
            WHERE transaction_id = target_transaction_id;

            IF lot_owner_id IS NULL
               OR lot_owner_kind IS DISTINCT FROM 'user'
               OR lot_owner_user_id IS NULL
               OR lot_owner_asset IS DISTINCT FROM 'sodai-credit'
               OR {reference_check}
               OR {allowance_shape_check}
               OR transaction_reference_id IS DISTINCT FROM lot_owner_id
               OR lot_issued_at IS DISTINCT FROM transaction_effective_at
               OR issuance_posting IS DISTINCT FROM -lot_amount
               OR owner_posting IS DISTINCT FROM lot_amount
               OR unexpected_postings IS DISTINCT FROM 0 THEN
                RAISE EXCEPTION 'credit grant % does not match its lot',
                    target_transaction_id;
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )


def upgrade() -> None:
    _replace_grant_guard(allow_free_allowance=True)


def downgrade() -> None:
    _replace_grant_guard(allow_free_allowance=False)
