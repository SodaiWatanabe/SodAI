from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest
import torch
from sodai_contracts.inference import (
    FinishReason,
    GenerationJob,
    GenerationOptions,
    GenerationPhase,
    GenerationTurn,
    InferenceSpeaker,
)

from sodai_inference.models.asuka1.engine import Asuka1Engine


class StubModel:
    def __call__(self, *_args, **_kwargs):
        return torch.zeros((1, 1, 128)), None, ()


class StubTokenizer:
    def decode(self, token_ids, **_kwargs):
        return {
            (): "",
            (100,): "考え",
            (101,): "こ",
            (101, 102): "こんにちは",
        }[tuple(token_ids)]


def job() -> GenerationJob:
    return GenerationJob(
        id=UUID(int=10),
        execution_id=UUID(int=1),
        response_request_id=UUID(int=2),
        attempt_id=UUID(int=3),
        thread_id=UUID(int=4),
        answerer_actor_id=UUID(int=5),
        model="asuka-1",
        artifact_id="artifact",
        turns=(GenerationTurn(InferenceSpeaker.PARTNER, "こんにちは"),),
        options=GenerationOptions(max_output_tokens=8, temperature=0.85),
        requested_at=datetime.now(timezone.utc),
        deadline=datetime.now(timezone.utc) + timedelta(minutes=1),
    )


def stub_engine(tokens: list[int]) -> Asuka1Engine:
    engine = Asuka1Engine.__new__(Asuka1Engine)
    engine._device = torch.device("cpu")
    engine._model = StubModel()
    engine._tokenizer = StubTokenizer()
    engine._eot_id = 11
    engine._stop_token_ids = {6}
    values = iter(tokens)
    engine._sample = lambda *_args, **_kwargs: torch.tensor([[next(values)]])
    engine.manifest = SimpleNamespace(artifact_id="artifact")
    return engine


def test_asuka1_separates_thinking_from_answer_at_eot() -> None:
    engine = stub_engine([100, 11, 101, 102, 6])

    steps = list(engine.generate([1, 2], job()))

    assert [step.phase for step in steps] == [
        GenerationPhase.THINKING,
        GenerationPhase.THINKING,
        GenerationPhase.ANSWERING,
        GenerationPhase.ANSWERING,
        GenerationPhase.ANSWERING,
        GenerationPhase.ANSWERING,
    ]
    assert [step.delta for step in steps[:-1]] == ["考え", "", "", "こ", "んにちは"]
    assert steps[1].content == "考え"
    assert steps[1].phase_tokens == 1
    assert steps[-1].content == "こんにちは"
    assert steps[-1].output_tokens == 5
    assert steps[-1].phase_tokens == 2
    assert steps[-1].finish_reason is FinishReason.STOP


def test_asuka1_rejects_generation_without_eot() -> None:
    engine = stub_engine([100, 6])

    with pytest.raises(ValueError, match="before the <\\|eot\\|> boundary"):
        list(engine.generate([1, 2], job()))
