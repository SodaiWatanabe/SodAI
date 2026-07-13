from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class PrincipalKind(str, Enum):
    USER = "user"
    GUEST = "guest"


@dataclass(frozen=True, slots=True)
class Principal:
    """The authenticated owner at the HTTP boundary.

    A principal is deliberately not an Actor. The identity module resolves it
    to an Actor before collaboration data is read or written.
    """

    kind: PrincipalKind
    id: UUID
