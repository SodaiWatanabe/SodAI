"""credit ledger and inference billing

Revision ID: 20260713_0003
Revises: 20260713_0002
Create Date: 2026-07-13 23:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260713_0003"
down_revision: str | None = "20260713_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

IMMUTABLE_TABLES = (
    "credit_transactions",
    "credit_postings",
    "credit_lots",
    "credit_reservation_allocations",
    "credit_lot_consumptions",
)


def upgrade() -> None:
    op.create_table(
        "credit_accounts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=True),
        sa.Column("asset_code", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('user', 'issuance', 'reserve', 'revenue', 'expired')",
            name=op.f("ck_credit_accounts_kind"),
        ),
        sa.CheckConstraint(
            "kind = 'user' OR owner_user_id IS NULL",
            name=op.f("ck_credit_accounts_ownership"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["app.users.id"],
            name=op.f("fk_credit_accounts_owner_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_accounts")),
        schema="app",
    )
    op.create_index(
        op.f("ix_credit_accounts_owner_user_id"),
        "credit_accounts",
        ["owner_user_id"],
        unique=False,
        schema="app",
    )
    op.create_index(
        "uq_credit_accounts_user_asset",
        "credit_accounts",
        ["owner_user_id", "asset_code"],
        unique=True,
        schema="app",
        postgresql_where=sa.text("owner_user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_credit_accounts_system_asset",
        "credit_accounts",
        ["kind", "asset_code"],
        unique=True,
        schema="app",
        postgresql_where=sa.text("kind <> 'user'"),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO app.credit_accounts (id, kind, asset_code)
            VALUES
                ('00000000-0000-4000-9000-000000000001', 'issuance', 'sodai-credit'),
                ('00000000-0000-4000-9000-000000000002', 'reserve', 'sodai-credit'),
                ('00000000-0000-4000-9000-000000000003', 'revenue', 'sodai-credit'),
                ('00000000-0000-4000-9000-000000000004', 'expired', 'sodai-credit')
            """
        )
    )

    op.create_table(
        "credit_transactions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column("reference_type", sa.String(length=64), nullable=False),
        sa.Column("reference_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "effective_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('grant', 'reserve', 'settle', 'release', 'expire')",
            name=op.f("ck_credit_transactions_kind"),
        ),
        sa.CheckConstraint(
            "length(idempotency_key_hash) = 64",
            name=op.f("ck_credit_transactions_idempotency_hash"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_transactions")),
        sa.UniqueConstraint(
            "idempotency_key_hash",
            name=op.f("uq_credit_transactions_idempotency"),
        ),
        schema="app",
    )
    op.create_index(
        "ix_credit_transactions_created_id",
        "credit_transactions",
        ["created_at", "id"],
        unique=False,
        schema="app",
    )

    op.create_table(
        "credit_postings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("transaction_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount <> 0", name=op.f("ck_credit_postings_amount_nonzero")),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["app.credit_accounts.id"],
            name=op.f("fk_credit_postings_account_id_credit_accounts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["app.credit_transactions.id"],
            name=op.f("fk_credit_postings_transaction_id_credit_transactions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_postings")),
        sa.UniqueConstraint(
            "transaction_id",
            "account_id",
            name="uq_credit_postings_transaction_account",
        ),
        schema="app",
    )
    op.create_index(
        op.f("ix_credit_postings_account_id"),
        "credit_postings",
        ["account_id"],
        unique=False,
        schema="app",
    )
    op.create_index(
        op.f("ix_credit_postings_transaction_id"),
        "credit_postings",
        ["transaction_id"],
        unique=False,
        schema="app",
    )

    op.create_table(
        "credit_lots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_account_id", sa.UUID(), nullable=False),
        sa.Column("issuance_transaction_id", sa.UUID(), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("original_amount", sa.BigInteger(), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "expires_at IS NULL OR expires_at > issued_at",
            name=op.f("ck_credit_lots_expiration"),
        ),
        sa.CheckConstraint(
            "original_amount > 0", name=op.f("ck_credit_lots_original_amount_positive")
        ),
        sa.CheckConstraint(
            "source_kind IN ('admin', 'purchased', 'subscription', 'earned', 'promotional')",
            name=op.f("ck_credit_lots_source_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["issuance_transaction_id"],
            ["app.credit_transactions.id"],
            name=op.f("fk_credit_lots_issuance_transaction_id_credit_transactions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_account_id"],
            ["app.credit_accounts.id"],
            name=op.f("fk_credit_lots_owner_account_id_credit_accounts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_lots")),
        sa.UniqueConstraint(
            "issuance_transaction_id", name="uq_credit_lots_issuance_transaction"
        ),
        schema="app",
    )
    op.create_index(
        op.f("ix_credit_lots_owner_account_id"),
        "credit_lots",
        ["owner_account_id"],
        unique=False,
        schema="app",
    )
    op.create_index(
        "ix_credit_lots_spend_order",
        "credit_lots",
        ["owner_account_id", "expires_at", "issued_at"],
        unique=False,
        schema="app",
    )

    op.create_table(
        "inference_billing_intents",
        sa.Column("execution_reference_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("asset_code", sa.String(length=32), nullable=False),
        sa.Column("tariff_revision", sa.String(length=64), nullable=False),
        sa.Column("fixed_charge", sa.BigInteger(), nullable=False),
        sa.Column("input_token_rate", sa.BigInteger(), nullable=False),
        sa.Column("output_token_rate", sa.BigInteger(), nullable=False),
        sa.Column("maximum_charge", sa.BigInteger(), nullable=False),
        sa.Column("unmetered_charge", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "fixed_charge >= 0 AND input_token_rate >= 0 AND output_token_rate >= 0 "
            "AND maximum_charge >= fixed_charge "
            "AND unmetered_charge >= 0 AND unmetered_charge <= maximum_charge "
            "AND (maximum_charge = 0 OR unmetered_charge > 0)",
            name=op.f("ck_inference_billing_intents_tariff_amounts"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app.users.id"],
            name=op.f("fk_inference_billing_intents_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "execution_reference_id",
            name=op.f("pk_inference_billing_intents"),
        ),
        schema="app",
    )
    op.create_index(
        op.f("ix_inference_billing_intents_user_id"),
        "inference_billing_intents",
        ["user_id"],
        unique=False,
        schema="app",
    )

    op.create_table(
        "inference_credit_reservations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("execution_reference_id", sa.UUID(), nullable=False),
        sa.Column("owner_account_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reserved_amount", sa.BigInteger(), nullable=False),
        sa.Column("settled_amount", sa.BigInteger(), nullable=False),
        sa.Column("reserve_transaction_id", sa.UUID(), nullable=False),
        sa.Column("final_transaction_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "reserved_amount > 0",
            name=op.f("ck_inference_credit_reservations_reserved_amount_positive"),
        ),
        sa.CheckConstraint(
            "settled_amount >= 0 AND settled_amount <= reserved_amount",
            name=op.f("ck_inference_credit_reservations_settled_amount"),
        ),
        sa.CheckConstraint(
            "(status = 'held' AND final_transaction_id IS NULL AND finalized_at IS NULL) OR "
            "(status IN ('settled', 'released') AND final_transaction_id IS NOT NULL "
            "AND finalized_at IS NOT NULL)",
            name=op.f("ck_inference_credit_reservations_state"),
        ),
        sa.CheckConstraint(
            "status IN ('held', 'settled', 'released')",
            name=op.f("ck_inference_credit_reservations_status"),
        ),
        sa.ForeignKeyConstraint(
            ["final_transaction_id"],
            ["app.credit_transactions.id"],
            name=op.f(
                "fk_inference_credit_reservations_final_transaction_id_credit_transactions"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_account_id"],
            ["app.credit_accounts.id"],
            name=op.f(
                "fk_inference_credit_reservations_owner_account_id_credit_accounts"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reserve_transaction_id"],
            ["app.credit_transactions.id"],
            name=op.f(
                "fk_inference_credit_reservations_reserve_transaction_id_credit_transactions"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inference_credit_reservations")),
        sa.UniqueConstraint(
            "execution_reference_id",
            name="uq_inference_credit_reservations_execution_reference",
        ),
        sa.UniqueConstraint(
            "final_transaction_id", name="uq_inference_credit_reservations_final_tx"
        ),
        sa.UniqueConstraint(
            "reserve_transaction_id", name="uq_inference_credit_reservations_reserve_tx"
        ),
        schema="app",
    )
    op.create_index(
        op.f("ix_inference_credit_reservations_execution_reference_id"),
        "inference_credit_reservations",
        ["execution_reference_id"],
        unique=False,
        schema="app",
    )
    op.create_index(
        op.f("ix_inference_credit_reservations_owner_account_id"),
        "inference_credit_reservations",
        ["owner_account_id"],
        unique=False,
        schema="app",
    )

    op.create_table(
        "credit_reservation_allocations",
        sa.Column("reservation_id", sa.UUID(), nullable=False),
        sa.Column("lot_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "amount > 0", name=op.f("ck_credit_reservation_allocations_amount_positive")
        ),
        sa.ForeignKeyConstraint(
            ["lot_id"],
            ["app.credit_lots.id"],
            name=op.f("fk_credit_reservation_allocations_lot_id_credit_lots"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id"],
            ["app.inference_credit_reservations.id"],
            name=op.f(
                "fk_credit_reservation_allocations_reservation_id_inference_credit_reservations"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "reservation_id", "lot_id", name=op.f("pk_credit_reservation_allocations")
        ),
        schema="app",
    )
    op.create_index(
        "ix_credit_reservation_allocations_lot_id",
        "credit_reservation_allocations",
        ["lot_id"],
        unique=False,
        schema="app",
    )

    op.create_table(
        "credit_lot_consumptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("lot_id", sa.UUID(), nullable=False),
        sa.Column("transaction_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "amount > 0", name=op.f("ck_credit_lot_consumptions_amount_positive")
        ),
        sa.CheckConstraint(
            "kind IN ('settle', 'expire')",
            name=op.f("ck_credit_lot_consumptions_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["lot_id"],
            ["app.credit_lots.id"],
            name=op.f("fk_credit_lot_consumptions_lot_id_credit_lots"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["app.credit_transactions.id"],
            name=op.f(
                "fk_credit_lot_consumptions_transaction_id_credit_transactions"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_lot_consumptions")),
        sa.UniqueConstraint(
            "transaction_id",
            "lot_id",
            "kind",
            name="uq_credit_lot_consumptions_transaction_lot_kind",
        ),
        schema="app",
    )
    op.create_index(
        op.f("ix_credit_lot_consumptions_lot_id"),
        "credit_lot_consumptions",
        ["lot_id"],
        unique=False,
        schema="app",
    )

    op.create_table(
        "inference_usage_records",
        sa.Column("execution_reference_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("input_tokens", sa.BigInteger(), nullable=True),
        sa.Column("output_tokens", sa.BigInteger(), nullable=True),
        sa.Column("tariff_revision", sa.String(length=64), nullable=False),
        sa.Column("charged_amount", sa.BigInteger(), nullable=False),
        sa.Column("billing_reason", sa.String(length=32), nullable=False),
        sa.Column(
            "finalized_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "billing_reason IN ('free', 'completed', 'failed', 'unmetered')",
            name=op.f("ck_inference_usage_records_billing_reason"),
        ),
        sa.CheckConstraint(
            "charged_amount >= 0", name=op.f("ck_inference_usage_records_charged_amount")
        ),
        sa.CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name=op.f("ck_inference_usage_records_input_tokens"),
        ),
        sa.CheckConstraint(
            "outcome IN ('completed', 'failed')",
            name=op.f("ck_inference_usage_records_outcome"),
        ),
        sa.CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name=op.f("ck_inference_usage_records_output_tokens"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app.users.id"],
            name=op.f("fk_inference_usage_records_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "execution_reference_id",
            name=op.f("pk_inference_usage_records"),
        ),
        schema="app",
    )
    op.create_index(
        op.f("ix_inference_usage_records_user_id"),
        "inference_usage_records",
        ["user_id"],
        unique=False,
        schema="app",
    )

    # Active work from the immediately preceding schema is free. Backfilling its
    # intent keeps completion and timeout projection atomic across this migration.
    op.execute(
        sa.text(
            """
            INSERT INTO app.inference_billing_intents (
                execution_reference_id,
                user_id,
                asset_code,
                tariff_revision,
                fixed_charge,
                input_token_rate,
                output_token_rate,
                maximum_charge,
                unmetered_charge
            )
            SELECT
                execution.id,
                requester.owner_user_id,
                'sodai-credit',
                'free-v1',
                0,
                0,
                0,
                0,
                0
            FROM app.executions AS execution
            JOIN app.response_requests AS request
              ON request.id = execution.response_request_id
            JOIN app.actors AS requester
              ON requester.id = request.requester_actor_id
            WHERE execution.status IN ('queued', 'running')
            """
        )
    )

    _create_ledger_guards()


def downgrade() -> None:
    _drop_ledger_guards()
    op.drop_index(
        op.f("ix_inference_usage_records_user_id"),
        table_name="inference_usage_records",
        schema="app",
    )
    op.drop_table("inference_usage_records", schema="app")
    op.drop_index(
        op.f("ix_credit_lot_consumptions_lot_id"),
        table_name="credit_lot_consumptions",
        schema="app",
    )
    op.drop_table("credit_lot_consumptions", schema="app")
    op.execute(
        "DROP INDEX IF EXISTS app.ix_credit_reservation_allocations_lot_id"
    )
    op.drop_table("credit_reservation_allocations", schema="app")
    op.drop_index(
        op.f("ix_inference_credit_reservations_owner_account_id"),
        table_name="inference_credit_reservations",
        schema="app",
    )
    op.drop_index(
        op.f("ix_inference_credit_reservations_execution_reference_id"),
        table_name="inference_credit_reservations",
        schema="app",
    )
    op.drop_table("inference_credit_reservations", schema="app")
    op.drop_index(
        op.f("ix_inference_billing_intents_user_id"),
        table_name="inference_billing_intents",
        schema="app",
    )
    op.drop_table("inference_billing_intents", schema="app")
    op.drop_index(
        "ix_credit_lots_spend_order", table_name="credit_lots", schema="app"
    )
    op.drop_index(
        op.f("ix_credit_lots_owner_account_id"),
        table_name="credit_lots",
        schema="app",
    )
    op.drop_table("credit_lots", schema="app")
    op.drop_index(
        op.f("ix_credit_postings_transaction_id"),
        table_name="credit_postings",
        schema="app",
    )
    op.drop_index(
        op.f("ix_credit_postings_account_id"),
        table_name="credit_postings",
        schema="app",
    )
    op.drop_table("credit_postings", schema="app")
    op.drop_index(
        "ix_credit_transactions_created_id",
        table_name="credit_transactions",
        schema="app",
    )
    op.drop_table("credit_transactions", schema="app")
    op.drop_index(
        "uq_credit_accounts_user_asset", table_name="credit_accounts", schema="app"
    )
    op.drop_index(
        "uq_credit_accounts_system_asset", table_name="credit_accounts", schema="app"
    )
    op.drop_index(
        op.f("ix_credit_accounts_owner_user_id"),
        table_name="credit_accounts",
        schema="app",
    )
    op.drop_table("credit_accounts", schema="app")


def _create_ledger_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION app.reject_immutable_credit_record()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'credit ledger records are immutable';
        END;
        $$
        """
    )
    for table in IMMUTABLE_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER {table}_immutable
            BEFORE UPDATE OR DELETE ON app.{table}
            FOR EACH ROW EXECUTE FUNCTION app.reject_immutable_credit_record()
            """
        )

    op.execute(
        """
        CREATE FUNCTION app.assert_credit_grant_consistent()
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
            lot_issued_at timestamptz;
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

            SELECT owner_account_id, original_amount, issued_at
            INTO lot_owner_id, lot_amount, lot_issued_at
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
               OR transaction_reference_type IS DISTINCT FROM 'user_credit_grant'
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
    for table, event in (
        ("credit_transactions", "INSERT"),
        ("credit_postings", "INSERT"),
        ("credit_lots", "INSERT"),
    ):
        op.execute(
            f"""
            CREATE CONSTRAINT TRIGGER {table}_grant_consistent
            AFTER {event} ON app.{table}
            DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION app.assert_credit_grant_consistent()
            """
        )

    op.execute(
        """
        CREATE FUNCTION app.assert_credit_expiration_consistent()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            target_transaction_id uuid;
            transaction_kind text;
            transaction_reference_type text;
            transaction_reference_id uuid;
            lot_owner_id uuid;
            consumed bigint;
            unexpected_consumptions bigint;
            owner_posting bigint;
            expired_posting bigint;
            unexpected_postings bigint;
        BEGIN
            IF TG_TABLE_NAME = 'credit_transactions' THEN
                target_transaction_id := NEW.id;
            ELSE
                target_transaction_id := NEW.transaction_id;
            END IF;

            SELECT kind, reference_type, reference_id
            INTO transaction_kind, transaction_reference_type,
                 transaction_reference_id
            FROM app.credit_transactions
            WHERE id = target_transaction_id;

            IF transaction_kind IS DISTINCT FROM 'expire' THEN
                IF TG_TABLE_NAME = 'credit_lot_consumptions'
                   AND transaction_kind NOT IN ('settle', 'release') THEN
                    RAISE EXCEPTION
                        'credit lot consumptions require an expiration or settlement transaction';
                END IF;
                RETURN NULL;
            END IF;

            SELECT owner_account_id INTO lot_owner_id
            FROM app.credit_lots
            WHERE id = transaction_reference_id
              AND expires_at <= (
                  SELECT effective_at
                  FROM app.credit_transactions
                  WHERE id = target_transaction_id
              );

            SELECT
                COALESCE(sum(amount), 0),
                count(*) FILTER (
                    WHERE kind <> 'expire' OR lot_id <> transaction_reference_id
                )
            INTO consumed, unexpected_consumptions
            FROM app.credit_lot_consumptions
            WHERE transaction_id = target_transaction_id;

            SELECT
                COALESCE(sum(amount) FILTER (WHERE account_id = lot_owner_id), 0),
                COALESCE(sum(amount) FILTER (
                    WHERE account_id = '00000000-0000-4000-9000-000000000004'
                ), 0),
                count(*) FILTER (
                    WHERE account_id NOT IN (
                        lot_owner_id,
                        '00000000-0000-4000-9000-000000000004'
                    )
                )
            INTO owner_posting, expired_posting, unexpected_postings
            FROM app.credit_postings
            WHERE transaction_id = target_transaction_id;

            IF transaction_reference_type IS DISTINCT FROM 'credit_lot'
               OR lot_owner_id IS NULL
               OR consumed <= 0
               OR unexpected_consumptions IS DISTINCT FROM 0
               OR owner_posting IS DISTINCT FROM -consumed
               OR expired_posting IS DISTINCT FROM consumed
               OR unexpected_postings IS DISTINCT FROM 0 THEN
                RAISE EXCEPTION 'credit expiration % is inconsistent',
                    target_transaction_id;
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )
    for table in (
        "credit_transactions",
        "credit_postings",
        "credit_lot_consumptions",
    ):
        op.execute(
            f"""
            CREATE CONSTRAINT TRIGGER {table}_expiration_consistent
            AFTER INSERT ON app.{table}
            DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION app.assert_credit_expiration_consistent()
            """
        )

    op.execute(
        """
        CREATE FUNCTION app.protect_credit_account()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'UPDATE'
               AND OLD.kind = 'user'
               AND OLD.owner_user_id IS NOT NULL
               AND NEW.owner_user_id IS NULL
               AND NEW.id = OLD.id
               AND NEW.kind = OLD.kind
               AND NEW.asset_code = OLD.asset_code
               AND NEW.created_at = OLD.created_at THEN
                IF EXISTS (
                    SELECT 1
                    FROM app.inference_credit_reservations
                    WHERE owner_account_id = OLD.id AND status = 'held'
                ) THEN
                    RAISE EXCEPTION 'held credit reservations must be finalized first';
                END IF;
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'credit accounts cannot be reassigned or deleted';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER credit_accounts_protected
        BEFORE UPDATE OR DELETE ON app.credit_accounts
        FOR EACH ROW EXECUTE FUNCTION app.protect_credit_account()
        """
    )

    op.execute(
        """
        CREATE FUNCTION app.protect_credit_attribution()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'UPDATE'
               AND OLD.user_id IS NOT NULL
               AND NEW.user_id IS NULL
               AND (to_jsonb(NEW) - 'user_id') = (to_jsonb(OLD) - 'user_id') THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'credit billing records are immutable';
        END;
        $$
        """
    )
    for table in ("inference_billing_intents", "inference_usage_records"):
        op.execute(
            f"""
            CREATE TRIGGER {table}_protected
            BEFORE UPDATE OR DELETE ON app.{table}
            FOR EACH ROW EXECUTE FUNCTION app.protect_credit_attribution()
            """
        )

    op.execute(
        """
        CREATE FUNCTION app.protect_billable_execution_delete()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
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
                RAISE EXCEPTION 'billable executions must be finalized before deletion';
            END IF;
            RETURN OLD;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER executions_billing_finalized
        BEFORE DELETE ON app.executions
        FOR EACH ROW EXECUTE FUNCTION app.protect_billable_execution_delete()
        """
    )

    op.execute(
        """
        CREATE FUNCTION app.assert_billing_registration_consistent()
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
                        OR reservation_owner_user_id IS DISTINCT FROM intent_user_id
                        OR reservation_asset_code IS DISTINCT FROM intent_asset_code
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
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER inference_billing_intents_registration
        AFTER INSERT ON app.inference_billing_intents
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION app.assert_billing_registration_consistent()
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER inference_credit_reservations_registration
        AFTER INSERT ON app.inference_credit_reservations
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION app.assert_billing_registration_consistent()
        """
    )

    op.execute(
        """
        CREATE FUNCTION app.assert_inference_usage_consistent()
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
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER inference_usage_records_consistent
        AFTER INSERT ON app.inference_usage_records
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION app.assert_inference_usage_consistent()
        """
    )

    op.execute(
        """
        CREATE FUNCTION app.protect_credit_reservation_lifecycle()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'UPDATE'
               AND OLD.status = 'held'
               AND NEW.status IN ('settled', 'released')
               AND NEW.id = OLD.id
               AND NEW.execution_reference_id = OLD.execution_reference_id
               AND NEW.owner_account_id = OLD.owner_account_id
               AND NEW.reserved_amount = OLD.reserved_amount
               AND NEW.reserve_transaction_id = OLD.reserve_transaction_id
               AND NEW.created_at = OLD.created_at THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'credit reservations only allow one terminal transition';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER inference_credit_reservations_lifecycle
        BEFORE UPDATE OR DELETE ON app.inference_credit_reservations
        FOR EACH ROW EXECUTE FUNCTION app.protect_credit_reservation_lifecycle()
        """
    )

    op.execute(
        """
        CREATE FUNCTION app.assert_credit_allocation_open()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            reservation_status text;
        BEGIN
            SELECT status INTO reservation_status
            FROM app.inference_credit_reservations
            WHERE id = NEW.reservation_id;

            IF reservation_status IS DISTINCT FROM 'held' THEN
                RAISE EXCEPTION 'credit allocations require a held reservation';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER credit_reservation_allocations_open
        BEFORE INSERT ON app.credit_reservation_allocations
        FOR EACH ROW EXECUTE FUNCTION app.assert_credit_allocation_open()
        """
    )

    op.execute(
        """
        CREATE FUNCTION app.assert_credit_reservation_allocated()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            target_reservation_id uuid;
            target_transaction_id uuid;
            observed_transaction_kind text;
            reserved bigint;
            allocated bigint;
            reserve_kind text;
            reserve_reference_type text;
            reserve_reference_id uuid;
            reserve_effective_at timestamptz;
            reservation_created_at timestamptz;
            owner_posting bigint;
            reserve_posting bigint;
            unexpected_postings bigint;
            mismatched_lots bigint;
            invalid_fefo_allocations bigint;
        BEGIN
            IF TG_TABLE_NAME = 'inference_credit_reservations' THEN
                target_reservation_id := NEW.id;
            ELSIF TG_TABLE_NAME = 'credit_reservation_allocations' THEN
                target_reservation_id := NEW.reservation_id;
            ELSE
                IF TG_TABLE_NAME = 'credit_transactions' THEN
                    target_transaction_id := NEW.id;
                ELSE
                    target_transaction_id := NEW.transaction_id;
                END IF;
                SELECT kind INTO observed_transaction_kind
                FROM app.credit_transactions
                WHERE id = target_transaction_id;
                IF observed_transaction_kind IS DISTINCT FROM 'reserve' THEN
                    RETURN NULL;
                END IF;
                SELECT id INTO target_reservation_id
                FROM app.inference_credit_reservations
                WHERE reserve_transaction_id = target_transaction_id;
            END IF;

            SELECT reserved_amount INTO reserved
            FROM app.inference_credit_reservations
            WHERE id = target_reservation_id;

            SELECT COALESCE(sum(amount), 0) INTO allocated
            FROM app.credit_reservation_allocations
            WHERE reservation_id = target_reservation_id;

            SELECT count(*) INTO mismatched_lots
            FROM app.credit_reservation_allocations AS allocation
            JOIN app.credit_lots AS lot ON lot.id = allocation.lot_id
            JOIN app.inference_credit_reservations AS reservation
              ON reservation.id = allocation.reservation_id
            WHERE reservation.id = target_reservation_id
              AND (
                  lot.owner_account_id <> reservation.owner_account_id
                  OR lot.issued_at > reservation.created_at
                  OR lot.expires_at <= reservation.created_at
              );

            WITH target AS (
                SELECT id, owner_account_id, reserved_amount, created_at
                FROM app.inference_credit_reservations
                WHERE id = target_reservation_id
            ),
            lot_capacity AS (
                SELECT
                    lot.id,
                    lot.expires_at,
                    lot.issued_at,
                    GREATEST(
                        lot.original_amount
                        - COALESCE((
                            SELECT sum(consumption.amount)
                            FROM app.credit_lot_consumptions AS consumption
                            JOIN app.credit_transactions AS transaction
                              ON transaction.id = consumption.transaction_id
                            WHERE consumption.lot_id = lot.id
                              AND transaction.effective_at <= target.created_at
                        ), 0)
                        - COALESCE((
                            SELECT sum(other_allocation.amount)
                            FROM app.credit_reservation_allocations AS other_allocation
                            JOIN app.inference_credit_reservations AS other_reservation
                              ON other_reservation.id = other_allocation.reservation_id
                            WHERE other_allocation.lot_id = lot.id
                              AND other_reservation.id <> target.id
                              AND other_reservation.created_at <= target.created_at
                              AND (
                                  other_reservation.finalized_at IS NULL
                                  OR other_reservation.finalized_at > target.created_at
                              )
                        ), 0),
                        0
                    ) AS available,
                    COALESCE(allocation.amount, 0) AS actual,
                    target.reserved_amount
                FROM target
                JOIN app.credit_lots AS lot
                  ON lot.owner_account_id = target.owner_account_id
                LEFT JOIN app.credit_reservation_allocations AS allocation
                  ON allocation.reservation_id = target.id
                 AND allocation.lot_id = lot.id
                WHERE lot.issued_at <= target.created_at
                  AND (lot.expires_at IS NULL OR lot.expires_at > target.created_at)
            ),
            expected AS (
                SELECT
                    actual,
                    GREATEST(
                        LEAST(
                            reserved_amount
                            - COALESCE(
                                sum(available) OVER (
                                    ORDER BY expires_at ASC NULLS LAST,
                                             issued_at,
                                             id
                                    ROWS BETWEEN UNBOUNDED PRECEDING
                                             AND 1 PRECEDING
                                ),
                                0
                            ),
                            available
                        ),
                        0
                    ) AS amount
                FROM lot_capacity
            )
            SELECT count(*) INTO invalid_fefo_allocations
            FROM expected
            WHERE actual IS DISTINCT FROM amount;

            SELECT transaction.kind, transaction.reference_type,
                   transaction.reference_id, transaction.effective_at,
                   reservation.created_at
            INTO reserve_kind, reserve_reference_type, reserve_reference_id,
                 reserve_effective_at, reservation_created_at
            FROM app.inference_credit_reservations AS reservation
            JOIN app.credit_transactions AS transaction
              ON transaction.id = reservation.reserve_transaction_id
            WHERE reservation.id = target_reservation_id;

            SELECT
                COALESCE(sum(posting.amount) FILTER (
                    WHERE posting.account_id = reservation.owner_account_id
                ), 0),
                COALESCE(sum(posting.amount) FILTER (
                    WHERE posting.account_id = '00000000-0000-4000-9000-000000000002'
                ), 0),
                count(*) FILTER (
                    WHERE posting.account_id NOT IN (
                        reservation.owner_account_id,
                        '00000000-0000-4000-9000-000000000002'
                    )
                )
            INTO owner_posting, reserve_posting, unexpected_postings
            FROM app.inference_credit_reservations AS reservation
            JOIN app.credit_postings AS posting
              ON posting.transaction_id = reservation.reserve_transaction_id
            WHERE reservation.id = target_reservation_id
            GROUP BY reservation.owner_account_id;

            IF reserved IS NULL
               OR allocated <> reserved
               OR mismatched_lots <> 0
               OR invalid_fefo_allocations <> 0
               OR reserve_kind IS DISTINCT FROM 'reserve'
               OR reserve_reference_type IS DISTINCT FROM 'inference_execution'
               OR reserve_reference_id IS DISTINCT FROM (
                    SELECT execution_reference_id
                    FROM app.inference_credit_reservations
                    WHERE id = target_reservation_id
               )
               OR reservation_created_at IS DISTINCT FROM reserve_effective_at
               OR owner_posting IS DISTINCT FROM -reserved
               OR reserve_posting IS DISTINCT FROM reserved
               OR unexpected_postings IS DISTINCT FROM 0 THEN
                RAISE EXCEPTION 'credit reservation % allocations do not match',
                    target_reservation_id;
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER inference_credit_reservations_allocated
        AFTER INSERT ON app.inference_credit_reservations
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION app.assert_credit_reservation_allocated()
        """
    )
    for table in ("credit_transactions", "credit_postings"):
        op.execute(
            f"""
            CREATE CONSTRAINT TRIGGER {table}_reservation_allocated
            AFTER INSERT ON app.{table}
            DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION app.assert_credit_reservation_allocated()
            """
        )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER credit_reservation_allocations_complete
        AFTER INSERT ON app.credit_reservation_allocations
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION app.assert_credit_reservation_allocated()
        """
    )

    op.execute(
        """
        CREATE FUNCTION app.assert_credit_lot_conserved()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            original bigint;
            consumed bigint;
            held bigint;
        BEGIN
            SELECT original_amount INTO original
            FROM app.credit_lots
            WHERE id = NEW.lot_id
            FOR UPDATE;

            SELECT COALESCE(sum(amount), 0) INTO consumed
            FROM app.credit_lot_consumptions
            WHERE lot_id = NEW.lot_id;

            SELECT COALESCE(sum(allocation.amount), 0) INTO held
            FROM app.credit_reservation_allocations AS allocation
            JOIN app.inference_credit_reservations AS reservation
              ON reservation.id = allocation.reservation_id
            WHERE allocation.lot_id = NEW.lot_id
              AND reservation.status = 'held';

            IF original IS NULL OR consumed + held > original THEN
                RAISE EXCEPTION 'credit lot % is over-allocated', NEW.lot_id;
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER credit_reservation_allocations_conserved
        AFTER INSERT ON app.credit_reservation_allocations
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION app.assert_credit_lot_conserved()
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER credit_lot_consumptions_conserved
        AFTER INSERT ON app.credit_lot_consumptions
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION app.assert_credit_lot_conserved()
        """
    )

    op.execute(
        """
        CREATE FUNCTION app.assert_credit_reservation_finalized()
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
            reserve_posting bigint;
            revenue_posting bigint;
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

            SELECT
                COALESCE(sum(amount) FILTER (
                    WHERE account_id = '00000000-0000-4000-9000-000000000002'
                ), 0),
                COALESCE(sum(amount) FILTER (
                    WHERE account_id = '00000000-0000-4000-9000-000000000003'
                ), 0),
                COALESCE(sum(amount) FILTER (
                    WHERE account_id = reservation_row.owner_account_id
                ), 0),
                COALESCE(sum(amount) FILTER (
                    WHERE account_id = '00000000-0000-4000-9000-000000000004'
                ), 0),
                count(*) FILTER (
                    WHERE account_id NOT IN (
                        reservation_row.owner_account_id,
                        '00000000-0000-4000-9000-000000000002',
                        '00000000-0000-4000-9000-000000000003',
                        '00000000-0000-4000-9000-000000000004'
                    )
                )
            INTO reserve_posting, revenue_posting, owner_posting,
                 expired_posting, unexpected_postings
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
                WHERE consumption.transaction_id = reservation_row.final_transaction_id
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
                  ON consumption.transaction_id = reservation_row.final_transaction_id
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
                  ON consumption.transaction_id = reservation_row.final_transaction_id
                 AND consumption.lot_id = allocation.lot_id
                WHERE allocation.reservation_id = reservation_row.id
                GROUP BY allocation.lot_id, allocation.amount, lot.expires_at,
                         lot.issued_at, lot.id
            ) AS fefo
            WHERE actual_settled IS DISTINCT FROM expected_settled;

            IF transaction_kind IS DISTINCT FROM (
                    CASE
                        WHEN reservation_row.settled_amount > 0 THEN 'settle'
                        ELSE 'release'
                    END
               )
               OR transaction_reference_type IS DISTINCT FROM 'inference_execution'
               OR transaction_reference_id IS DISTINCT FROM
                    reservation_row.execution_reference_id
               OR reservation_row.finalized_at IS DISTINCT FROM
                    transaction_effective_at
               OR reservation_row.status IS DISTINCT FROM (
                    CASE
                        WHEN reservation_row.settled_amount > 0 THEN 'settled'
                        ELSE 'released'
                    END
               )
               OR reserve_posting <> -reservation_row.reserved_amount
               OR revenue_posting <> reservation_row.settled_amount
               OR settled_consumption <> reservation_row.settled_amount
               OR expired_posting <> expired_consumption
               OR owner_posting + expired_posting + reservation_row.settled_amount
                    <> reservation_row.reserved_amount
               OR unexpected_postings <> 0
               OR mismatched_consumptions <> 0
               OR invalid_allocation_finalizations <> 0
               OR invalid_fefo_consumptions <> 0 THEN
                RAISE EXCEPTION 'credit reservation % finalization is inconsistent',
                    target_reservation_id;
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER inference_credit_reservations_finalized
        AFTER UPDATE ON app.inference_credit_reservations
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION app.assert_credit_reservation_finalized()
        """
    )
    for table in (
        "credit_transactions",
        "credit_postings",
        "credit_lot_consumptions",
    ):
        op.execute(
            f"""
            CREATE CONSTRAINT TRIGGER {table}_reservation_finalized
            AFTER INSERT ON app.{table}
            DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION app.assert_credit_reservation_finalized()
            """
        )

    op.execute(
        """
        CREATE FUNCTION app.assert_credit_transaction_balanced()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            target_transaction_id uuid;
            posting_count bigint;
            posting_total bigint;
        BEGIN
            IF TG_TABLE_NAME = 'credit_transactions' THEN
                target_transaction_id := NEW.id;
            ELSE
                target_transaction_id := NEW.transaction_id;
            END IF;

            SELECT count(*), COALESCE(sum(amount), 0)
            INTO posting_count, posting_total
            FROM app.credit_postings
            WHERE transaction_id = target_transaction_id;

            IF posting_count < 2 OR posting_total <> 0 THEN
                RAISE EXCEPTION 'credit transaction % is not balanced', target_transaction_id;
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER credit_transactions_balanced
        AFTER INSERT ON app.credit_transactions
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION app.assert_credit_transaction_balanced()
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER credit_postings_balanced
        AFTER INSERT ON app.credit_postings
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION app.assert_credit_transaction_balanced()
        """
    )

    op.execute(
        """
        CREATE FUNCTION app.assert_credit_account_nonnegative()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            account_kind text;
            account_balance bigint;
        BEGIN
            SELECT kind INTO account_kind
            FROM app.credit_accounts
            WHERE id = NEW.account_id
            FOR UPDATE;

            IF account_kind <> 'issuance' THEN
                SELECT COALESCE(sum(amount), 0)
                INTO account_balance
                FROM app.credit_postings
                WHERE account_id = NEW.account_id;

                IF account_balance < 0 THEN
                    RAISE EXCEPTION 'credit account % cannot be overdrawn', NEW.account_id;
                END IF;
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER credit_accounts_nonnegative
        AFTER INSERT ON app.credit_postings
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION app.assert_credit_account_nonnegative()
        """
    )


def _drop_ledger_guards() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS inference_usage_records_consistent "
        "ON app.inference_usage_records"
    )
    op.execute("DROP FUNCTION IF EXISTS app.assert_inference_usage_consistent()")
    op.execute(
        "DROP TRIGGER IF EXISTS inference_credit_reservations_registration "
        "ON app.inference_credit_reservations"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS inference_billing_intents_registration "
        "ON app.inference_billing_intents"
    )
    op.execute("DROP FUNCTION IF EXISTS app.assert_billing_registration_consistent()")
    op.execute("DROP TRIGGER IF EXISTS executions_billing_finalized ON app.executions")
    op.execute("DROP FUNCTION IF EXISTS app.protect_billable_execution_delete()")
    for table in ("inference_usage_records", "inference_billing_intents"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_protected ON app.{table}")
    op.execute("DROP FUNCTION IF EXISTS app.protect_credit_attribution()")
    op.execute(
        "DROP TRIGGER IF EXISTS inference_credit_reservations_finalized "
        "ON app.inference_credit_reservations"
    )
    for table in (
        "credit_lot_consumptions",
        "credit_postings",
        "credit_transactions",
    ):
        op.execute(
            f"DROP TRIGGER IF EXISTS {table}_reservation_finalized ON app.{table}"
        )
    op.execute("DROP FUNCTION IF EXISTS app.assert_credit_reservation_finalized()")
    op.execute(
        "DROP TRIGGER IF EXISTS credit_lot_consumptions_conserved "
        "ON app.credit_lot_consumptions"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS credit_reservation_allocations_conserved "
        "ON app.credit_reservation_allocations"
    )
    op.execute("DROP FUNCTION IF EXISTS app.assert_credit_lot_conserved()")
    op.execute(
        "DROP TRIGGER IF EXISTS credit_reservation_allocations_complete "
        "ON app.credit_reservation_allocations"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS inference_credit_reservations_allocated "
        "ON app.inference_credit_reservations"
    )
    for table in ("credit_postings", "credit_transactions"):
        op.execute(
            f"DROP TRIGGER IF EXISTS {table}_reservation_allocated ON app.{table}"
        )
    op.execute("DROP FUNCTION IF EXISTS app.assert_credit_reservation_allocated()")
    op.execute(
        "DROP TRIGGER IF EXISTS credit_reservation_allocations_open "
        "ON app.credit_reservation_allocations"
    )
    op.execute("DROP FUNCTION IF EXISTS app.assert_credit_allocation_open()")
    op.execute(
        "DROP TRIGGER IF EXISTS inference_credit_reservations_lifecycle "
        "ON app.inference_credit_reservations"
    )
    op.execute("DROP FUNCTION IF EXISTS app.protect_credit_reservation_lifecycle()")
    op.execute(
        "DROP TRIGGER IF EXISTS credit_accounts_nonnegative ON app.credit_postings"
    )
    op.execute("DROP FUNCTION IF EXISTS app.assert_credit_account_nonnegative()")
    op.execute("DROP TRIGGER IF EXISTS credit_postings_balanced ON app.credit_postings")
    op.execute(
        "DROP TRIGGER IF EXISTS credit_transactions_balanced ON app.credit_transactions"
    )
    op.execute("DROP FUNCTION IF EXISTS app.assert_credit_transaction_balanced()")
    op.execute("DROP TRIGGER IF EXISTS credit_accounts_protected ON app.credit_accounts")
    op.execute("DROP FUNCTION IF EXISTS app.protect_credit_account()")
    for table in (
        "credit_lot_consumptions",
        "credit_postings",
        "credit_transactions",
    ):
        op.execute(
            f"DROP TRIGGER IF EXISTS {table}_expiration_consistent ON app.{table}"
        )
    op.execute("DROP FUNCTION IF EXISTS app.assert_credit_expiration_consistent()")
    for table in ("credit_lots", "credit_postings", "credit_transactions"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_grant_consistent ON app.{table}")
    op.execute("DROP FUNCTION IF EXISTS app.assert_credit_grant_consistent()")
    for table in IMMUTABLE_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_immutable ON app.{table}")
    op.execute("DROP FUNCTION IF EXISTS app.reject_immutable_credit_record()")
