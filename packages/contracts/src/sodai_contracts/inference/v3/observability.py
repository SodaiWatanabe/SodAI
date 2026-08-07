from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from uuid import UUID

from sodai_contracts.inference.v3.messages import GenerationEvent, GenerationJob


@dataclass(frozen=True, slots=True)
class InferenceCorrelation:
    execution_id: UUID
    attempt_id: UUID
    thread_id: UUID
    response_request_id: UUID | None = None
    job_id: UUID | None = None
    model: str | None = None
    artifact_id: str | None = None

    @classmethod
    def from_job(cls, job: GenerationJob) -> InferenceCorrelation:
        return cls(
            execution_id=job.execution_id,
            response_request_id=job.response_request_id,
            attempt_id=job.attempt_id,
            thread_id=job.thread_id,
            job_id=job.id,
            model=job.model,
            artifact_id=job.artifact_id,
        )

    @classmethod
    def from_event(cls, event: GenerationEvent) -> InferenceCorrelation:
        return cls(
            execution_id=event.execution_id,
            attempt_id=event.attempt_id,
            thread_id=event.thread_id,
        )

    def as_log_fields(self) -> dict[str, str]:
        fields = {
            "execution_id": str(self.execution_id),
            "attempt_id": str(self.attempt_id),
            "thread_id": str(self.thread_id),
        }
        optional = {
            "response_request_id": self.response_request_id,
            "job_id": self.job_id,
            "model": self.model,
            "artifact_id": self.artifact_id,
        }
        fields.update(
            {key: str(value) for key, value in optional.items() if value is not None}
        )
        return fields


def log_inference_event(
    logger: logging.Logger,
    level: int,
    event: str,
    correlation: InferenceCorrelation | None = None,
    exc_info: bool = False,
    **fields: object,
) -> None:
    payload: dict[str, object] = {"event": event}
    if correlation is not None:
        payload.update(correlation.as_log_fields())
    payload.update({key: value for key, value in fields.items() if value is not None})
    logger.log(
        level,
        json.dumps(payload, separators=(",", ":"), sort_keys=True),
        exc_info=exc_info,
    )
