from uuid import uuid4

import pytest

from app.domain.answerers import AnswererId, AnswererPricingKind, RuntimeKind
from app.domain.principals import Principal, PrincipalKind
from app.services.inference.asuka import AsukaPseudoGenerator
from app.services.thread import AnswererAccessError, ThreadService


def principal(kind: PrincipalKind) -> Principal:
    return Principal(kind, uuid4())


def test_guest_cannot_select_asuka() -> None:
    with pytest.raises(AnswererAccessError):
        ThreadService.select_answerer(principal(PrincipalKind.GUEST), AnswererId.ASUKA_1)


def test_authenticated_account_can_select_asuka() -> None:
    answerer = ThreadService.select_answerer(principal(PrincipalKind.USER), AnswererId.ASUKA_1)

    assert answerer.runtime_kind is RuntimeKind.PSEUDO_MODEL
    assert answerer.runtime_name == "asuka-1"


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
    guest_answerers = ThreadService.available_answerers(principal(PrincipalKind.GUEST))
    assert all(item.pricing.kind is AnswererPricingKind.FREE for item in guest_answerers)


def test_asuka_pseudo_response_is_long_enough_to_exercise_streaming() -> None:
    response = AsukaPseudoGenerator.compose("こんにちは")

    assert len(response) > 80
    assert "疑似AI" in response
