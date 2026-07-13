from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from app.domain.credits import (
    CREDIT_ASSET_CODE,
    CREDIT_SCALE,
    FREE_INFERENCE_TARIFF,
    InferenceTariff,
)


class AnswererId(str, Enum):
    HINA = "hina"
    ASUKA_1 = "asuka-1"


class AnswererAudience(str, Enum):
    GUEST = "guest"
    AUTHENTICATED = "authenticated"


class RuntimeKind(str, Enum):
    LOCAL_MODEL = "local_model"
    PSEUDO_MODEL = "pseudo_model"


class AnswererPricingKind(str, Enum):
    FREE = "free"
    METERED = "metered"


@dataclass(frozen=True, slots=True)
class AnswererPricing:
    kind: AnswererPricingKind
    asset_code: str
    scale: int
    tariff_revision: str
    fixed_charge: int
    input_token_rate: int
    output_token_rate: int
    maximum_charge: int
    unmetered_charge: int


@dataclass(frozen=True, slots=True)
class AnswererDefinition:
    id: AnswererId
    actor_id: UUID
    name: str
    description: str
    runtime_kind: RuntimeKind
    runtime_name: str
    tariff: InferenceTariff
    audiences: frozenset[AnswererAudience]
    default_for: frozenset[AnswererAudience] = frozenset()


@dataclass(frozen=True, slots=True)
class AvailableAnswerer:
    id: AnswererId
    name: str
    description: str
    is_default: bool
    pricing: AnswererPricing


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
        tariff=FREE_INFERENCE_TARIFF,
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
        tariff=FREE_INFERENCE_TARIFF,
        audiences=frozenset(AnswererAudience),
        default_for=frozenset({AnswererAudience.GUEST}),
    ),
)
_ANSWERERS_BY_ID = {answerer.id: answerer for answerer in ANSWERER_CATALOG}

if len(_ANSWERERS_BY_ID) != len(ANSWERER_CATALOG):
    raise RuntimeError("Answerer catalog contains duplicate identifiers")
if any(
    AnswererAudience.GUEST in answerer.audiences and not answerer.tariff.is_free
    for answerer in ANSWERER_CATALOG
):
    raise RuntimeError("Guest answerers must use a free tariff")

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
            pricing=AnswererPricing(
                kind=(
                    AnswererPricingKind.FREE
                    if item.tariff.is_free
                    else AnswererPricingKind.METERED
                ),
                asset_code=CREDIT_ASSET_CODE,
                scale=CREDIT_SCALE,
                tariff_revision=item.tariff.revision,
                fixed_charge=item.tariff.fixed_charge,
                input_token_rate=item.tariff.input_token_rate,
                output_token_rate=item.tariff.output_token_rate,
                maximum_charge=item.tariff.maximum_charge,
                unmetered_charge=item.tariff.unmetered_charge,
            ),
        )
        for item in ANSWERER_CATALOG
        if audience in item.audiences
    ]
