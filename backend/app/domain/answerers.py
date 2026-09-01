from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from app.domain.credits import (
    CREDIT_ASSET_CODE,
    CREDIT_SCALE,
    FREE_INFERENCE_TARIFF,
    HumanCreditTerms,
    InferenceTariff,
)
from app.domain.reasoning import (
    REASONING_EFFORT_CATALOG,
    ReasoningEffort,
)


class AnswererId(str, Enum):
    HINA = "hina"
    ASUKA_1 = "asuka-1"
    ASUKA_1_1 = "asuka-1.1"
    HUMAN_LITE = "human-lite"
    HUMAN_STANDARD = "human-standard"
    HUMAN_PRO = "human-pro"


class AnswererAudience(str, Enum):
    GUEST = "guest"
    AUTHENTICATED = "authenticated"


class RuntimeKind(str, Enum):
    LOCAL_MODEL = "local_model"
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
    deployment_name: str | None
    tariff: InferenceTariff
    audiences: frozenset[AnswererAudience]
    default_for: frozenset[AnswererAudience] = frozenset()
    supported_reasoning_efforts: frozenset[ReasoningEffort] = frozenset(
        {ReasoningEffort.NONE}
    )
    default_reasoning_effort: ReasoningEffort = ReasoningEffort.NONE
    generation_temperature: float = 0.85
    generation_max_output_tokens: int = 128
    required_human_rank: int | None = None
    is_legacy: bool = False


@dataclass(frozen=True, slots=True)
class AvailableReasoningEffort:
    id: ReasoningEffort
    name: str
    execution_time_limit_seconds: int | None
    customer_charge: int
    performer_reward: int


@dataclass(frozen=True, slots=True)
class AvailableAnswerer:
    id: AnswererId
    name: str
    description: str
    kind: AnswererKind
    is_default: bool
    is_legacy: bool
    pricing: AnswererPricing
    reasoning_efforts: tuple[AvailableReasoningEffort, ...]
    default_reasoning_effort: ReasoningEffort


HINA_ACTOR_ID = UUID("00000000-0000-4000-8000-000000000001")
HUMAN_LITE_ACTOR_ID = UUID("00000000-0000-4000-8000-000000000003")
HUMAN_PRO_ACTOR_ID = UUID("00000000-0000-4000-8000-000000000004")
HUMAN_STANDARD_ACTOR_ID = UUID("00000000-0000-4000-8000-000000000005")
ASUKA_1_1_ACTOR_ID = UUID("00000000-0000-4000-8000-000000000006")
ASUKA_1_1_FIXED_CHARGE = CREDIT_SCALE // 10
HUMAN_LITE_REASONING_EFFORTS = frozenset({ReasoningEffort.LOW})
HUMAN_STANDARD_REASONING_EFFORTS = HUMAN_LITE_REASONING_EFFORTS | {
    ReasoningEffort.MEDIUM,
    ReasoningEffort.HIGH,
}
HUMAN_PRO_REASONING_EFFORTS = HUMAN_STANDARD_REASONING_EFFORTS | {
    ReasoningEffort.XHIGH
}


def _fixed_tariff(revision: str, charge: int) -> InferenceTariff:
    return InferenceTariff(
        revision=revision,
        fixed_charge=charge,
        maximum_charge=charge,
        unmetered_charge=charge,
    )


HUMAN_CREDIT_TERMS = {
    (AnswererId.HUMAN_LITE, ReasoningEffort.LOW): HumanCreditTerms.from_customer_charge(
        CREDIT_SCALE // 2
    ),
    (
        AnswererId.HUMAN_STANDARD,
        ReasoningEffort.LOW,
    ): HumanCreditTerms.from_customer_charge(3 * CREDIT_SCALE // 4),
    (
        AnswererId.HUMAN_STANDARD,
        ReasoningEffort.MEDIUM,
    ): HumanCreditTerms.from_customer_charge(3 * CREDIT_SCALE // 2),
    (
        AnswererId.HUMAN_STANDARD,
        ReasoningEffort.HIGH,
    ): HumanCreditTerms.from_customer_charge(3 * CREDIT_SCALE),
    (AnswererId.HUMAN_PRO, ReasoningEffort.LOW): HumanCreditTerms.from_customer_charge(
        CREDIT_SCALE
    ),
    (
        AnswererId.HUMAN_PRO,
        ReasoningEffort.MEDIUM,
    ): HumanCreditTerms.from_customer_charge(2 * CREDIT_SCALE),
    (
        AnswererId.HUMAN_PRO,
        ReasoningEffort.HIGH,
    ): HumanCreditTerms.from_customer_charge(4 * CREDIT_SCALE),
    (
        AnswererId.HUMAN_PRO,
        ReasoningEffort.XHIGH,
    ): HumanCreditTerms.from_customer_charge(8 * CREDIT_SCALE),
}

ASUKA_1_1_TARIFF = InferenceTariff(
    revision="asuka-1.1-flat-v1",
    fixed_charge=ASUKA_1_1_FIXED_CHARGE,
    maximum_charge=ASUKA_1_1_FIXED_CHARGE,
    unmetered_charge=ASUKA_1_1_FIXED_CHARGE,
)

ANSWERER_CATALOG = (
    AnswererDefinition(
        id=AnswererId.ASUKA_1_1,
        actor_id=ASUKA_1_1_ACTOR_ID,
        name="Asuka 1.1",
        description="会話に最適。",
        runtime_kind=RuntimeKind.LOCAL_MODEL,
        runtime_name="asuka-1",
        deployment_name="asuka-1.1",
        tariff=ASUKA_1_1_TARIFF,
        audiences=frozenset({AnswererAudience.AUTHENTICATED}),
        default_for=frozenset({AnswererAudience.AUTHENTICATED}),
        generation_temperature=0.85,
        generation_max_output_tokens=256,
    ),
    AnswererDefinition(
        id=AnswererId.HINA,
        actor_id=HINA_ACTOR_ID,
        name="Hina",
        description="知能の萌芽を捉える。",
        runtime_kind=RuntimeKind.LOCAL_MODEL,
        runtime_name="hina",
        deployment_name="hina",
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
        deployment_name=None,
        tariff=_fixed_tariff("human-lite-low-v1", CREDIT_SCALE // 2),
        audiences=frozenset({AnswererAudience.AUTHENTICATED}),
        supported_reasoning_efforts=HUMAN_LITE_REASONING_EFFORTS,
        default_reasoning_effort=ReasoningEffort.LOW,
        required_human_rank=1,
    ),
    AnswererDefinition(
        id=AnswererId.HUMAN_STANDARD,
        actor_id=HUMAN_STANDARD_ACTOR_ID,
        name="Human Standard",
        description="幅広い相談に対応。",
        runtime_kind=RuntimeKind.HUMAN,
        runtime_name="human-standard",
        deployment_name=None,
        tariff=_fixed_tariff("human-standard-medium-v1", 3 * CREDIT_SCALE // 2),
        audiences=frozenset({AnswererAudience.AUTHENTICATED}),
        supported_reasoning_efforts=HUMAN_STANDARD_REASONING_EFFORTS,
        default_reasoning_effort=ReasoningEffort.MEDIUM,
        required_human_rank=2,
    ),
    AnswererDefinition(
        id=AnswererId.HUMAN_PRO,
        actor_id=HUMAN_PRO_ACTOR_ID,
        name="Human Pro",
        description="より高度な応答。",
        runtime_kind=RuntimeKind.HUMAN,
        runtime_name="human-pro",
        deployment_name=None,
        tariff=_fixed_tariff("human-pro-medium-v1", 2 * CREDIT_SCALE),
        audiences=frozenset({AnswererAudience.AUTHENTICATED}),
        supported_reasoning_efforts=HUMAN_PRO_REASONING_EFFORTS,
        default_reasoning_effort=ReasoningEffort.MEDIUM,
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
if any(
    (answerer.runtime_kind is RuntimeKind.LOCAL_MODEL)
    != (answerer.deployment_name is not None)
    for answerer in ANSWERER_CATALOG
):
    raise RuntimeError("Only local model answerers must define a deployment name")
if any(
    answerer.default_reasoning_effort not in answerer.supported_reasoning_efforts
    for answerer in ANSWERER_CATALOG
):
    raise RuntimeError("Answerer default reasoning effort must be supported")
if any(
    answerer.runtime_kind is RuntimeKind.HUMAN
    and ReasoningEffort.NONE in answerer.supported_reasoning_efforts
    for answerer in ANSWERER_CATALOG
):
    raise RuntimeError("Human answerers cannot support none reasoning effort")
if {
    (answerer.id, effort)
    for answerer in ANSWERER_CATALOG
    if answerer.runtime_kind is RuntimeKind.HUMAN
    for effort in answerer.supported_reasoning_efforts
} != set(HUMAN_CREDIT_TERMS):
    raise RuntimeError("Human credit terms must cover every supported reasoning effort")

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


def get_human_credit_terms(
    answerer_id: AnswererId,
    reasoning_effort: ReasoningEffort,
) -> HumanCreditTerms:
    try:
        return HUMAN_CREDIT_TERMS[(answerer_id, reasoning_effort)]
    except KeyError as error:
        raise ValueError("unsupported Human credit terms") from error


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
            reasoning_efforts=tuple(
                AvailableReasoningEffort(
                    id=definition.id,
                    name=definition.name,
                    execution_time_limit_seconds=definition.execution_time_limit_seconds,
                    customer_charge=(
                        get_human_credit_terms(item.id, definition.id).customer_charge
                        if item.runtime_kind is RuntimeKind.HUMAN
                        else item.tariff.maximum_charge
                    ),
                    performer_reward=(
                        get_human_credit_terms(item.id, definition.id).performer_reward
                        if item.runtime_kind is RuntimeKind.HUMAN
                        else 0
                    ),
                )
                for definition in REASONING_EFFORT_CATALOG
                if definition.id in item.supported_reasoning_efforts
            ),
            default_reasoning_effort=item.default_reasoning_effort,
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
