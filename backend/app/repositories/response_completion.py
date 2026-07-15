from datetime import datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.responses import ResponseStatus
from app.domain.threads import EntryKind
from app.models.platform import (
    EntryTextContentModel,
    ExecutionModel,
    ResponseRequestModel,
    ThreadEntryModel,
    ThreadModel,
)


async def complete_response(
    session: AsyncSession,
    execution: ExecutionModel,
    request: ResponseRequestModel,
    thread: ThreadModel,
    content: str,
    now: datetime,
) -> ThreadEntryModel:
    """Persist one answer through the shared model/Human completion path."""

    last_ordinal = await session.scalar(
        select(func.max(ThreadEntryModel.ordinal)).where(ThreadEntryModel.thread_id == thread.id)
    )
    result = ThreadEntryModel(
        id=uuid4(),
        thread_id=thread.id,
        author_actor_id=request.target_actor_id,
        kind=EntryKind.MESSAGE.value,
        ordinal=(last_ordinal if last_ordinal is not None else -1) + 1,
    )
    result.text = EntryTextContentModel(content=content)
    session.add(result)
    execution.partial_output = content
    execution.status = ResponseStatus.COMPLETED.value
    execution.result_entry_id = result.id
    execution.finished_at = now
    execution.lease_expires_at = None
    request.status = ResponseStatus.COMPLETED.value
    request.finished_at = now
    thread.last_activity_at = now
    return result
