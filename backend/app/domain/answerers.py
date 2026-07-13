from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class AnswererId(str, Enum):
    HINA = "hina"
    ASUKA_1 = "asuka-1"


class AnswererAudience(str, Enum):
    GUEST = "guest"
    AUTHENTICATED = "authenticated"


class RuntimeKind(str, Enum):
    LOCAL_MODEL = "local_model"
    PSEUDO_MODEL = "pseudo_model"


@dataclass(frozen=True, slots=True)
class AnswererDefinition:
    id: AnswererId
    actor_id: UUID
    name: str
    description: str
    runtime_kind: RuntimeKind
    runtime_name: str
    audiences: frozenset[AnswererAudience]
    default_for: frozenset[AnswererAudience] = frozenset()


@dataclass(frozen=True, slots=True)
class AvailableAnswerer:
    id: AnswererId
    name: str
    description: str
    is_default: bool


HINA_ACTOR_ID = UUID("00000000-0000-4000-8000-000000000001")
ASUKA_1_ACTOR_ID = UUID("00000000-0000-4000-8000-000000000002")

ANSWERER_CATALOG = (
    AnswererDefinition(
        id=AnswererId.ASUKA_1,
        actor_id=ASUKA_1_ACTOR_ID,
        name="Asuka 1",
        description="会話に最適。",
        runtime_kind=RuntimeKind.PSEUDO_MODEL,
        runtime_name="asuka-1",
        audiences=frozenset({AnswererAudience.AUTHENTICATED}),
        default_for=frozenset({AnswererAudience.AUTHENTICATED}),
    ),
    AnswererDefinition(
        id=AnswererId.HINA,
        actor_id=HINA_ACTOR_ID,
        name="Hina",
        description="知能の萌芽を捉える。",
        runtime_kind=RuntimeKind.LOCAL_MODEL,
        runtime_name="hina",
        audiences=frozenset(AnswererAudience),
        default_for=frozenset({AnswererAudience.GUEST}),
    ),
)
_ANSWERERS_BY_ID = {answerer.id: answerer for answerer in ANSWERER_CATALOG}

if len(_ANSWERERS_BY_ID) != len(ANSWERER_CATALOG):
    raise RuntimeError("Answerer catalog contains duplicate identifiers")

_DEFAULTS: dict[AnswererAudience, AnswererDefinition] = {}
for audience in AnswererAudience:
    defaults = [item for item in ANSWERER_CATALOG if audience in item.default_for]
    if len(defaults) != 1 or audience not in defaults[0].audiences:
        raise RuntimeError(f"Answerer catalog must define one available default for {audience}")
    _DEFAULTS[audience] = defaults[0]


def get_answerer(answerer_id: AnswererId) -> AnswererDefinition | None:
    return _ANSWERERS_BY_ID.get(answerer_id)


def get_default_answerer(audience: AnswererAudience) -> AnswererDefinition:
    return _DEFAULTS[audience]


def list_available_answerers(audience: AnswererAudience) -> list[AvailableAnswerer]:
    default = get_default_answerer(audience)
    return [
        AvailableAnswerer(
            id=item.id,
            name=item.name,
            description=item.description,
            is_default=item.id is default.id,
        )
        for item in ANSWERER_CATALOG
        if audience in item.audiences
    ]
