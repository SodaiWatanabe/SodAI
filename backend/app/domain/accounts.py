from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class AccountStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class ExternalIdentity:
    """A verified identity asserted by any OIDC-compatible provider."""

    issuer: str
    subject: str
    email: str | None = None
    email_verified: bool = False
    display_name: str | None = None

    def __post_init__(self) -> None:
        if not self.issuer.strip():
            raise ValueError("identity issuer must not be empty")
        if not self.subject.strip():
            raise ValueError("identity subject must not be empty")


@dataclass(frozen=True, slots=True)
class Account:
    """SodAI-owned account, independent from the current authentication provider."""

    id: UUID
    status: AccountStatus
    display_name: str | None
    email: str | None
    email_verified: bool
    created_at: datetime
    updated_at: datetime
