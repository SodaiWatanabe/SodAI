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
    HUMAN_LITE = "human-lite"
    HUMAN_STANDARD = "human-standard"
    HUMAN_PRO = "human-pro"


class AnswererAudience(str, Enum):
    GUEST = "guest"
    AUTHENTICATED = "authenticated"


class RuntimeKind(str, Enum):
    LOCAL_MODEL = "local_model"
    PSEUDO_MODEL = "pseudo_model"
    HUMAN = "human"


class AnswererPricingKind(str, Enum):
    FREE = "free"
    METERED = "metered"


class AnswererKind(str, Enum):
    AI = "ai"
    HUMAN = "human"


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
    required_human_rank: int | None = None
    is_legacy: bool = False


@dataclass(frozen=True, slots=True)
class AvailableAnswerer:
    id: AnswererId
    name: str
    description: str
    kind: AnswererKind
    is_default: bool
    is_legacy: bool
    pricing: AnswererPricing


HINA_ACTOR_ID = UUID("00000000-0000-4000-8000-000000000001")
ASUKA_1_ACTOR_ID = UUID("00000000-0000-4000-8000-000000000002")
HUMAN_LITE_ACTOR_ID = UUID("00000000-0000-4000-8000-000000000003")
HUMAN_PRO_ACTOR_ID = UUID("00000000-0000-4000-8000-000000000004")
HUMAN_STANDARD_ACTOR_ID = UUID("00000000-0000-4000-8000-000000000005")
ASUKA_1_FIXED_CHARGE = CREDIT_SCALE // 10

ASUKA_1_TARIFF = InferenceTariff(
    revision="asuka-1-flat-v2",
    fixed_charge=ASUKA_1_FIXED_CHARGE,
    maximum_charge=ASUKA_1_FIXED_CHARGE,
    unmetered_charge=ASUKA_1_FIXED_CHARGE,
)

ANSWERER_CATALOG = (
    AnswererDefinition(
        id=AnswererId.ASUKA_1,
        actor_id=ASUKA_1_ACTOR_ID,
        name="Asuka 1",
        description="会話に最適。",
        runtime_kind=RuntimeKind.PSEUDO_MODEL,
        runtime_name="asuka-1",
        tariff=ASUKA_1_TARIFF,
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
        is_legacy=True,
    ),
    AnswererDefinition(
        id=AnswererId.HUMAN_LITE,
        actor_id=HUMAN_LITE_ACTOR_ID,
        name="Human Lite",
        description="日常のやりとりに最適。",
        runtime_kind=RuntimeKind.HUMAN,
        runtime_name="human-lite",
        tariff=FREE_INFERENCE_TARIFF,
        audiences=frozenset({AnswererAudience.AUTHENTICATED}),
        required_human_rank=1,
    ),
    AnswererDefinition(
        id=AnswererId.HUMAN_STANDARD,
        actor_id=HUMAN_STANDARD_ACTOR_ID,
        name="Human Standard",
        description="幅広い相談に対応。",
        runtime_kind=RuntimeKind.HUMAN,
        runtime_name="human-standard",
        tariff=FREE_INFERENCE_TARIFF,
        audiences=frozenset({AnswererAudience.AUTHENTICATED}),
        required_human_rank=2,
    ),
    AnswererDefinition(
        id=AnswererId.HUMAN_PRO,
        actor_id=HUMAN_PRO_ACTOR_ID,
        name="Human Pro",
        description="より高度な応答。",
        runtime_kind=RuntimeKind.HUMAN,
        runtime_name="human-pro",
        tariff=FREE_INFERENCE_TARIFF,
        audiences=frozenset({AnswererAudience.AUTHENTICATED}),
        required_human_rank=3,
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
if any(
    (answerer.runtime_kind is RuntimeKind.HUMAN) != (answerer.required_human_rank is not None)
    for answerer in ANSWERER_CATALOG
):
    raise RuntimeError("Only Human answerers must define a required Human rank")

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
            kind=(
                AnswererKind.HUMAN if item.runtime_kind is RuntimeKind.HUMAN else AnswererKind.AI
            ),
            is_default=item.id is default.id,
            is_legacy=item.is_legacy,
            pricing=AnswererPricing(
                kind=(
                    AnswererPricingKind.FREE if item.tariff.is_free else AnswererPricingKind.METERED
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


def get_human_rank_name(rank_level: int) -> str:
    eligible = [
        item
        for item in ANSWERER_CATALOG
        if item.runtime_kind is RuntimeKind.HUMAN
        and item.required_human_rank is not None
        and item.required_human_rank <= rank_level
    ]
    if not eligible:
        return "Human"
    return max(eligible, key=lambda item: item.required_human_rank or 0).name
