from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

SCHEMA_VERSION = 2
MAX_GENERATION_TURNS = 32
MAX_GENERATION_INPUT_BYTES = 64 * 1024
INFERENCE_ATTEMPT_LOCK_SECONDS = 60
INFERENCE_JOB_CLAIM_IDLE_MS = 90_000
MIN_INFERENCE_JOB_TIMEOUT_SECONDS = 120


class InferenceSpeaker(str, Enum):
    PARTNER = "partner"
    SELF = "self"


class GenerationEventType(str, Enum):
    STARTED = "started"
    DELTA = "delta"
    HEARTBEAT = "heartbeat"
    COMPLETED = "completed"
    FAILED = "failed"


class FinishReason(str, Enum):
    STOP = "stop"
    LENGTH = "length"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class GenerationTurn:
    speaker: InferenceSpeaker
    content: str

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("generation turn content cannot be blank")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> GenerationTurn:
        return cls(
            speaker=InferenceSpeaker(_required_string(value, "speaker")),
            content=_required_string(value, "content"),
        )


@dataclass(frozen=True, slots=True)
class GenerationOptions:
    max_output_tokens: int = 128
    temperature: float = 0.85

    def __post_init__(self) -> None:
        if not 1 <= self.max_output_tokens <= 512:
            raise ValueError("max_output_tokens must be between 1 and 512")
        if not 0 < self.temperature <= 2:
            raise ValueError("temperature must be greater than 0 and at most 2")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> GenerationOptions:
        return cls(
            max_output_tokens=int(value.get("max_output_tokens", 128)),
            temperature=float(value.get("temperature", 0.85)),
        )


@dataclass(frozen=True, slots=True)
class GenerationJob:
    id: UUID
    execution_id: UUID
    response_request_id: UUID
    attempt_id: UUID
    thread_id: UUID
    answerer_actor_id: UUID
    model: str
    artifact_id: str
    turns: tuple[GenerationTurn, ...]
    options: GenerationOptions
    requested_at: datetime
    deadline: datetime

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("generation model cannot be blank")
        if not self.artifact_id.strip():
            raise ValueError("artifact_id cannot be blank")
        if not self.turns:
            raise ValueError("generation job must contain at least one turn")
        if len(self.turns) > MAX_GENERATION_TURNS:
            raise ValueError(
                f"generation job cannot exceed {MAX_GENERATION_TURNS} turns"
            )
        input_bytes = sum(len(turn.content.encode("utf-8")) for turn in self.turns)
        if input_bytes > MAX_GENERATION_INPUT_BYTES:
            raise ValueError(
                f"generation job input cannot exceed {MAX_GENERATION_INPUT_BYTES} bytes"
            )
        if self.turns[-1].speaker is not InferenceSpeaker.PARTNER:
            raise ValueError("generation job must end with a partner turn")
        if self.requested_at.tzinfo is None:
            raise ValueError("requested_at must be timezone-aware")
        if self.deadline.tzinfo is None:
            raise ValueError("deadline must be timezone-aware")
        if self.deadline <= self.requested_at:
            raise ValueError("deadline must be after requested_at")

    @classmethod
    def create(
        cls,
        *,
        execution_id: UUID,
        response_request_id: UUID,
        attempt_id: UUID,
        thread_id: UUID,
        answerer_actor_id: UUID,
        model: str,
        artifact_id: str,
        turns: tuple[GenerationTurn, ...],
        options: GenerationOptions | None = None,
        deadline: datetime,
    ) -> GenerationJob:
        requested_at = datetime.now(timezone.utc)
        return cls(
            id=uuid4(),
            execution_id=execution_id,
            response_request_id=response_request_id,
            attempt_id=attempt_id,
            thread_id=thread_id,
            answerer_actor_id=answerer_actor_id,
            model=model,
            artifact_id=artifact_id,
            turns=turns,
            options=options or GenerationOptions(),
            requested_at=requested_at,
            deadline=deadline,
        )

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "id": str(self.id),
                "execution_id": str(self.execution_id),
                "response_request_id": str(self.response_request_id),
                "attempt_id": str(self.attempt_id),
                "thread_id": str(self.thread_id),
                "answerer_actor_id": str(self.answerer_actor_id),
                "model": self.model,
                "artifact_id": self.artifact_id,
                "turns": [
                    {"speaker": turn.speaker.value, "content": turn.content}
                    for turn in self.turns
                ],
                "options": asdict(self.options),
                "requested_at": self.requested_at.isoformat(),
                "deadline": self.deadline.isoformat(),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, payload: str | bytes) -> GenerationJob:
        value = _json_object(payload)
        _require_schema_version(value)
        turns = value.get("turns")
        if not isinstance(turns, list):
            raise ValueError("turns must be an array")
        options = value.get("options", {})
        if not isinstance(options, dict):
            raise ValueError("options must be an object")
        return cls(
            id=UUID(_required_string(value, "id")),
            execution_id=UUID(_required_string(value, "execution_id")),
            response_request_id=UUID(_required_string(value, "response_request_id")),
            attempt_id=UUID(_required_string(value, "attempt_id")),
            thread_id=UUID(_required_string(value, "thread_id")),
            answerer_actor_id=UUID(_required_string(value, "answerer_actor_id")),
            model=_required_string(value, "model"),
            artifact_id=_required_string(value, "artifact_id"),
            turns=tuple(GenerationTurn.from_dict(turn) for turn in turns),
            options=GenerationOptions.from_dict(options),
            requested_at=datetime.fromisoformat(
                _required_string(value, "requested_at")
            ),
            deadline=datetime.fromisoformat(_required_string(value, "deadline")),
        )


@dataclass(frozen=True, slots=True)
class GenerationEvent:
    id: UUID
    type: GenerationEventType
    execution_id: UUID
    attempt_id: UUID
    sequence: int
    thread_id: UUID
    occurred_at: datetime
    resolved_model: str | None = None
    delta: str | None = None
    content: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: FinishReason | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        if self.sequence < 0:
            raise ValueError("event sequence cannot be negative")
        if self.type is GenerationEventType.STARTED and not self.resolved_model:
            raise ValueError("started event requires resolved_model")
        if self.type is GenerationEventType.DELTA:
            if self.delta is None:
                raise ValueError("delta event requires delta")
        if self.type is GenerationEventType.COMPLETED:
            if self.content is None or self.finish_reason is None:
                raise ValueError("completed event requires content and finish_reason")
        if self.type is GenerationEventType.FAILED and not self.error_code:
            raise ValueError("failed event requires error_code")

    @classmethod
    def create(
        cls,
        event_type: GenerationEventType,
        *,
        execution_id: UUID,
        attempt_id: UUID,
        sequence: int,
        thread_id: UUID,
        **values: Any,
    ) -> GenerationEvent:
        return cls(
            id=uuid4(),
            type=event_type,
            execution_id=execution_id,
            attempt_id=attempt_id,
            sequence=sequence,
            thread_id=thread_id,
            occurred_at=datetime.now(timezone.utc),
            **values,
        )

    def to_json(self) -> str:
        value = {
            "schema_version": SCHEMA_VERSION,
            "id": str(self.id),
            "type": self.type.value,
            "execution_id": str(self.execution_id),
            "attempt_id": str(self.attempt_id),
            "sequence": self.sequence,
            "thread_id": str(self.thread_id),
            "occurred_at": self.occurred_at.isoformat(),
            "resolved_model": self.resolved_model,
            "delta": self.delta,
            "content": self.content,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "finish_reason": self.finish_reason.value if self.finish_reason else None,
            "error_code": self.error_code,
        }
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_json(cls, payload: str | bytes) -> GenerationEvent:
        value = _json_object(payload)
        _require_schema_version(value)
        finish_reason = value.get("finish_reason")
        return cls(
            id=UUID(_required_string(value, "id")),
            type=GenerationEventType(_required_string(value, "type")),
            execution_id=UUID(_required_string(value, "execution_id")),
            attempt_id=UUID(_required_string(value, "attempt_id")),
            sequence=_required_int(value, "sequence"),
            thread_id=UUID(_required_string(value, "thread_id")),
            occurred_at=datetime.fromisoformat(_required_string(value, "occurred_at")),
            resolved_model=_optional_string(value, "resolved_model"),
            delta=_optional_string(value, "delta"),
            content=_optional_string(value, "content"),
            input_tokens=_optional_int(value, "input_tokens"),
            output_tokens=_optional_int(value, "output_tokens"),
            finish_reason=FinishReason(finish_reason)
            if finish_reason is not None
            else None,
            error_code=_optional_string(value, "error_code"),
        )


def _json_object(payload: str | bytes) -> dict[str, Any]:
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("contract payload must be a JSON object")
    return value


def _require_schema_version(value: dict[str, Any]) -> None:
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported inference contract schema version")


def _required_string(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise ValueError(f"{key} must be a non-empty string")
    return item


def _optional_string(value: dict[str, Any], key: str) -> str | None:
    item = value.get(key)
    if item is None:
        return None
    if not isinstance(item, str):
        raise ValueError(f"{key} must be a string or null")
    return item


def _optional_int(value: dict[str, Any], key: str) -> int | None:
    item = value.get(key)
    if item is None:
        return None
    if isinstance(item, bool) or not isinstance(item, int):
        raise ValueError(f"{key} must be an integer or null")
    return item


def _required_int(value: dict[str, Any], key: str) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int):
        raise ValueError(f"{key} must be an integer")
    return item
