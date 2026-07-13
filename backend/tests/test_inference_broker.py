import asyncio

import pytest
from sodai_contracts.inference import InferenceNamespace

from app.services.inference.broker import RedisInferenceBroker, StreamBacklog
from app.services.inference.coordinator import reconciliation_is_safe


class FakeRedis:
    def __init__(self):
        self.claim_cursors = []
        self.eval_args = None

    async def xreadgroup(self, **kwargs):
        return [["events", [("20-0", {"payload": "new"})]]]

    async def xautoclaim(self, *args, **kwargs):
        self.claim_cursors.append(kwargs["start_id"])
        next_cursor = "50-0" if len(self.claim_cursors) == 1 else "0-0"
        return [next_cursor, [("10-0", {"payload": "deferred"})], []]

    async def eval(self, *args):
        self.eval_args = args
        return 1


def test_reads_new_and_claimable_events_fairly() -> None:
    redis = FakeRedis()
    broker = RedisInferenceBroker(
        redis,  # type: ignore[arg-type]
        namespace=InferenceNamespace("test:inference"),
        event_consumer="consumer",
        event_claim_idle_ms=2_000,
    )

    messages = asyncio.run(broker.read_events())

    assert [(message.id, message.payload) for message in messages] == [
        ("10-0", "deferred"),
        ("20-0", "new"),
    ]

    asyncio.run(broker.read_events())

    assert redis.claim_cursors == ["0-0", "50-0"]


def test_acknowledging_an_event_also_removes_its_payload() -> None:
    redis = FakeRedis()
    broker = RedisInferenceBroker(
        redis,  # type: ignore[arg-type]
        namespace=InferenceNamespace("test:inference"),
        event_consumer="consumer",
        event_claim_idle_ms=2_000,
    )

    asyncio.run(broker.acknowledge_event("20-0"))

    assert redis.eval_args[1:] == (
        1,
        "test:inference:events:v2",
        "test-inference-projector-v2",
        "20-0",
    )


@pytest.mark.parametrize(
    ("backlog", "deferred_count", "expected"),
    [
        (StreamBacklog(pending=0, lag=0), 0, True),
        (StreamBacklog(pending=1, lag=0), 0, False),
        (StreamBacklog(pending=1, lag=0), 1, True),
        (StreamBacklog(pending=1, lag=1), 1, False),
        (StreamBacklog(pending=0, lag=None), 0, False),
    ],
)
def test_reconciliation_waits_for_uninspected_events_but_not_known_gaps(
    backlog: StreamBacklog, deferred_count: int, expected: bool
) -> None:
    assert reconciliation_is_safe(backlog, deferred_count) is expected
