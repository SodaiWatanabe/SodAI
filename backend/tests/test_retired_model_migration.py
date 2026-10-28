import os
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import UUID, uuid4

import pytest
from sodai_contracts.inference import (
    FinishReason,
    GenerationEvent,
    GenerationEventType,
    GenerationPhase,
)

from app.db.session import dispose_engine, get_session_factory
from app.domain.answerers import AnswererId, get_answerer
from app.domain.principals import Principal, PrincipalKind
from app.models.platform import GuestSessionModel
from app.repositories.threads import SqlAlchemyThreadRepository
from app.schemas.thread import ThreadResponse
from app.services.thread import AnswererAccessError, ThreadService

MIGRATION_PHASE = os.getenv("SODAI_RETIRED_MODEL_MIGRATION_TEST")
GUEST_ID = UUID("00000000-0000-4000-8000-000000000191")
pytestmark = pytest.mark.skipif(
    MIGRATION_PHASE not in {"prepare", "verify"},
    reason="run around the retired model migration",
)


class RetiredAnswererId(str, Enum):
    HINA = "hina"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_retired_model_history_remains_readable() -> None:
    principal = Principal(PrincipalKind.GUEST, GUEST_ID)
    try:
        async with get_session_factory()() as session:
            repository = SqlAlchemyThreadRepository(session)
            if MIGRATION_PHASE == "prepare":
                now = datetime.now(timezone.utc)
                session.add(
                    GuestSessionModel(
                        id=GUEST_ID,
                        token_hash=uuid4().hex + uuid4().hex,
                        expires_at=now + timedelta(days=1),
                        last_seen_at=now,
                    )
                )
                await session.flush()
                context = await repository.ensure_personal_context(principal)
                current = get_answerer(AnswererId.ASUKA_1_1)
                assert current is not None
                retired = replace(
                    current,
                    id=RetiredAnswererId.HINA,
                    actor_id=UUID("00000000-0000-4000-8000-000000000001"),
                )
                creation = await repository.create_thread_response(
                    principal,
                    context,
                    "過去の会話",
                    retired,
                    execution_target="local:hina",
                    artifact_id="historical",
                    deadline_at=now + timedelta(minutes=5),
                )
                execution = creation.response.execution
                await repository.project_generation_event(
                    GenerationEvent.create(
                        GenerationEventType.STARTED,
                        execution_id=execution.id,
                        attempt_id=execution.attempt_id,
                        thread_id=creation.thread.id,
                        sequence=0,
                        resolved_model="hina@historical",
                        phase=GenerationPhase.ANSWERING,
                    )
                )
                await repository.project_generation_event(
                    GenerationEvent.create(
                        GenerationEventType.COMPLETED,
                        execution_id=execution.id,
                        attempt_id=execution.attempt_id,
                        thread_id=creation.thread.id,
                        sequence=1,
                        content="過去の回答",
                        thinking_content="",
                        thinking_tokens=0,
                        answer_tokens=1,
                        output_tokens=2,
                        finish_reason=FinishReason.STOP,
                    )
                )
                await session.commit()
            else:
                threads = await repository.list(principal)
                assert len(threads) == 1
                assert threads[0].answerer is AnswererId.ASUKA_1_1
                thread = await repository.get(principal, threads[0].id)
                serialized = ThreadResponse.model_validate(thread).model_dump(mode="json")
                assert serialized["answerer"] == "asuka-1.1"
                assert serialized["latest_response"]["requested_answerer"] == "hina"
                assert serialized["entries"][-1]["author"]["name"] == "Hina"
                assert serialized["entries"][-1]["content"] == "過去の回答"
                assert get_answerer("hina") is None
                with pytest.raises(AnswererAccessError):
                    ThreadService.select_answerer(principal, "hina")
    finally:
        await dispose_engine()
