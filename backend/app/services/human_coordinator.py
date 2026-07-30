from __future__ import annotations

import asyncio
from typing import Protocol

from app.core.config import Settings, get_settings
from app.services.human import get_human_service


class HumanMatchingService(Protocol):
    async def match_available_best_effort(self) -> None: ...


class HumanCoordinator:
    def __init__(
        self,
        service: HumanMatchingService,
        *,
        reconciliation_interval_seconds: float,
    ) -> None:
        self._service = service
        self._reconciliation_interval_seconds = reconciliation_interval_seconds
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(
            self._reconcile_loop(),
            name="human-matching-reconciler",
        )

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)
        self._task = None

    async def _reconcile_loop(self) -> None:
        while True:
            await self._service.match_available_best_effort()
            await asyncio.sleep(self._reconciliation_interval_seconds)


def create_human_coordinator(settings: Settings | None = None) -> HumanCoordinator:
    settings = settings or get_settings()
    return HumanCoordinator(
        get_human_service(),
        reconciliation_interval_seconds=settings.human_reconciliation_interval_seconds,
    )
