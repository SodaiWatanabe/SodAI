from datetime import datetime, timedelta, timezone
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.domain.answerers import AnswererId
from app.domain.inference_operations import (
    EXPECTED_APPLICATION_SCHEMA_REVISION,
    OperationalStatus,
    RuntimeInferenceSnapshot,
    StreamGroupSnapshot,
)
from app.services.inference.operations import InferenceOperationsService


def stream(
    *,
    lag: int | None = 0,
    pending: int = 0,
    pending_idle_ms: int | None = None,
    backlog_age_ms: int | None = None,
) -> StreamGroupSnapshot:
    return StreamGroupSnapshot(
        pending=pending,
        lag=lag,
        oldest_pending_idle_ms=pending_idle_ms,
        oldest_backlog_age_ms=backlog_age_ms,
    )


def runtime(
    *, ready: bool = True, stream_state: StreamGroupSnapshot | None = None
) -> RuntimeInferenceSnapshot:
    return RuntimeInferenceSnapshot(
        answerer=AnswererId.HINA,
        model="hina",
        artifact_id="artifact",
        is_current_deployment=True,
        deployment_available=True,
        worker_ready=ready,
        readiness_ttl_seconds=20 if ready else None,
        stream=stream_state or stream(),
    )


def classify(
    *,
    runtimes: tuple[RuntimeInferenceSnapshot, ...] | None = None,
    event_stream: StreamGroupSnapshot | None = None,
    schema_revision: str = EXPECTED_APPLICATION_SCHEMA_REVISION,
    oldest_pending_outbox_at: datetime | None = None,
    oldest_queued_at: datetime | None = None,
) -> OperationalStatus:
    return InferenceOperationsService._classify(
        database_available=True,
        schema_revision=schema_revision,
        redis_available=True,
        event_stream=event_stream or stream(),
        runtimes=runtimes or (runtime(),),
        oldest_pending_outbox_at=oldest_pending_outbox_at,
        oldest_queued_at=oldest_queued_at,
    )


def test_inference_is_unavailable_when_a_worker_is_not_ready() -> None:
    assert classify(runtimes=(runtime(ready=False),)) is OperationalStatus.UNAVAILABLE


def test_inference_is_unavailable_when_a_consumer_group_is_missing() -> None:
    assert (
        classify(runtimes=(runtime(stream_state=stream(lag=None)),))
        is OperationalStatus.UNAVAILABLE
    )


def test_inference_is_unavailable_when_the_schema_revision_is_stale() -> None:
    assert classify(schema_revision="20260713_0001") is OperationalStatus.UNAVAILABLE


def test_expected_schema_revision_tracks_the_alembic_head() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    scripts = ScriptDirectory.from_config(Config(str(backend_root / "alembic.ini")))
    assert EXPECTED_APPLICATION_SCHEMA_REVISION == scripts.get_current_head()


def test_inference_is_degraded_when_work_stops_progressing() -> None:
    now = datetime.now(timezone.utc)
    assert (
        classify(oldest_queued_at=now - timedelta(minutes=1))
        is OperationalStatus.DEGRADED
    )
    assert (
        classify(oldest_pending_outbox_at=now - timedelta(seconds=11))
        is OperationalStatus.DEGRADED
    )
    assert (
        classify(event_stream=stream(pending=1, pending_idle_ms=10_001))
        is OperationalStatus.DEGRADED
    )


def test_inference_stays_healthy_during_normal_in_flight_work() -> None:
    now = datetime.now(timezone.utc)
    assert (
        classify(
            event_stream=stream(lag=1, backlog_age_ms=100),
            oldest_pending_outbox_at=now - timedelta(seconds=1),
            oldest_queued_at=now - timedelta(seconds=1),
        )
        is OperationalStatus.HEALTHY
    )
