from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import torch
from sodai_contracts.inference import (
    FinishReason,
    GenerationJob,
    GenerationOptions,
    GenerationTurn,
    InferenceSpeaker,
)

from sodai_inference.models.hina.engine import HinaEngine


class StubModel:
    def __init__(self, tokens: list[int]) -> None:
        self._tokens = iter(tokens)

    def __call__(self, _sequence: torch.Tensor) -> torch.Tensor:
        logits = torch.full((1, 1, 128), float("-inf"))
        logits[0, 0, next(self._tokens)] = 0
        return logits


class StubTokenizer:
    @staticmethod
    def decode(_token_ids, **_kwargs) -> str:
        return "\ufffd"


def job() -> GenerationJob:
    now = datetime.now(timezone.utc)
    return GenerationJob(
        id=UUID(int=10),
        execution_id=UUID(int=1),
        response_request_id=UUID(int=2),
        attempt_id=UUID(int=3),
        thread_id=UUID(int=4),
        answerer_actor_id=UUID(int=5),
        model="hina",
        artifact_id="artifact",
        turns=(GenerationTurn(InferenceSpeaker.PARTNER, "こんにちは"),),
        options=GenerationOptions(max_output_tokens=2, temperature=0.85),
        requested_at=now,
        deadline=now + timedelta(minutes=1),
    )


def test_hina_final_decoder_flush_excludes_the_stop_token() -> None:
    engine = HinaEngine.__new__(HinaEngine)
    engine._device = torch.device("cpu")
    engine._model = StubModel([100, 6])
    engine._tokenizer = StubTokenizer()
    engine._stop_token_ids = {6}
    engine.manifest = SimpleNamespace(artifact_id="artifact")

    steps = list(engine.generate([1, 2], job()))

    assert len(steps) == 2
    final_delta, terminal = steps
    assert final_delta.delta == "\ufffd"
    assert final_delta.output_tokens == 2
    assert final_delta.phase_tokens == 1
    assert terminal.output_tokens == 2
    assert terminal.phase_tokens == 1
    assert terminal.finish_reason is FinishReason.STOP
