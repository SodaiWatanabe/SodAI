from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.domain.credits import FREE_INFERENCE_TARIFF, InferenceTariff
from app.services.credits import CreditService


def test_metered_tariff_caps_the_charge_at_the_reserved_amount() -> None:
    tariff = InferenceTariff(
        revision="test-v1",
        fixed_charge=2,
        input_token_rate=3,
        output_token_rate=5,
        maximum_charge=100,
        unmetered_charge=100,
    )

    assert tariff.charge(10, 4) == 52
    assert tariff.charge(100, 100) == 100


def test_tariff_rejects_invalid_amounts() -> None:
    with pytest.raises(ValueError):
        InferenceTariff(revision="invalid", maximum_charge=-1)
    with pytest.raises(ValueError):
        InferenceTariff(revision="invalid", fixed_charge=2, maximum_charge=1)
    with pytest.raises(ValueError):
        InferenceTariff(revision="fail-open", maximum_charge=10)


def test_current_free_tariff_has_no_reservation() -> None:
    assert FREE_INFERENCE_TARIFF.is_free
    assert FREE_INFERENCE_TARIFF.charge(100, 100) == 0


def test_credit_transaction_cursor_is_opaque_and_round_trips() -> None:
    created_at = datetime(2026, 7, 13, 15, 0, tzinfo=timezone.utc)
    transaction_id = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748b")
    cursor = "MjAyNi0wNy0xM1QxNTowMDowMCswMDowMHwwMThmOTZkNC03YzQ4LTdjMjctYTcxZi01OTFlM2NiODc0OGI"

    assert CreditService._parse_cursor(cursor) == (created_at, transaction_id)


@pytest.mark.parametrize("cursor", ["not-base64!", "", "bm90LWEtdHVwbGU"])
def test_credit_transaction_cursor_rejects_malformed_values(cursor: str) -> None:
    with pytest.raises(ValueError, match="invalid credit transaction cursor"):
        CreditService._parse_cursor(cursor)
