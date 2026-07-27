from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import UUID

CREDIT_ASSET_CODE = "sodai-credit"
CREDIT_SCALE = 1_000_000
FREE_CREDIT_ALLOWANCE_DURATION = timedelta(hours=168)

ISSUANCE_ACCOUNT_ID = UUID("00000000-0000-4000-9000-000000000001")
RESERVE_ACCOUNT_ID = UUID("00000000-0000-4000-9000-000000000002")
REVENUE_ACCOUNT_ID = UUID("00000000-0000-4000-9000-000000000003")
EXPIRED_ACCOUNT_ID = UUID("00000000-0000-4000-9000-000000000004")


class CreditAccountKind(str, Enum):
    USER = "user"
    ISSUANCE = "issuance"
    RESERVE = "reserve"
    REVENUE = "revenue"
    EXPIRED = "expired"


class CreditSourceKind(str, Enum):
    ADMIN = "admin"
    PURCHASED = "purchased"
    SUBSCRIPTION = "subscription"
    EARNED = "earned"
    PROMOTIONAL = "promotional"


class CreditTransactionKind(str, Enum):
    GRANT = "grant"
    RESERVE = "reserve"
    SETTLE = "settle"
    RELEASE = "release"
    EXPIRE = "expire"


class CreditReservationStatus(str, Enum):
    HELD = "held"
    SETTLED = "settled"
    RELEASED = "released"


class CreditConsumptionKind(str, Enum):
    SETTLE = "settle"
    EXPIRE = "expire"


class BillingOutcome(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BillingReason(str, Enum):
    FREE = "free"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNMETERED = "unmetered"


class InsufficientCreditsError(Exception):
    pass


class CreditIdempotencyConflictError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class CreditBalance:
    asset_code: str
    scale: int
    available: int
    reserved: int


@dataclass(frozen=True, slots=True)
class CreditAllowanceWindow:
    starts_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class CreditAllowanceLot:
    lot_id: UUID
    starts_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class FreeCreditAllowance:
    limit: int
    used: int
    reserved: int
    remaining: int
    starts_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class CreditOverview:
    asset_code: str
    scale: int
    available: int
    reserved: int
    free_allowance: FreeCreditAllowance | None


@dataclass(frozen=True, slots=True)
class CreditLotBalance:
    limit: int
    used: int
    reserved: int
    remaining: int


@dataclass(frozen=True, slots=True)
class FreeCreditAllowancePolicy:
    amount: int
    cycle_duration: timedelta

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise ValueError("free credit allowance must be positive")
        if self.cycle_duration != FREE_CREDIT_ALLOWANCE_DURATION:
            raise ValueError("free credit allowance duration must be exactly 168 hours")

    def start_window(self, now: datetime) -> CreditAllowanceWindow:
        if now.tzinfo is None:
            raise ValueError("free credit allowance time must be timezone-aware")
        starts_at = now.astimezone(timezone.utc)
        return CreditAllowanceWindow(
            starts_at=starts_at,
            expires_at=starts_at + self.cycle_duration,
        )


@dataclass(frozen=True, slots=True)
class CreditTransaction:
    id: UUID
    kind: CreditTransactionKind
    available_delta: int
    reserved_delta: int
    source_kind: CreditSourceKind | None
    expires_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CreditTransactionPage:
    items: tuple[CreditTransaction, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class CreditGrant:
    transaction_id: UUID
    lot_id: UUID
    amount: int
    replayed: bool


@dataclass(frozen=True, slots=True)
class InferenceTariff:
    revision: str
    fixed_charge: int = 0
    input_token_rate: int = 0
    output_token_rate: int = 0
    maximum_charge: int = 0
    unmetered_charge: int = 0

    def __post_init__(self) -> None:
        if not self.revision.strip():
            raise ValueError("tariff revision cannot be blank")
        values = (
            self.fixed_charge,
            self.input_token_rate,
            self.output_token_rate,
            self.maximum_charge,
            self.unmetered_charge,
        )
        if any(value < 0 for value in values):
            raise ValueError("tariff amounts cannot be negative")
        if self.maximum_charge < self.fixed_charge:
            raise ValueError("maximum charge cannot be less than the fixed charge")
        if self.unmetered_charge > self.maximum_charge:
            raise ValueError("unmetered charge cannot exceed the maximum charge")
        if self.maximum_charge > 0 and self.unmetered_charge == 0:
            raise ValueError("metered tariffs require an unmetered fallback charge")

    @property
    def is_free(self) -> bool:
        return self.maximum_charge == 0

    def charge(self, input_tokens: int, output_tokens: int) -> int:
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("token counts cannot be negative")
        amount = (
            self.fixed_charge
            + input_tokens * self.input_token_rate
            + output_tokens * self.output_token_rate
        )
        return min(amount, self.maximum_charge)


FREE_INFERENCE_TARIFF = InferenceTariff(revision="free-v1")

FREE_CREDIT_ALLOWANCE_POLICY = FreeCreditAllowancePolicy(
    amount=20 * CREDIT_SCALE,
    cycle_duration=FREE_CREDIT_ALLOWANCE_DURATION,
)
