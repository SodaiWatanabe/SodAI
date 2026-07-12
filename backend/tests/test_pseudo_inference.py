from uuid import UUID

import pytest

from app.domain.conversations import ConversationPrincipal, PrincipalKind
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


def test_guest_cannot_select_flagship_model() -> None:
    principal = ConversationPrincipal(
        PrincipalKind.GUEST,
        UUID("018f96d4-7c48-7c27-a71f-591e3cb8748a"),
    )

    with pytest.raises(ModelAccessError):
        ConversationService.resolve_model(principal, "flagship")


def test_authenticated_user_can_select_flagship_model() -> None:
    principal = ConversationPrincipal(
        PrincipalKind.USER,
        UUID("018f96d4-7c48-7c27-a71f-591e3cb8748a"),
    )

    assert ConversationService.resolve_model(principal, "flagship") == "pseudo-sodai-flagship-v1"
