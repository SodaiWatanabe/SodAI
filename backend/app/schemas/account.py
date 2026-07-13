from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.accounts import AccountStatus


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: AccountStatus
    display_name: str | None
    email: str | None
    email_verified: bool
    created_at: datetime
    updated_at: datetime


class AccountProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("display_name must not be blank")
        return normalized
