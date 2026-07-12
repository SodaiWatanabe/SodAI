from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

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
