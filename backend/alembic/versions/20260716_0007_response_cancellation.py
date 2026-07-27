"""Add first-class response cancellation.

Revision ID: 20260716_0007
Revises: 20260716_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260716_0007"
down_revision: str | None = "20260716_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _replace_check(
        "response_requests",
        "status",
        "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
    )
    _replace_check(
        "response_requests",
        "state",
        "(status = 'queued' AND finished_at IS NULL) OR "
        "(status = 'running' AND started_at IS NOT NULL AND finished_at IS NULL) OR "
        "(status IN ('completed', 'failed', 'cancelled') AND finished_at IS NOT NULL)",
    )
    _replace_check(
        "executions",
        "status",
        "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
    )
    _replace_check(
        "executions",
        "state",
        "(status = 'queued' AND started_at IS NULL AND finished_at IS NULL "
        "AND result_entry_id IS NULL AND error_code IS NULL) OR "
        "(status = 'running' AND started_at IS NOT NULL AND finished_at IS NULL "
        "AND lease_expires_at IS NOT NULL AND result_entry_id IS NULL "
        "AND error_code IS NULL) OR "
        "(status = 'completed' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
        "AND result_entry_id IS NOT NULL AND error_code IS NULL "
        "AND lease_expires_at IS NULL) OR "
        "(status = 'failed' AND finished_at IS NOT NULL AND result_entry_id IS NULL "
        "AND error_code IS NOT NULL AND lease_expires_at IS NULL) OR "
        "(status = 'cancelled' AND finished_at IS NOT NULL AND error_code IS NULL "
        "AND lease_expires_at IS NULL)",
    )
    _replace_check(
        "human_claims",
        "status",
        "status IN ('active', 'answered', 'skipped', 'expired', 'cancelled')",
    )
    _replace_check(
        "inference_usage_records",
        "outcome",
        "outcome IN ('completed', 'failed', 'cancelled')",
    )
    _replace_check(
        "inference_usage_records",
        "billing_reason",
        "billing_reason IN ('free', 'completed', 'failed', 'cancelled', 'unmetered')",
    )
    _replace_usage_consistency_function(include_cancellation=True)


def downgrade() -> None:
    _assert_no_cancellation_rows()

    _replace_check(
        "inference_usage_records",
        "billing_reason",
        "billing_reason IN ('free', 'completed', 'failed', 'unmetered')",
    )
    _replace_check(
        "inference_usage_records",
        "outcome",
        "outcome IN ('completed', 'failed')",
    )
    _replace_check(
        "human_claims",
        "status",
        "status IN ('active', 'answered', 'skipped', 'expired')",
    )
    _replace_check(
        "executions",
        "state",
        "(status = 'queued' AND started_at IS NULL AND finished_at IS NULL "
        "AND result_entry_id IS NULL AND error_code IS NULL) OR "
        "(status = 'running' AND started_at IS NOT NULL AND finished_at IS NULL "
        "AND lease_expires_at IS NOT NULL AND result_entry_id IS NULL "
        "AND error_code IS NULL) OR "
        "(status = 'completed' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
        "AND result_entry_id IS NOT NULL AND error_code IS NULL "
        "AND lease_expires_at IS NULL) OR "
        "(status = 'failed' AND finished_at IS NOT NULL AND result_entry_id IS NULL "
        "AND error_code IS NOT NULL AND lease_expires_at IS NULL)",
    )
    _replace_check(
        "executions",
        "status",
        "status IN ('queued', 'running', 'completed', 'failed')",
    )
    _replace_check(
        "response_requests",
        "state",
        "(status = 'queued' AND finished_at IS NULL) OR "
        "(status = 'running' AND started_at IS NOT NULL AND finished_at IS NULL) OR "
        "(status IN ('completed', 'failed') AND finished_at IS NOT NULL)",
    )
    _replace_check(
        "response_requests",
        "status",
        "status IN ('queued', 'running', 'completed', 'failed')",
    )
    _replace_usage_consistency_function(include_cancellation=False)


def _replace_check(table: str, name: str, condition: str) -> None:
    constraint_name = op.f(f"ck_{table}_{name}")
    op.drop_constraint(constraint_name, table, schema="app", type_="check")
    op.create_check_constraint(constraint_name, table, condition, schema="app")


def _assert_no_cancellation_rows() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM app.executions WHERE status = 'cancelled')
                   OR EXISTS (
                       SELECT 1 FROM app.response_requests WHERE status = 'cancelled'
                   )
                   OR EXISTS (SELECT 1 FROM app.human_claims WHERE status = 'cancelled')
                   OR EXISTS (
                       SELECT 1
                         FROM app.inference_usage_records
                        WHERE outcome = 'cancelled' OR billing_reason = 'cancelled'
                   ) THEN
                    RAISE EXCEPTION
                        'response cancellation history must be retained before downgrade';
                END IF;
            END;
            $$
            """
        )
    )


def _replace_usage_consistency_function(*, include_cancellation: bool) -> None:
    cancellation_branch = """
            ELSIF NEW.outcome = 'cancelled' THEN
                IF NEW.input_tokens IS NULL THEN
                    expected_charge := 0;
                ELSE
                    expected_charge := LEAST(
                        intent_fixed::numeric
                        + NEW.input_tokens::numeric * intent_input_rate::numeric
                        + COALESCE(NEW.output_tokens, 0)::numeric
                          * intent_output_rate::numeric,
                        intent_maximum::numeric
                    )::bigint;
                END IF;
                expected_reason := 'cancelled';
    """ if include_cancellation else ""
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION app.assert_inference_usage_consistent()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                intent_user_id uuid;
                intent_revision text;
                intent_fixed bigint;
                intent_input_rate bigint;
                intent_output_rate bigint;
                intent_maximum bigint;
                intent_unmetered bigint;
                execution_status text;
                execution_input_tokens bigint;
                execution_output_tokens bigint;
                reservation_status text;
                reservation_settled bigint;
                expected_charge bigint;
                expected_reason text;
            BEGIN
                SELECT
                    intent.user_id,
                    intent.tariff_revision,
                    intent.fixed_charge,
                    intent.input_token_rate,
                    intent.output_token_rate,
                    intent.maximum_charge,
                    intent.unmetered_charge,
                    execution.status,
                    execution.input_tokens,
                    execution.output_tokens
                INTO intent_user_id, intent_revision, intent_fixed,
                     intent_input_rate, intent_output_rate, intent_maximum,
                     intent_unmetered, execution_status, execution_input_tokens,
                     execution_output_tokens
                FROM app.inference_billing_intents AS intent
                JOIN app.executions AS execution
                  ON execution.id = intent.execution_reference_id
                WHERE intent.execution_reference_id = NEW.execution_reference_id;

                IF NEW.outcome = 'failed' THEN
                    expected_charge := 0;
                    expected_reason := 'failed';
                {cancellation_branch}
                ELSIF intent_maximum = 0 THEN
                    expected_charge := 0;
                    expected_reason := 'free';
                ELSIF NEW.input_tokens IS NULL OR NEW.output_tokens IS NULL THEN
                    expected_charge := intent_unmetered;
                    expected_reason := 'unmetered';
                ELSE
                    expected_charge := LEAST(
                        intent_fixed::numeric
                        + NEW.input_tokens::numeric * intent_input_rate::numeric
                        + NEW.output_tokens::numeric * intent_output_rate::numeric,
                        intent_maximum::numeric
                    )::bigint;
                    expected_reason := 'completed';
                END IF;

                SELECT status, settled_amount
                INTO reservation_status, reservation_settled
                FROM app.inference_credit_reservations
                WHERE execution_reference_id = NEW.execution_reference_id;

                IF intent_revision IS NULL
                   OR NEW.user_id IS DISTINCT FROM intent_user_id
                   OR NEW.tariff_revision IS DISTINCT FROM intent_revision
                   OR NEW.outcome IS DISTINCT FROM execution_status
                   OR NEW.input_tokens IS DISTINCT FROM execution_input_tokens
                   OR NEW.output_tokens IS DISTINCT FROM execution_output_tokens
                   OR NEW.charged_amount IS DISTINCT FROM expected_charge
                   OR NEW.billing_reason IS DISTINCT FROM expected_reason
                   OR (
                        intent_maximum > 0
                        AND (
                            reservation_status NOT IN ('settled', 'released')
                            OR reservation_settled IS DISTINCT FROM expected_charge
                        )
                   )
                   OR (intent_maximum = 0 AND reservation_status IS NOT NULL) THEN
                    RAISE EXCEPTION 'inference usage % is inconsistent',
                        NEW.execution_reference_id;
                END IF;
                RETURN NULL;
            END;
            $$
            """
        )
    )
