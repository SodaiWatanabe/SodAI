from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from functools import lru_cache
from time import monotonic, time

from redis.asyncio import Redis
from redis.exceptions import ResponseError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.db.session import get_session_factory
from app.domain.answerers import ANSWERER_CATALOG, AnswererId, RuntimeKind, get_answerer
from app.domain.inference_operations import (
    EXPECTED_APPLICATION_SCHEMA_REVISION,
    InferenceOperationsSnapshot,
    OperationalStatus,
    RuntimeInferenceSnapshot,
    StreamGroupSnapshot,
)
from app.repositories.inference_operations import (
    InferenceOperationsRepository,
    unavailable_database_snapshot,
)
from app.services.inference.asuka import ASUKA_PSEUDO_ARTIFACT_ID
from app.services.inference.deployment import ModelDeploymentError, ModelDeploymentRegistry

logger = logging.getLogger(__name__)


class InferenceOperationsService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        deployments: ModelDeploymentRegistry,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._deployments = deployments
        self._settings = settings
        self._lock = asyncio.Lock()
        self._cached: InferenceOperationsSnapshot | None = None
        self._cached_at = 0.0

    async def snapshot(self, *, use_cache: bool = True) -> InferenceOperationsSnapshot:
        cached = self._fresh_cached_snapshot() if use_cache else None
        if cached is not None:
            return cached
        async with self._lock:
            cached = self._fresh_cached_snapshot() if use_cache else None
            if cached is not None:
                return cached
            snapshot = await self._collect()
            self._cached = snapshot
            self._cached_at = monotonic()
            return snapshot

    def _fresh_cached_snapshot(self) -> InferenceOperationsSnapshot | None:
        if (
            self._cached is None
            or monotonic() - self._cached_at
            >= self._settings.inference_status_cache_seconds
        ):
            return None
        return self._cached

    async def _collect(self) -> InferenceOperationsSnapshot:
        database = await self._database_snapshot()
        redis_result = await self._redis_snapshot(database.active_artifacts)
        redis_available, event_stream, runtimes = redis_result
        status = self._classify(
            database_available=database.available,
            schema_revision=database.schema_revision,
            redis_available=redis_available,
            event_stream=event_stream,
            runtimes=runtimes,
            oldest_pending_outbox_at=database.oldest_pending_outbox_at,
            oldest_queued_at=database.oldest_queued_at,
        )
        return InferenceOperationsSnapshot(
            status=status,
            checked_at=datetime.now(timezone.utc),
            database=database,
            redis_available=redis_available,
            event_stream=event_stream,
            runtimes=runtimes,
        )

    async def _database_snapshot(self):
        try:
            async with self._session_factory() as session:
                return await asyncio.wait_for(
                    InferenceOperationsRepository(session).snapshot(),
                    timeout=self._settings.inference_status_timeout_seconds,
                )
        except Exception:
            logger.debug("Inference database status check failed", exc_info=True)
            return unavailable_database_snapshot()

    async def _redis_snapshot(
        self, active_artifacts: dict[tuple[AnswererId, str], int]
    ) -> tuple[bool, StreamGroupSnapshot, tuple[RuntimeInferenceSnapshot, ...]]:
        redis = Redis.from_url(
            self._settings.redis_url,
            password=self._settings.redis_password,
            decode_responses=True,
        )
        try:
            return await asyncio.wait_for(
                self._read_redis(redis, active_artifacts),
                timeout=self._settings.inference_status_timeout_seconds,
            )
        except Exception:
            logger.debug("Inference Redis status check failed", exc_info=True)
            return (
                False,
                _missing_stream_group(),
                self._unavailable_runtimes(active_artifacts),
            )
        finally:
            await redis.aclose()

    async def _read_redis(
        self,
        redis: Redis,
        active_artifacts: dict[tuple[AnswererId, str], int],
    ) -> tuple[bool, StreamGroupSnapshot, tuple[RuntimeInferenceSnapshot, ...]]:
        await redis.ping()
        event_stream = await self._group_state(
            redis,
            self._settings.inference_keys.event_stream,
            self._settings.inference_keys.projector_group,
        )
        runtime_specs: list[tuple[AnswererId, str, str | None, bool, bool]] = []
        current_artifacts: set[tuple[AnswererId, str]] = set()
        for answerer in ANSWERER_CATALOG:
            if answerer.runtime_kind is RuntimeKind.HUMAN:
                continue
            artifact_id, deployment_available = self._artifact(
                answerer.runtime_kind, answerer.runtime_name
            )
            runtime_specs.append(
                (
                    answerer.id,
                    answerer.runtime_name,
                    artifact_id,
                    True,
                    deployment_available,
                )
            )
            if artifact_id is not None:
                current_artifacts.add((answerer.id, artifact_id))
        for answerer_artifact in active_artifacts:
            if answerer_artifact in current_artifacts:
                continue
            answerer_id, artifact_id = answerer_artifact
            answerer = get_answerer(answerer_id)
            if answerer is None:
                continue
            runtime_specs.append(
                (
                    answerer.id,
                    answerer.runtime_name,
                    artifact_id,
                    False,
                    self._artifact_is_available(
                        answerer.runtime_kind,
                        answerer.runtime_name,
                        artifact_id,
                    ),
                )
            )

        runtimes = []
        for answerer_id, model, artifact_id, is_current, deployment_available in runtime_specs:
            if artifact_id is None:
                runtimes.append(
                    RuntimeInferenceSnapshot(
                        answerer=answerer_id,
                        model=model,
                        artifact_id=None,
                        is_current_deployment=is_current,
                        deployment_available=False,
                        worker_ready=False,
                        readiness_ttl_seconds=None,
                        stream=_missing_stream_group(),
                    )
                )
                continue
            readiness_key = self._settings.inference_keys.worker_readiness(
                model, artifact_id
            )
            ready, ready_ttl, queue_state = await asyncio.gather(
                redis.exists(readiness_key),
                redis.ttl(readiness_key),
                self._group_state(
                    redis,
                    self._settings.inference_keys.job_stream_for(
                        model, artifact_id
                    ),
                    self._settings.inference_keys.worker_group,
                ),
            )
            runtimes.append(
                RuntimeInferenceSnapshot(
                    answerer=answerer_id,
                    model=model,
                    artifact_id=artifact_id,
                    is_current_deployment=is_current,
                    deployment_available=deployment_available,
                    worker_ready=bool(ready),
                    readiness_ttl_seconds=ready_ttl if ready_ttl >= 0 else None,
                    stream=queue_state,
                )
            )
        return True, event_stream, tuple(runtimes)

    def _artifact_is_available(
        self,
        runtime_kind: RuntimeKind,
        model: str,
        artifact_id: str,
    ) -> bool:
        if runtime_kind is RuntimeKind.PSEUDO_MODEL:
            return artifact_id == ASUKA_PSEUDO_ARTIFACT_ID
        try:
            self._deployments.resolve_artifact(model, artifact_id)
        except ModelDeploymentError:
            return False
        return True

    def _artifact(self, runtime_kind: RuntimeKind, model: str) -> tuple[str | None, bool]:
        if runtime_kind is RuntimeKind.PSEUDO_MODEL:
            return ASUKA_PSEUDO_ARTIFACT_ID, True
        try:
            return self._deployments.resolve(model).artifact_id, True
        except ModelDeploymentError:
            return None, False

    @staticmethod
    async def _group_state(
        redis: Redis, stream: str, group_name: str
    ) -> StreamGroupSnapshot:
        try:
            groups = await redis.xinfo_groups(stream)
        except ResponseError as error:
            if "no such key" in str(error).lower():
                return _missing_stream_group()
            raise
        group = next((item for item in groups if item.get("name") == group_name), None)
        if group is None:
            return _missing_stream_group()
        pending = group.get("pending")
        lag = group.get("lag")
        pending_count = pending if isinstance(pending, int) else 0
        lag_count = lag if isinstance(lag, int) else None
        oldest_pending_idle_ms = None
        if pending_count:
            pending_entries = await redis.xpending_range(
                stream,
                group_name,
                min="-",
                max="+",
                count=1,
            )
            if pending_entries:
                idle = pending_entries[0].get("time_since_delivered")
                oldest_pending_idle_ms = idle if isinstance(idle, int) else None
        oldest_backlog_age_ms = None
        last_delivered_id = group.get("last-delivered-id")
        if lag_count and isinstance(last_delivered_id, str):
            entries = await redis.xrange(
                stream,
                min=f"({last_delivered_id}",
                max="+",
                count=1,
            )
            if entries:
                milliseconds = int(entries[0][0].split("-", maxsplit=1)[0])
                oldest_backlog_age_ms = max(0, int(time() * 1_000) - milliseconds)
        return StreamGroupSnapshot(
            pending=pending_count,
            lag=lag_count,
            oldest_pending_idle_ms=oldest_pending_idle_ms,
            oldest_backlog_age_ms=oldest_backlog_age_ms,
        )

    def _unavailable_runtimes(
        self, active_artifacts: dict[tuple[AnswererId, str], int]
    ) -> tuple[RuntimeInferenceSnapshot, ...]:
        runtimes = []
        current_artifacts: set[tuple[AnswererId, str]] = set()
        for answerer in ANSWERER_CATALOG:
            if answerer.runtime_kind is RuntimeKind.HUMAN:
                continue
            artifact_id, deployment_available = self._artifact(
                answerer.runtime_kind, answerer.runtime_name
            )
            if artifact_id is not None:
                current_artifacts.add((answerer.id, artifact_id))
            runtimes.append(
                RuntimeInferenceSnapshot(
                    answerer=answerer.id,
                    model=answerer.runtime_name,
                    artifact_id=artifact_id,
                    is_current_deployment=True,
                    deployment_available=deployment_available,
                    worker_ready=False,
                    readiness_ttl_seconds=None,
                    stream=_missing_stream_group(),
                )
            )
        for answerer_id, artifact_id in active_artifacts:
            if (answerer_id, artifact_id) in current_artifacts:
                continue
            answerer = get_answerer(answerer_id)
            if answerer is None:
                continue
            runtimes.append(
                RuntimeInferenceSnapshot(
                    answerer=answerer.id,
                    model=answerer.runtime_name,
                    artifact_id=artifact_id,
                    is_current_deployment=False,
                    deployment_available=self._artifact_is_available(
                        answerer.runtime_kind,
                        answerer.runtime_name,
                        artifact_id,
                    ),
                    worker_ready=False,
                    readiness_ttl_seconds=None,
                    stream=_missing_stream_group(),
                )
            )
        return tuple(runtimes)

    @staticmethod
    def _classify(
        *,
        database_available: bool,
        schema_revision: str | None,
        redis_available: bool,
        event_stream: StreamGroupSnapshot,
        runtimes: tuple[RuntimeInferenceSnapshot, ...],
        oldest_pending_outbox_at: datetime | None,
        oldest_queued_at: datetime | None,
    ) -> OperationalStatus:
        if (
            not database_available
            or schema_revision != EXPECTED_APPLICATION_SCHEMA_REVISION
            or not redis_available
            or event_stream.lag is None
            or any(not item.deployment_available or not item.worker_ready for item in runtimes)
            or any(item.stream.lag is None for item in runtimes)
        ):
            return OperationalStatus.UNAVAILABLE
        now = datetime.now(timezone.utc)
        queue_is_stale = (
            oldest_queued_at is not None
            and (now - oldest_queued_at).total_seconds() > 30
        )
        outbox_is_stale = (
            oldest_pending_outbox_at is not None
            and (now - oldest_pending_outbox_at).total_seconds() > 10
        )
        event_stream_is_stale = (
            (event_stream.oldest_pending_idle_ms or 0) > 10_000
            or (event_stream.oldest_backlog_age_ms or 0) > 10_000
        )
        runtime_queue_is_stale = any(
            (runtime.stream.oldest_backlog_age_ms or 0) > 30_000
            for runtime in runtimes
        )
        if (
            queue_is_stale
            or outbox_is_stale
            or event_stream_is_stale
            or runtime_queue_is_stale
        ):
            return OperationalStatus.DEGRADED
        return OperationalStatus.HEALTHY


def _missing_stream_group() -> StreamGroupSnapshot:
    return StreamGroupSnapshot(
        pending=0,
        lag=None,
        oldest_pending_idle_ms=None,
        oldest_backlog_age_ms=None,
    )


@lru_cache
def get_inference_operations_service() -> InferenceOperationsService:
    settings = get_settings()
    return InferenceOperationsService(
        get_session_factory(),
        ModelDeploymentRegistry(settings.model_root),
        settings,
    )
