from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.answerers import AnswererId

EXPECTED_APPLICATION_SCHEMA_REVISION = "20260731_0010"


class OperationalStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class DatabaseInferenceSnapshot:
    available: bool
    schema_revision: str | None
    queued: int
    running: int
    failed_last_hour: int
    pending_outbox: int
    oldest_pending_outbox_at: datetime | None
    oldest_queued_at: datetime | None
    active_by_answerer: dict[AnswererId, int]
    active_artifacts: dict[tuple[AnswererId, str], int]


@dataclass(frozen=True, slots=True)
class StreamGroupSnapshot:
    pending: int
    lag: int | None
    oldest_pending_idle_ms: int | None
    oldest_backlog_age_ms: int | None


@dataclass(frozen=True, slots=True)
class RuntimeInferenceSnapshot:
    answerer: AnswererId
    model: str
    artifact_id: str | None
    is_current_deployment: bool
    deployment_available: bool
    worker_ready: bool
    readiness_ttl_seconds: int | None
    stream: StreamGroupSnapshot


@dataclass(frozen=True, slots=True)
class InferenceOperationsSnapshot:
    status: OperationalStatus
    checked_at: datetime
    database: DatabaseInferenceSnapshot
    redis_available: bool
    event_stream: StreamGroupSnapshot
    runtimes: tuple[RuntimeInferenceSnapshot, ...]
