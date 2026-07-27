import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy import func as sql_func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import APPLICATION_SCHEMA, Base


class CreditAccountModel(Base):
    __tablename__ = "credit_accounts"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('user', 'issuance', 'reserve', 'revenue', 'expired')",
            name="kind",
        ),
        CheckConstraint(
            "kind = 'user' OR owner_user_id IS NULL",
            name="ownership",
        ),
        Index(
            "uq_credit_accounts_user_asset",
            "owner_user_id",
            "asset_code",
            unique=True,
            postgresql_where=text("owner_user_id IS NOT NULL"),
        ),
        Index(
            "uq_credit_accounts_system_asset",
            "kind",
            "asset_code",
            unique=True,
            postgresql_where=text("kind <> 'user'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.users.id", ondelete="SET NULL"),
        index=True,
    )
    asset_code: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )


class CreditTransactionModel(Base):
    __tablename__ = "credit_transactions"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('grant', 'reserve', 'settle', 'release', 'expire')",
            name="kind",
        ),
        CheckConstraint("length(idempotency_key_hash) = 64", name="idempotency_hash"),
        UniqueConstraint("idempotency_key_hash", name="uq_credit_transactions_idempotency"),
        Index("ix_credit_transactions_created_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_type: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )

    postings: Mapped[list["CreditPostingModel"]] = relationship(
        back_populates="transaction"
    )


class CreditPostingModel(Base):
    __tablename__ = "credit_postings"
    __table_args__ = (
        CheckConstraint("amount <> 0", name="amount_nonzero"),
        UniqueConstraint(
            "transaction_id", "account_id", name="uq_credit_postings_transaction_account"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.credit_transactions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.credit_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )

    transaction: Mapped[CreditTransactionModel] = relationship(back_populates="postings")


class CreditLotModel(Base):
    __tablename__ = "credit_lots"
    __table_args__ = (
        CheckConstraint("original_amount > 0", name="original_amount_positive"),
        CheckConstraint(
            "source_kind IN ('admin', 'purchased', 'subscription', 'earned', 'promotional')",
            name="source_kind",
        ),
        CheckConstraint("expires_at IS NULL OR expires_at > issued_at", name="expiration"),
        UniqueConstraint(
            "issuance_transaction_id", name="uq_credit_lots_issuance_transaction"
        ),
        Index("ix_credit_lots_spend_order", "owner_account_id", "expires_at", "issued_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.credit_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    issuance_transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.credit_transactions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    original_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InferenceCreditReservationModel(Base):
    __tablename__ = "inference_credit_reservations"
    __table_args__ = (
        CheckConstraint("status IN ('held', 'settled', 'released')", name="status"),
        CheckConstraint("reserved_amount > 0", name="reserved_amount_positive"),
        CheckConstraint(
            "settled_amount >= 0 AND settled_amount <= reserved_amount",
            name="settled_amount",
        ),
        CheckConstraint(
            "(status = 'held' AND final_transaction_id IS NULL AND finalized_at IS NULL) OR "
            "(status IN ('settled', 'released') AND final_transaction_id IS NOT NULL "
            "AND finalized_at IS NOT NULL)",
            name="state",
        ),
        UniqueConstraint(
            "execution_reference_id",
            name="uq_inference_credit_reservations_execution_reference",
        ),
        UniqueConstraint(
            "reserve_transaction_id", name="uq_inference_credit_reservations_reserve_tx"
        ),
        UniqueConstraint(
            "final_transaction_id", name="uq_inference_credit_reservations_final_tx"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Financial records outlive operational conversation data. This immutable
    # reference intentionally has no FK that could erase or block that history.
    execution_reference_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    owner_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.credit_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reserved_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    settled_amount: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    reserve_transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.credit_transactions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    final_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.credit_transactions.id", ondelete="RESTRICT"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CreditReservationAllocationModel(Base):
    __tablename__ = "credit_reservation_allocations"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_credit_reservation_allocations_lot_id", "lot_id"),
    )

    reservation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{APPLICATION_SCHEMA}.inference_credit_reservations.id", ondelete="RESTRICT"
        ),
        primary_key=True,
    )
    lot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.credit_lots.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)


class CreditLotConsumptionModel(Base):
    __tablename__ = "credit_lot_consumptions"
    __table_args__ = (
        CheckConstraint("kind IN ('settle', 'expire')", name="kind"),
        CheckConstraint("amount > 0", name="amount_positive"),
        UniqueConstraint(
            "transaction_id",
            "lot_id",
            "kind",
            name="uq_credit_lot_consumptions_transaction_lot_kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.credit_lots.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.credit_transactions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)


class InferenceBillingIntentModel(Base):
    __tablename__ = "inference_billing_intents"
    __table_args__ = (
        CheckConstraint(
            "fixed_charge >= 0 AND input_token_rate >= 0 AND output_token_rate >= 0 "
            "AND maximum_charge >= fixed_charge "
            "AND unmetered_charge >= 0 AND unmetered_charge <= maximum_charge "
            "AND (maximum_charge = 0 OR unmetered_charge > 0)",
            name="tariff_amounts",
        ),
    )

    execution_reference_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.users.id", ondelete="SET NULL"),
        index=True,
    )
    asset_code: Mapped[str] = mapped_column(String(32), nullable=False)
    tariff_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    fixed_charge: Mapped[int] = mapped_column(BigInteger, nullable=False)
    input_token_rate: Mapped[int] = mapped_column(BigInteger, nullable=False)
    output_token_rate: Mapped[int] = mapped_column(BigInteger, nullable=False)
    maximum_charge: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unmetered_charge: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )


class InferenceUsageRecordModel(Base):
    __tablename__ = "inference_usage_records"
    __table_args__ = (
        CheckConstraint("outcome IN ('completed', 'failed', 'cancelled')", name="outcome"),
        CheckConstraint(
            "billing_reason IN ('free', 'completed', 'failed', 'cancelled', 'unmetered')",
            name="billing_reason",
        ),
        CheckConstraint("input_tokens IS NULL OR input_tokens >= 0", name="input_tokens"),
        CheckConstraint("output_tokens IS NULL OR output_tokens >= 0", name="output_tokens"),
        CheckConstraint("charged_amount >= 0", name="charged_amount"),
    )

    execution_reference_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{APPLICATION_SCHEMA}.users.id", ondelete="SET NULL"),
        index=True,
    )
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(BigInteger)
    output_tokens: Mapped[int | None] = mapped_column(BigInteger)
    tariff_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    charged_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    billing_reason: Mapped[str] = mapped_column(String(32), nullable=False)
    finalized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_func.now()
    )
