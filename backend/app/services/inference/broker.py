from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import ResponseError
from sodai_contracts.inference import GenerationJob, InferenceNamespace

ACK_AND_DELETE_SCRIPT = """
local acknowledged = redis.call('XACK', KEYS[1], ARGV[1], ARGV[2])
redis.call('XDEL', KEYS[1], ARGV[2])
return acknowledged
"""


@dataclass(frozen=True, slots=True)
class StreamMessage:
    id: str
    payload: str


@dataclass(frozen=True, slots=True)
class StreamBacklog:
    pending: int
    lag: int | None


class RedisInferenceBroker:
    def __init__(
        self,
        redis: Redis,
        *,
        namespace: InferenceNamespace,
        event_consumer: str,
        event_claim_idle_ms: int,
    ) -> None:
        self._redis = redis
        self.namespace = namespace
        self.job_stream = namespace.job_stream
        self.event_stream = namespace.event_stream
        self.event_group = namespace.projector_group
        self.event_consumer = event_consumer
        self.event_claim_idle_ms = event_claim_idle_ms
        self._event_claim_cursor = "0-0"

    async def publish_job(self, job: GenerationJob) -> str:
        return await self._redis.xadd(
            self.namespace.job_stream_for(job.model, job.artifact_id),
            {"payload": job.to_json()},
            maxlen=100_000,
            approximate=True,
        )

    async def publish_cancellation(
        self,
        attempt_id: UUID,
        *,
        ttl_seconds: int,
    ) -> None:
        await self._redis.set(
            self.namespace.attempt_cancellation(attempt_id),
            "1",
            ex=ttl_seconds,
        )

    async def ensure_event_group(self) -> None:
        try:
            await self._redis.xgroup_create(
                self.event_stream,
                self.event_group,
                id="0-0",
                mkstream=True,
            )
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    async def read_events(self) -> list[StreamMessage]:
        streams = await self._redis.xreadgroup(
            groupname=self.event_group,
            consumername=self.event_consumer,
            streams={self.event_stream: ">"},
            count=32,
            block=250,
        )
        new_messages = _stream_messages(streams[0][1]) if streams else []
        claimed = await self._redis.xautoclaim(
            self.event_stream,
            self.event_group,
            self.event_consumer,
            min_idle_time=self.event_claim_idle_ms,
            start_id=self._event_claim_cursor,
            count=32,
        )
        if claimed:
            self._event_claim_cursor = claimed[0]
        claimed_messages = _stream_messages(claimed[1] if len(claimed) > 1 else [])
        return sorted(
            (*new_messages, *claimed_messages), key=lambda message: _stream_id(message.id)
        )

    async def acknowledge_event(self, message_id: str) -> None:
        await self._redis.eval(
            ACK_AND_DELETE_SCRIPT,
            1,
            self.event_stream,
            self.event_group,
            message_id,
        )

    async def event_backlog(self) -> StreamBacklog:
        pending = await self._redis.xpending(self.event_stream, self.event_group)
        pending_count = pending.get("pending", 0) if isinstance(pending, dict) else 0
        groups = await self._redis.xinfo_groups(self.event_stream)
        group = next(
            (item for item in groups if item.get("name") == self.event_group),
            None,
        )
        if group is None:
            return StreamBacklog(pending=pending_count, lag=None)
        lag = group.get("lag")
        return StreamBacklog(
            pending=pending_count,
            lag=lag if isinstance(lag, int) else None,
        )

    async def close(self) -> None:
        await self._redis.aclose()


def _stream_messages(entries: list[tuple[str, dict[str, Any]]]) -> list[StreamMessage]:
    messages: list[StreamMessage] = []
    for message_id, fields in entries:
        payload = fields.get("payload")
        if isinstance(payload, str):
            messages.append(StreamMessage(id=message_id, payload=payload))
    return messages


def _stream_id(value: str) -> tuple[int, int]:
    milliseconds, sequence = value.split("-", maxsplit=1)
    return int(milliseconds), int(sequence)
