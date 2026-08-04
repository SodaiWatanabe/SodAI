from uuid import uuid4

import pytest

from app.domain.answerers import (
    AnswererId,
    AnswererPricingKind,
    RuntimeKind,
    get_answerer,
    get_human_credit_terms,
)
from app.domain.principals import Principal, PrincipalKind
from app.domain.reasoning import ReasoningEffort
from app.services.thread import (
    AnswererAccessError,
    ReasoningEffortAccessError,
    ThreadService,
)


def principal(kind: PrincipalKind) -> Principal:
    return Principal(kind, uuid4())


def test_guest_cannot_select_asuka() -> None:
    with pytest.raises(AnswererAccessError):
        ThreadService.select_answerer(principal(PrincipalKind.GUEST), AnswererId.ASUKA_1)


def test_authenticated_account_can_select_asuka() -> None:
    answerer = ThreadService.select_answerer(principal(PrincipalKind.USER), AnswererId.ASUKA_1)

    assert answerer.runtime_kind is RuntimeKind.LOCAL_MODEL
    assert answerer.runtime_name == "asuka-1"
    assert answerer.generation_temperature == 0.85
    assert answerer.generation_max_output_tokens == 256


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (PrincipalKind.GUEST, AnswererId.HINA),
        (PrincipalKind.USER, AnswererId.ASUKA_1),
    ],
)
def test_default_answerer_depends_on_principal(kind: PrincipalKind, expected: AnswererId) -> None:
    assert ThreadService.select_answerer(principal(kind), None).id is expected


def test_answerer_catalog_is_the_single_ui_source() -> None:
    answerers = ThreadService.available_answerers(principal(PrincipalKind.USER))

    assert [(item.id, item.name, item.description, item.is_default) for item in answerers] == [
        (AnswererId.ASUKA_1, "Asuka 1", "会話に最適。", True),
        (AnswererId.HINA, "Hina", "知能の萌芽を捉える。", False),
        (AnswererId.HUMAN_LITE, "Human Lite", "日常のやりとりに最適。", False),
        (AnswererId.HUMAN_STANDARD, "Human Standard", "幅広い相談に対応。", False),
        (AnswererId.HUMAN_PRO, "Human Pro", "より高度な応答。", False),
    ]
    by_id = {item.id: item for item in answerers}
    assert by_id[AnswererId.ASUKA_1].pricing.kind is AnswererPricingKind.METERED
    assert (
        by_id[AnswererId.ASUKA_1].pricing.tariff_revision,
        by_id[AnswererId.ASUKA_1].pricing.fixed_charge,
        by_id[AnswererId.ASUKA_1].pricing.input_token_rate,
        by_id[AnswererId.ASUKA_1].pricing.output_token_rate,
        by_id[AnswererId.ASUKA_1].pricing.maximum_charge,
        by_id[AnswererId.ASUKA_1].pricing.unmetered_charge,
    ) == ("asuka-1-flat-v2", 100_000, 0, 0, 100_000, 100_000)
    assert by_id[AnswererId.HINA].pricing.kind is AnswererPricingKind.FREE
    hina = get_answerer(AnswererId.HINA)
    assert hina is not None and hina.generation_max_output_tokens == 128
    assert by_id[AnswererId.HINA].is_legacy is True
    assert by_id[AnswererId.HUMAN_LITE].is_legacy is False
    assert by_id[AnswererId.HUMAN_STANDARD].is_legacy is False
    assert by_id[AnswererId.HUMAN_PRO].is_legacy is False
    assert by_id[AnswererId.HUMAN_LITE].pricing.kind is AnswererPricingKind.METERED
    assert by_id[AnswererId.HUMAN_STANDARD].pricing.kind is AnswererPricingKind.METERED
    assert by_id[AnswererId.HUMAN_PRO].pricing.kind is AnswererPricingKind.METERED
    assert [option.id for option in by_id[AnswererId.ASUKA_1].reasoning_efforts] == [
        ReasoningEffort.NONE
    ]
    assert {
        answerer_id: [
            (option.id, option.execution_time_limit_seconds)
            for option in by_id[answerer_id].reasoning_efforts
        ]
        for answerer_id in (
            AnswererId.HUMAN_LITE,
            AnswererId.HUMAN_STANDARD,
            AnswererId.HUMAN_PRO,
        )
    } == {
        AnswererId.HUMAN_LITE: [(ReasoningEffort.LOW, 180)],
        AnswererId.HUMAN_STANDARD: [
            (ReasoningEffort.LOW, 180),
            (ReasoningEffort.MEDIUM, 480),
            (ReasoningEffort.HIGH, 1200),
        ],
        AnswererId.HUMAN_PRO: [
            (ReasoningEffort.LOW, 180),
            (ReasoningEffort.MEDIUM, 480),
            (ReasoningEffort.HIGH, 1200),
            (ReasoningEffort.XHIGH, 3600),
        ],
    }
    assert (
        by_id[AnswererId.HUMAN_LITE].default_reasoning_effort
        is ReasoningEffort.LOW
    )
    assert (
        by_id[AnswererId.HUMAN_STANDARD].default_reasoning_effort
        is ReasoningEffort.MEDIUM
    )
    assert (
        by_id[AnswererId.HUMAN_PRO].default_reasoning_effort
        is ReasoningEffort.MEDIUM
    )
    lite = get_answerer(AnswererId.HUMAN_LITE)
    standard = get_answerer(AnswererId.HUMAN_STANDARD)
    pro = get_answerer(AnswererId.HUMAN_PRO)
    assert lite is not None and lite.required_human_rank == 1
    assert standard is not None and standard.required_human_rank == 2
    assert pro is not None and pro.required_human_rank == 3
    guest_answerers = ThreadService.available_answerers(principal(PrincipalKind.GUEST))
    assert all(item.pricing.kind is AnswererPricingKind.FREE for item in guest_answerers)


@pytest.mark.parametrize(
    ("answerer_id", "effort", "charge", "reward", "revenue"),
    [
        (AnswererId.HUMAN_LITE, ReasoningEffort.LOW, 500_000, 450_000, 50_000),
        (AnswererId.HUMAN_STANDARD, ReasoningEffort.LOW, 750_000, 675_000, 75_000),
        (
            AnswererId.HUMAN_STANDARD,
            ReasoningEffort.MEDIUM,
            1_500_000,
            1_350_000,
            150_000,
        ),
        (
            AnswererId.HUMAN_STANDARD,
            ReasoningEffort.HIGH,
            3_000_000,
            2_700_000,
            300_000,
        ),
        (AnswererId.HUMAN_PRO, ReasoningEffort.LOW, 1_000_000, 900_000, 100_000),
        (
            AnswererId.HUMAN_PRO,
            ReasoningEffort.MEDIUM,
            2_000_000,
            1_800_000,
            200_000,
        ),
        (
            AnswererId.HUMAN_PRO,
            ReasoningEffort.HIGH,
            4_000_000,
            3_600_000,
            400_000,
        ),
        (
            AnswererId.HUMAN_PRO,
            ReasoningEffort.XHIGH,
            8_000_000,
            7_200_000,
            800_000,
        ),
    ],
)
def test_human_credit_terms_split_ten_percent_platform_share(
    answerer_id: AnswererId,
    effort: ReasoningEffort,
    charge: int,
    reward: int,
    revenue: int,
) -> None:
    terms = get_human_credit_terms(answerer_id, effort)

    assert (
        terms.customer_charge,
        terms.performer_reward,
        terms.platform_revenue,
    ) == (charge, reward, revenue)


def test_human_reasoning_effort_rejects_none() -> None:
    answerer = get_answerer(AnswererId.HUMAN_LITE)
    assert answerer is not None

    with pytest.raises(ReasoningEffortAccessError):
        ThreadService.select_reasoning_effort(answerer, ReasoningEffort.NONE)

    assert (
        ThreadService.select_reasoning_effort(answerer, None)
        is ReasoningEffort.LOW
    )

    with pytest.raises(ReasoningEffortAccessError):
        ThreadService.select_reasoning_effort(answerer, ReasoningEffort.MEDIUM)


def test_human_reasoning_effort_unlocks_by_answerer_rank() -> None:
    standard = get_answerer(AnswererId.HUMAN_STANDARD)
    pro = get_answerer(AnswererId.HUMAN_PRO)
    assert standard is not None
    assert pro is not None

    assert (
        ThreadService.select_reasoning_effort(standard, ReasoningEffort.HIGH)
        is ReasoningEffort.HIGH
    )
    with pytest.raises(ReasoningEffortAccessError):
        ThreadService.select_reasoning_effort(standard, ReasoningEffort.XHIGH)
    assert (
        ThreadService.select_reasoning_effort(pro, ReasoningEffort.XHIGH)
        is ReasoningEffort.XHIGH
    )
