"""settle Human requests through the shared credit ledger

Revision ID: 20260731_0009
Revises: 20260730_0008
Create Date: 2026-07-31 12:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260731_0009"
down_revision: str | None = "20260730_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _replace_lot_guard(*, allow_earned_settlement: bool) -> None:
    earned_branch = (
        """
            IF transaction_kind = 'settle' AND (
                TG_TABLE_NAME = 'credit_lots'
                OR EXISTS (
                    SELECT 1 FROM app.credit_lots
                    WHERE issuance_transaction_id = target_transaction_id
                )
            ) THEN
                SELECT owner_account_id, original_amount, source_kind, issued_at,
                       expires_at
                INTO lot_owner_id, lot_amount, lot_source_kind, lot_issued_at,
                     lot_expires_at
                FROM app.credit_lots
                WHERE issuance_transaction_id = target_transaction_id;

                SELECT kind, owner_user_id, asset_code
                INTO lot_owner_kind, lot_owner_user_id, lot_owner_asset
                FROM app.credit_accounts
                WHERE id = lot_owner_id;

                SELECT COALESCE(sum(amount) FILTER (
                    WHERE account_id = lot_owner_id
                ), 0)
                INTO owner_posting
                FROM app.credit_postings
                WHERE transaction_id = target_transaction_id;

                IF lot_owner_id IS NULL
                   OR lot_owner_kind IS DISTINCT FROM 'user'
                   OR lot_owner_user_id IS NULL
                   OR lot_owner_asset IS DISTINCT FROM 'sodai-credit'
                   OR lot_source_kind IS DISTINCT FROM 'earned'
                   OR lot_expires_at IS NOT NULL
                   OR transaction_reference_type IS DISTINCT FROM
                        'inference_execution'
                   OR lot_issued_at IS DISTINCT FROM transaction_effective_at
                   OR owner_posting IS DISTINCT FROM lot_amount THEN
                    RAISE EXCEPTION 'earned credit lot % is inconsistent',
                        target_transaction_id;
                END IF;
                RETURN NULL;
            END IF;
        """
        if allow_earned_settlement
        else ""
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

            {earned_branch}

            IF transaction_kind IS DISTINCT FROM 'grant' THEN
                IF TG_TABLE_NAME = 'credit_lots' THEN
                    RAISE EXCEPTION
                        'credit lots require a grant or earned settlement transaction';
                END IF;
                RETURN NULL;
            END IF;

            SELECT owner_account_id, original_amount, source_kind, issued_at,
                   expires_at
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
                    WHERE account_id =
                        '00000000-0000-4000-9000-000000000001'
                ), 0),
                COALESCE(sum(amount) FILTER (
                    WHERE account_id = lot_owner_id
                ), 0),
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
               OR transaction_reference_type NOT IN (
                    'user_credit_grant',
                    'free_credit_allowance'
               )
               OR (
                    transaction_reference_type = 'free_credit_allowance'
                    AND (
                        lot_source_kind IS DISTINCT FROM 'promotional'
                        OR lot_expires_at IS NULL
                        OR lot_expires_at - lot_issued_at
                            IS DISTINCT FROM interval '168 hours'
                    )
               )
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


def _replace_registration_guard(*, allow_human: bool) -> None:
    human_branch = (
        """
            IF intent_maximum IS NULL THEN
                SELECT EXISTS (
                    SELECT 1
                    FROM app.human_tasks AS task
                    WHERE task.execution_id = target_execution_id
                ), space.owner_user_id
                INTO is_human_execution, human_owner_user_id
                FROM app.executions AS execution
                JOIN app.threads AS thread ON thread.id = execution.thread_id
                JOIN app.spaces AS space ON space.id = thread.space_id
                WHERE execution.id = target_execution_id;

                IF is_human_execution IS DISTINCT FROM TRUE
                   OR reservation_amount IS NULL
                   OR human_owner_user_id IS NULL
                   OR reservation_owner_user_id IS DISTINCT FROM
                        human_owner_user_id
                   OR reservation_asset_code IS DISTINCT FROM 'sodai-credit'
                THEN
                    RAISE EXCEPTION 'billing registration % is inconsistent',
                        target_execution_id;
                END IF;
                RETURN NULL;
            END IF;
        """
        if allow_human
        else ""
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION app.assert_billing_registration_consistent()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            target_execution_id uuid;
            intent_user_id uuid;
            intent_asset_code text;
            intent_maximum bigint;
            reservation_owner_user_id uuid;
            reservation_asset_code text;
            reservation_amount bigint;
            is_human_execution boolean;
            human_owner_user_id uuid;
        BEGIN
            target_execution_id := NEW.execution_reference_id;

            IF NOT EXISTS (
                SELECT 1
                FROM app.executions
                WHERE id = target_execution_id
            ) THEN
                RAISE EXCEPTION 'billing intent requires an execution';
            END IF;

            SELECT user_id, asset_code, maximum_charge
            INTO intent_user_id, intent_asset_code, intent_maximum
            FROM app.inference_billing_intents
            WHERE execution_reference_id = target_execution_id;

            SELECT account.owner_user_id, account.asset_code,
                   reservation.reserved_amount
            INTO reservation_owner_user_id, reservation_asset_code,
                 reservation_amount
            FROM app.inference_credit_reservations AS reservation
            JOIN app.credit_accounts AS account
              ON account.id = reservation.owner_account_id
            WHERE reservation.execution_reference_id = target_execution_id;

            {human_branch}

            IF intent_maximum IS NULL
               OR intent_asset_code IS DISTINCT FROM 'sodai-credit'
               OR (
                    intent_maximum = 0
                    AND reservation_amount IS NOT NULL
               )
               OR (
                    intent_maximum > 0
                    AND (
                        intent_user_id IS NULL
                        OR reservation_amount IS DISTINCT FROM intent_maximum
                        OR reservation_owner_user_id IS DISTINCT FROM
                            intent_user_id
                        OR reservation_asset_code IS DISTINCT FROM
                            intent_asset_code
                    )
               ) THEN
                RAISE EXCEPTION 'billing registration % is inconsistent',
                    target_execution_id;
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )


def _replace_finalization_guard(*, allow_reward: bool) -> None:
    unexpected_postings = (
        """
                count(*) FILTER (
                    WHERE account_id <> reservation_row.owner_account_id
                      AND account_id NOT IN (
                        '00000000-0000-4000-9000-000000000002',
                        '00000000-0000-4000-9000-000000000003',
                        '00000000-0000-4000-9000-000000000004'
                      )
                      AND (
                        reward_account_id IS NULL
                        OR account_id <> reward_account_id
                      )
                )
        """
        if allow_reward
        else """
                count(*) FILTER (
                    WHERE account_id NOT IN (
                        reservation_row.owner_account_id,
                        '00000000-0000-4000-9000-000000000002',
                        '00000000-0000-4000-9000-000000000003',
                        '00000000-0000-4000-9000-000000000004'
                    )
                )
        """
    )
    reward_checks = (
        """
               OR reward_amount < 0
               OR reward_amount > reservation_row.settled_amount
               OR (
                    reward_account_id IS NOT NULL
                    AND reward_account_id = reservation_row.owner_account_id
               )
               OR reward_posting IS DISTINCT FROM reward_amount
               OR revenue_posting + reward_amount
                    <> reservation_row.settled_amount
        """
        if allow_reward
        else """
               OR reward_account_id IS NOT NULL
               OR revenue_posting <> reservation_row.settled_amount
        """
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION app.assert_credit_reservation_finalized()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            target_reservation_id uuid;
            target_transaction_id uuid;
            observed_transaction_kind text;
            reservation_row app.inference_credit_reservations%ROWTYPE;
            transaction_kind text;
            transaction_reference_type text;
            transaction_reference_id uuid;
            transaction_effective_at timestamptz;
            reward_account_id uuid;
            reward_amount bigint;
            reserve_posting bigint;
            revenue_posting bigint;
            reward_posting bigint;
            owner_posting bigint;
            expired_posting bigint;
            settled_consumption bigint;
            expired_consumption bigint;
            unexpected_postings bigint;
            mismatched_consumptions bigint;
            invalid_allocation_finalizations bigint;
            invalid_fefo_consumptions bigint;
        BEGIN
            IF TG_TABLE_NAME = 'inference_credit_reservations' THEN
                target_reservation_id := NEW.id;
            ELSE
                IF TG_TABLE_NAME = 'credit_transactions' THEN
                    target_transaction_id := NEW.id;
                ELSE
                    target_transaction_id := NEW.transaction_id;
                END IF;
                SELECT kind INTO observed_transaction_kind
                FROM app.credit_transactions
                WHERE id = target_transaction_id;
                IF observed_transaction_kind NOT IN ('settle', 'release') THEN
                    RETURN NULL;
                END IF;
                SELECT id INTO target_reservation_id
                FROM app.inference_credit_reservations
                WHERE final_transaction_id = target_transaction_id;
            END IF;

            SELECT * INTO reservation_row
            FROM app.inference_credit_reservations
            WHERE id = target_reservation_id;

            SELECT kind, reference_type, reference_id, effective_at
            INTO transaction_kind, transaction_reference_type,
                 transaction_reference_id, transaction_effective_at
            FROM app.credit_transactions
            WHERE id = reservation_row.final_transaction_id;

            SELECT owner_account_id, original_amount
            INTO reward_account_id, reward_amount
            FROM app.credit_lots
            WHERE issuance_transaction_id =
                reservation_row.final_transaction_id;
            reward_amount := COALESCE(reward_amount, 0);

            SELECT
                COALESCE(sum(amount) FILTER (
                    WHERE account_id =
                        '00000000-0000-4000-9000-000000000002'
                ), 0),
                COALESCE(sum(amount) FILTER (
                    WHERE account_id =
                        '00000000-0000-4000-9000-000000000003'
                ), 0),
                COALESCE(sum(amount) FILTER (
                    WHERE account_id = reward_account_id
                ), 0),
                COALESCE(sum(amount) FILTER (
                    WHERE account_id = reservation_row.owner_account_id
                ), 0),
                COALESCE(sum(amount) FILTER (
                    WHERE account_id =
                        '00000000-0000-4000-9000-000000000004'
                ), 0),
                {unexpected_postings}
            INTO reserve_posting, revenue_posting, reward_posting,
                 owner_posting, expired_posting, unexpected_postings
            FROM app.credit_postings
            WHERE transaction_id = reservation_row.final_transaction_id;

            SELECT
                COALESCE(sum(amount) FILTER (WHERE kind = 'settle'), 0),
                COALESCE(sum(amount) FILTER (WHERE kind = 'expire'), 0)
            INTO settled_consumption, expired_consumption
            FROM app.credit_lot_consumptions
            WHERE transaction_id = reservation_row.final_transaction_id;

            SELECT count(*) INTO mismatched_consumptions
            FROM (
                SELECT consumption.lot_id
                FROM app.credit_lot_consumptions AS consumption
                LEFT JOIN app.credit_reservation_allocations AS allocation
                  ON allocation.reservation_id = reservation_row.id
                 AND allocation.lot_id = consumption.lot_id
                WHERE consumption.transaction_id =
                    reservation_row.final_transaction_id
                GROUP BY consumption.lot_id
                HAVING max(allocation.amount) IS NULL
                    OR sum(consumption.amount) > max(allocation.amount)
            ) AS invalid_consumption;

            SELECT count(*) INTO invalid_allocation_finalizations
            FROM (
                SELECT allocation.lot_id
                FROM app.credit_reservation_allocations AS allocation
                JOIN app.credit_lots AS lot ON lot.id = allocation.lot_id
                LEFT JOIN app.credit_lot_consumptions AS consumption
                  ON consumption.transaction_id =
                        reservation_row.final_transaction_id
                 AND consumption.lot_id = allocation.lot_id
                WHERE allocation.reservation_id = reservation_row.id
                GROUP BY allocation.lot_id, allocation.amount, lot.expires_at
                HAVING COALESCE(sum(consumption.amount), 0) > allocation.amount
                    OR (
                        lot.expires_at IS NOT NULL
                        AND lot.expires_at <= reservation_row.finalized_at
                        AND COALESCE(sum(consumption.amount) FILTER (
                            WHERE consumption.kind = 'expire'
                        ), 0) IS DISTINCT FROM (
                            allocation.amount
                            - COALESCE(sum(consumption.amount) FILTER (
                                WHERE consumption.kind = 'settle'
                            ), 0)
                        )
                    )
                    OR (
                        (lot.expires_at IS NULL
                         OR lot.expires_at > reservation_row.finalized_at)
                        AND COALESCE(sum(consumption.amount) FILTER (
                            WHERE consumption.kind = 'expire'
                        ), 0) <> 0
                    )
            ) AS invalid_allocation;

            SELECT count(*) INTO invalid_fefo_consumptions
            FROM (
                SELECT
                    allocation.lot_id,
                    COALESCE(sum(consumption.amount) FILTER (
                        WHERE consumption.kind = 'settle'
                    ), 0) AS actual_settled,
                    GREATEST(
                        LEAST(
                            reservation_row.settled_amount
                            - COALESCE(
                                sum(allocation.amount) OVER (
                                    ORDER BY lot.expires_at ASC NULLS LAST,
                                             lot.issued_at,
                                             lot.id
                                    ROWS BETWEEN UNBOUNDED PRECEDING
                                             AND 1 PRECEDING
                                ),
                                0
                            ),
                            allocation.amount
                        ),
                        0
                    ) AS expected_settled
                FROM app.credit_reservation_allocations AS allocation
                JOIN app.credit_lots AS lot ON lot.id = allocation.lot_id
                LEFT JOIN app.credit_lot_consumptions AS consumption
                  ON consumption.transaction_id =
                        reservation_row.final_transaction_id
                 AND consumption.lot_id = allocation.lot_id
                WHERE allocation.reservation_id = reservation_row.id
                GROUP BY allocation.lot_id, allocation.amount, lot.expires_at,
                         lot.issued_at, lot.id
            ) AS fefo
            WHERE actual_settled IS DISTINCT FROM expected_settled;

            IF transaction_kind IS DISTINCT FROM (
                    CASE
                        WHEN reservation_row.settled_amount > 0
                            THEN 'settle'
                        ELSE 'release'
                    END
               )
               OR transaction_reference_type IS DISTINCT FROM
                    'inference_execution'
               OR transaction_reference_id IS DISTINCT FROM
                    reservation_row.execution_reference_id
               OR reservation_row.finalized_at IS DISTINCT FROM
                    transaction_effective_at
               OR reservation_row.status IS DISTINCT FROM (
                    CASE
                        WHEN reservation_row.settled_amount > 0
                            THEN 'settled'
                        ELSE 'released'
                    END
               )
               OR reserve_posting <> -reservation_row.reserved_amount
               {reward_checks}
               OR settled_consumption <> reservation_row.settled_amount
               OR expired_posting <> expired_consumption
               OR owner_posting + expired_posting
                    + reservation_row.settled_amount
                    <> reservation_row.reserved_amount
               OR unexpected_postings <> 0
               OR mismatched_consumptions <> 0
               OR invalid_allocation_finalizations <> 0
               OR invalid_fefo_consumptions <> 0 THEN
                RAISE EXCEPTION
                    'credit reservation % finalization is inconsistent',
                    target_reservation_id;
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )


def _replace_execution_delete_guard(*, protect_human: bool) -> None:
    held_check = (
        """
            IF EXISTS (
                SELECT 1
                FROM app.inference_credit_reservations AS reservation
                WHERE reservation.execution_reference_id = OLD.id
                  AND reservation.status = 'held'
            ) THEN
                RAISE EXCEPTION
                    'billable executions must be finalized before deletion';
            END IF;
        """
        if protect_human
        else ""
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION app.protect_billable_execution_delete()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            {held_check}
            IF EXISTS (
                SELECT 1
                FROM app.inference_billing_intents AS intent
                WHERE intent.execution_reference_id = OLD.id
                  AND intent.maximum_charge > 0
            ) AND NOT EXISTS (
                SELECT 1
                FROM app.inference_usage_records AS usage
                WHERE usage.execution_reference_id = OLD.id
            ) THEN
                RAISE EXCEPTION
                    'billable executions must be finalized before deletion';
            END IF;
            RETURN OLD;
        END;
        $$
        """
    )


def upgrade() -> None:
    _replace_lot_guard(allow_earned_settlement=True)
    _replace_registration_guard(allow_human=True)
    _replace_finalization_guard(allow_reward=True)
    _replace_execution_delete_guard(protect_human=True)


def downgrade() -> None:
    _replace_execution_delete_guard(protect_human=False)
    _replace_finalization_guard(allow_reward=False)
    _replace_registration_guard(allow_human=False)
    _replace_lot_guard(allow_earned_settlement=False)
