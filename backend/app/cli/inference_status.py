from __future__ import annotations

import asyncio

from app.services.inference.operations import get_inference_operations_service


async def _run() -> None:
    snapshot = await get_inference_operations_service().snapshot(use_cache=False)
    database = snapshot.database
    active = ",".join(
        f"{answerer.value}:{count}"
        for answerer, count in sorted(
            database.active_by_answerer.items(), key=lambda item: item[0].value
        )
    )
    oldest = database.oldest_queued_at.isoformat() if database.oldest_queued_at else "-"
    print(f"Inference: {snapshot.status.value}")
    print(
        "Database: "
        f"{'available' if database.available else 'unavailable'} "
        f"revision={database.schema_revision or '-'} "
        f"queued={database.queued} running={database.running} "
        f"failed_1h={database.failed_last_hour} outbox={database.pending_outbox}"
    )
    print(
        "Queue: "
        f"oldest={oldest} "
        f"active={active or '-'}"
    )
    print(
        "Redis: "
        f"{'available' if snapshot.redis_available else 'unavailable'} "
        f"events_pending={snapshot.event_stream.pending} "
        f"events_lag={snapshot.event_stream.lag if snapshot.event_stream.lag is not None else '-'} "
        f"events_pending_idle_ms={snapshot.event_stream.oldest_pending_idle_ms or '-'} "
        f"events_backlog_age_ms={snapshot.event_stream.oldest_backlog_age_ms or '-'}"
    )
    for runtime in snapshot.runtimes:
        readiness_ttl = (
            runtime.readiness_ttl_seconds
            if runtime.readiness_ttl_seconds is not None
            else "-"
        )
        print(
            f"Runtime {runtime.answerer.value}: "
            f"role={'current' if runtime.is_current_deployment else 'pinned-active'} "
            f"artifact={runtime.artifact_id or '-'} "
            f"deployment={'available' if runtime.deployment_available else 'unavailable'} "
            f"worker={'ready' if runtime.worker_ready else 'unavailable'} "
            f"ttl={readiness_ttl} "
            f"pending={runtime.stream.pending} "
            f"lag={runtime.stream.lag if runtime.stream.lag is not None else '-'} "
            f"backlog_age_ms={runtime.stream.oldest_backlog_age_ms or '-'}"
        )


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
