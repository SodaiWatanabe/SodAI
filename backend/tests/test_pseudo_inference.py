from uuid import UUID

import pytest

from app.domain.conversations import ConversationPrincipal, PrincipalKind
from app.domain.model_catalog import ModelId
from app.services.conversation import ConversationService, ModelAccessError
from app.services.pseudo_inference import PseudoSodAI


def test_pseudo_sodai_responds_to_greeting_without_role_language() -> None:
    response = PseudoSodAI.compose("こんにちは")

    assert response.startswith("こんにちは。")
    assert "アシスタント" not in response
    assert "ユーザー" not in response


def test_pseudo_sodai_keeps_partner_message_in_generic_response() -> None:
    response = PseudoSodAI.compose("今日は設計について考えています")

    assert "今日は設計について考えています" in response
    assert "疑似AI" in response


def test_guest_cannot_select_asuka_1() -> None:
    principal = ConversationPrincipal(
        PrincipalKind.GUEST,
        UUID("018f96d4-7c48-7c27-a71f-591e3cb8748a"),
    )

    with pytest.raises(ModelAccessError):
        ConversationService.select_model(principal, ModelId.ASUKA_1)


def test_authenticated_user_can_select_asuka_1() -> None:
    principal = ConversationPrincipal(
        PrincipalKind.USER,
        UUID("018f96d4-7c48-7c27-a71f-591e3cb8748a"),
    )

    assert (
        ConversationService.select_model(principal, ModelId.ASUKA_1).runtime_id
        == "pseudo-sodai-asuka-1-v1"
    )


@pytest.mark.parametrize(
    ("kind", "expected"),
    [(PrincipalKind.GUEST, ModelId.HINA), (PrincipalKind.USER, ModelId.ASUKA_1)],
)
def test_default_model_depends_on_principal(kind: PrincipalKind, expected: ModelId) -> None:
    principal = ConversationPrincipal(
        kind,
        UUID("018f96d4-7c48-7c27-a71f-591e3cb8748a"),
    )

    assert ConversationService.select_model(principal, None).id is expected


def test_model_catalog_uses_sodai_model_names() -> None:
    principal = ConversationPrincipal(
        PrincipalKind.USER,
        UUID("018f96d4-7c48-7c27-a71f-591e3cb8748a"),
    )

    models = ConversationService.available_models(principal)

    assert [(model.id, model.name, model.description, model.is_default) for model in models] == [
        (ModelId.ASUKA_1, "Asuka 1", "会話に最適。", True),
        (ModelId.HINA, "Hina", "知能の萌芽。", False),
    ]


def test_guest_model_catalog_contains_only_hina() -> None:
    principal = ConversationPrincipal(
        PrincipalKind.GUEST,
        UUID("018f96d4-7c48-7c27-a71f-591e3cb8748a"),
    )

    models = ConversationService.available_models(principal)

    assert [(model.id, model.is_default) for model in models] == [(ModelId.HINA, True)]
