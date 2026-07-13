from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.credits import CreditSourceKind, CreditTransactionKind


class CreditBalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_code: str
    scale: int
    available: int
    reserved: int


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
