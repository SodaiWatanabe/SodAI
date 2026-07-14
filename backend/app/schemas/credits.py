from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.credits import CreditSourceKind, CreditTransactionKind


class FreeCreditAllowanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    limit: int
    used: int
    reserved: int
    remaining: int
    starts_at: datetime
    expires_at: datetime


class CreditBalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_code: str
    scale: int
    available: int
    reserved: int
    free_allowance: FreeCreditAllowanceResponse | None


class CreditTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: CreditTransactionKind
    available_delta: int
    reserved_delta: int
    source_kind: CreditSourceKind | None
    expires_at: datetime | None
    created_at: datetime


class CreditTransactionListResponse(BaseModel):
    items: list[CreditTransactionResponse]
    next_cursor: str | None
