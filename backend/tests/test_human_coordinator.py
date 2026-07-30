import asyncio

import pytest

from app.services.human_coordinator import HumanCoordinator


class StubHumanService:
    def __init__(self) -> None:
        self.reconciled = asyncio.Event()
        self.calls = 0

    async def match_available_best_effort(self) -> None:
        self.calls += 1
        self.reconciled.set()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_human_coordinator_reconciles_without_browser_activity() -> None:
    service = StubHumanService()
    coordinator = HumanCoordinator(
        service,
        reconciliation_interval_seconds=0.01,
    )

    coordinator.start()
    await asyncio.wait_for(service.reconciled.wait(), timeout=1)
    await coordinator.stop()

    assert service.calls >= 1
