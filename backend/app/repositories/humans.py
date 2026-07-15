from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import and_, exists, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.answerers import AnswererId, get_answerer, get_human_rank_name
from app.domain.humans import (
    BrainState,
    BrainStatus,
    HumanAssignment,
    HumanContextEntry,
)
from app.domain.responses import ResponseStatus
from app.domain.threads import ActorKind
from app.models.humans import (
    HumanClaimModel,
    HumanProfileModel,
    HumanTaskModel,
    HumanWaitEntryModel,
)
from app.models.platform import (
    ActorModel,
    EntryTextContentModel,
    ExecutionModel,
    ResponseContextItemModel,
    ResponseRequestModel,
    SpaceModel,
    ThreadEntryModel,
    ThreadModel,
)
from app.repositories.response_completion import complete_response

HUMAN_MATCH_LOCK_KEY = 0x534F44414903
WAIT_LEASE = timedelta(seconds=30)
CLAIM_LEASE = timedelta(seconds=60)


class HumanClaimNotFoundError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class HumanProjection:
    owner_user_id: UUID
    performer_user_id: UUID | None
    space_id: UUID
    thread_id: UUID
    thread_revision: int
    response_request_id: UUID
    execution_id: UUID
    claim_id: UUID | None
    target_actor_id: UUID
    result_entry_id: UUID | None


@dataclass(frozen=True, slots=True)
class MatchResult:
    expired: tuple[HumanProjection, ...]
    matched: HumanProjection | None


class SqlAlchemyHumanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def state(self, user_id: UUID) -> BrainState:
        profile = await self._session.get(HumanProfileModel, user_id)
        rank_level = profile.rank_level if profile else 1
        assignment = await self._active_assignment(user_id)
        if assignment is not None:
            return BrainState(
                BrainStatus.ASSIGNED,
                rank_level,
                get_human_rank_name(rank_level),
                assignment,
            )
        waiting = await self._session.scalar(
            select(HumanWaitEntryModel.id).where(
                HumanWaitEntryModel.performer_user_id == user_id,
                HumanWaitEntryModel.status == "waiting",
                HumanWaitEntryModel.last_seen_at > datetime.now(timezone.utc) - WAIT_LEASE,
            )
        )
        return BrainState(
            BrainStatus.WAITING if waiting is not None else BrainStatus.IDLE,
            rank_level,
            get_human_rank_name(rank_level),
        )

    async def ready(self, user_id: UUID) -> None:
        await self._lock_matching()
        now = datetime.now(timezone.utc)
        await self._session.execute(
            pg_insert(HumanProfileModel)
            .values(user_id=user_id, rank_level=1, updated_at=now)
            .on_conflict_do_nothing(index_elements=[HumanProfileModel.user_id])
        )
        if not await self._renew_active_claim(user_id, now):
            await self._ensure_wait_entry(user_id, now)
        await self._session.flush()

    async def set_rank(self, user_id: UUID, rank_level: int) -> None:
        if rank_level < 1:
            raise ValueError("Human rank must be positive")
        await self._lock_matching()
        now = datetime.now(timezone.utc)
        await self._session.execute(
            pg_insert(HumanProfileModel)
            .values(user_id=user_id, rank_level=rank_level, updated_at=now)
            .on_conflict_do_update(
                index_elements=[HumanProfileModel.user_id],
                set_={"rank_level": rank_level, "updated_at": now},
            )
        )
        await self._session.execute(
            update(HumanWaitEntryModel)
            .where(
                HumanWaitEntryModel.performer_user_id == user_id,
                HumanWaitEntryModel.status == "waiting",
            )
            .values(rank_level=rank_level)
        )
        await self._session.flush()

    async def stop(self, user_id: UUID) -> BrainState:
        await self._lock_matching()
        now = datetime.now(timezone.utc)
        wait_entry = await self._session.scalar(
            select(HumanWaitEntryModel)
            .where(
                HumanWaitEntryModel.performer_user_id == user_id,
                HumanWaitEntryModel.status == "waiting",
            )
            .with_for_update()
        )
        if wait_entry is not None:
            wait_entry.status = "stopped"
            wait_entry.ended_at = now
        await self._session.flush()
        return await self.state(user_id)

    async def match_once(self) -> MatchResult:
        await self._session.execute(select(func.pg_advisory_xact_lock(HUMAN_MATCH_LOCK_KEY)))
        now = datetime.now(timezone.utc)
        await self._session.execute(
            update(HumanWaitEntryModel)
            .where(
                HumanWaitEntryModel.status == "waiting",
                HumanWaitEntryModel.last_seen_at <= now - WAIT_LEASE,
            )
            .values(status="stale", ended_at=now)
        )
        expired = await self._expire_claims(now)

        prior_claim = exists(
            select(HumanClaimModel.id).where(
                HumanClaimModel.execution_id == HumanTaskModel.execution_id,
                HumanClaimModel.performer_user_id == HumanWaitEntryModel.performer_user_id,
            )
        )
        active_claim = exists(
            select(HumanClaimModel.id).where(
                HumanClaimModel.performer_user_id == HumanWaitEntryModel.performer_user_id,
                HumanClaimModel.status == "active",
            )
        )
        statement = (
            select(
                HumanTaskModel,
                HumanWaitEntryModel,
                ExecutionModel,
                ResponseRequestModel,
                ThreadModel,
                SpaceModel,
            )
            .select_from(HumanTaskModel)
            .join(ExecutionModel, ExecutionModel.id == HumanTaskModel.execution_id)
            .join(
                ResponseRequestModel,
                ResponseRequestModel.id == ExecutionModel.response_request_id,
            )
            .join(ThreadModel, ThreadModel.id == ExecutionModel.thread_id)
            .join(SpaceModel, SpaceModel.id == ThreadModel.space_id)
            .join(
                HumanWaitEntryModel,
                and_(
                    HumanWaitEntryModel.rank_level >= HumanTaskModel.required_rank_level,
                    HumanWaitEntryModel.performer_user_id != SpaceModel.owner_user_id,
                ),
            )
            .where(
                ExecutionModel.status == ResponseStatus.QUEUED.value,
                ResponseRequestModel.status == ResponseStatus.QUEUED.value,
                HumanWaitEntryModel.status == "waiting",
                HumanWaitEntryModel.last_seen_at > now - WAIT_LEASE,
                ~prior_claim,
                ~active_claim,
            )
            .order_by(
                HumanTaskModel.queued_at,
                HumanTaskModel.execution_id,
                HumanWaitEntryModel.ready_at,
                HumanWaitEntryModel.id,
            )
            .limit(1)
            .with_for_update(
                of=(HumanTaskModel, HumanWaitEntryModel),
                skip_locked=True,
            )
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return MatchResult(tuple(expired), None)
        task, waiter, execution, request, thread, space = row
        if space.owner_user_id is None:
            raise RuntimeError("Human tasks require an authenticated thread owner")

        claim = HumanClaimModel(
            id=uuid4(),
            execution_id=task.execution_id,
            wait_entry_id=waiter.id,
            performer_user_id=waiter.performer_user_id,
            status="active",
            claimed_at=now,
            lease_expires_at=now + CLAIM_LEASE,
        )
        self._session.add(claim)
        waiter.status = "matched"
        waiter.ended_at = now
        execution.status = ResponseStatus.RUNNING.value
        execution.started_at = now
        execution.lease_expires_at = now + CLAIM_LEASE
        request.status = ResponseStatus.RUNNING.value
        request.started_at = now
        thread.revision += 1
        thread.updated_at = now
        await self._session.flush()
        return MatchResult(
            tuple(expired),
            self._projection(space, thread, request, execution, claim),
        )

    async def skip(self, user_id: UUID, claim_id: UUID) -> HumanProjection:
        await self._lock_matching()
        row = await self._locked_claim(user_id, claim_id)
        claim, execution, request, thread, space = row
        now = datetime.now(timezone.utc)
        claim.status = "skipped"
        claim.finished_at = now
        execution.status = ResponseStatus.QUEUED.value
        execution.started_at = None
        execution.lease_expires_at = None
        request.status = ResponseStatus.QUEUED.value
        request.started_at = None
        thread.revision += 1
        thread.updated_at = now
        await self._ensure_wait_entry(user_id, now)
        await self._session.flush()
        return self._projection(space, thread, request, execution, claim)

    async def answer(self, user_id: UUID, claim_id: UUID, content: str) -> HumanProjection:
        await self._lock_matching()
        row = await self._locked_claim(user_id, claim_id)
        claim, execution, request, thread, space = row
        now = datetime.now(timezone.utc)
        thread.revision += 1
        thread.updated_at = now
        await complete_response(
            self._session,
            execution,
            request,
            thread,
            content,
            now,
        )
        claim.status = "answered"
        claim.finished_at = now
        await self._ensure_wait_entry(user_id, now)
        await self._session.flush()
        return self._projection(space, thread, request, execution, claim)

    async def _active_assignment(self, user_id: UUID) -> HumanAssignment | None:
        row = (
            await self._session.execute(
                select(
                    HumanClaimModel,
                    ExecutionModel,
                    ResponseRequestModel,
                )
                .join(
                    ExecutionModel,
                    ExecutionModel.id == HumanClaimModel.execution_id,
                )
                .join(
                    ResponseRequestModel,
                    ResponseRequestModel.id == ExecutionModel.response_request_id,
                )
                .where(
                    HumanClaimModel.performer_user_id == user_id,
                    HumanClaimModel.status == "active",
                )
            )
        ).one_or_none()
        if row is None:
            return None
        claim, execution, request = row
        answerer_id = AnswererId(request.requested_answerer)
        answerer = get_answerer(answerer_id)
        if answerer is None:
            raise RuntimeError("Human assignment references an unknown answerer")
        context_rows = (
            await self._session.execute(
                select(
                    ActorModel.kind,
                    EntryTextContentModel.content,
                )
                .select_from(ResponseContextItemModel)
                .join(
                    ThreadEntryModel,
                    and_(
                        ThreadEntryModel.id == ResponseContextItemModel.entry_id,
                        ThreadEntryModel.thread_id == ResponseContextItemModel.thread_id,
                    ),
                )
                .join(ActorModel, ActorModel.id == ThreadEntryModel.author_actor_id)
                .join(
                    EntryTextContentModel,
                    EntryTextContentModel.entry_id == ThreadEntryModel.id,
                )
                .where(ResponseContextItemModel.response_request_id == request.id)
                .order_by(ResponseContextItemModel.ordinal)
            )
        ).all()
        return HumanAssignment(
            claim_id=claim.id,
            execution_id=execution.id,
            answerer_name=answerer.name,
            context=tuple(
                HumanContextEntry(
                    author_kind=ActorKind(kind),
                    content=content,
                )
                for kind, content in context_rows
            ),
        )

    async def _locked_claim(
        self, user_id: UUID, claim_id: UUID
    ) -> tuple[
        HumanClaimModel,
        ExecutionModel,
        ResponseRequestModel,
        ThreadModel,
        SpaceModel,
    ]:
        statement = (
            select(
                HumanClaimModel,
                ExecutionModel,
                ResponseRequestModel,
                ThreadModel,
                SpaceModel,
            )
            .join(ExecutionModel, ExecutionModel.id == HumanClaimModel.execution_id)
            .join(
                ResponseRequestModel,
                ResponseRequestModel.id == ExecutionModel.response_request_id,
            )
            .join(ThreadModel, ThreadModel.id == ExecutionModel.thread_id)
            .join(SpaceModel, SpaceModel.id == ThreadModel.space_id)
            .where(
                HumanClaimModel.id == claim_id,
                HumanClaimModel.performer_user_id == user_id,
                HumanClaimModel.status == "active",
            )
            .with_for_update(
                of=(
                    HumanClaimModel,
                    ExecutionModel,
                    ResponseRequestModel,
                    ThreadModel,
                )
            )
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            raise HumanClaimNotFoundError
        return row

    async def _expire_claims(self, now: datetime) -> list[HumanProjection]:
        statement = (
            select(
                HumanClaimModel,
                ExecutionModel,
                ResponseRequestModel,
                ThreadModel,
                SpaceModel,
            )
            .join(ExecutionModel, ExecutionModel.id == HumanClaimModel.execution_id)
            .join(
                ResponseRequestModel,
                ResponseRequestModel.id == ExecutionModel.response_request_id,
            )
            .join(ThreadModel, ThreadModel.id == ExecutionModel.thread_id)
            .join(SpaceModel, SpaceModel.id == ThreadModel.space_id)
            .where(
                HumanClaimModel.status == "active",
                HumanClaimModel.lease_expires_at <= now,
            )
            .with_for_update(
                of=(HumanClaimModel, ExecutionModel, ResponseRequestModel, ThreadModel),
                skip_locked=True,
            )
        )
        projections: list[HumanProjection] = []
        for claim, execution, request, thread, space in (
            await self._session.execute(statement)
        ).all():
            claim.status = "expired"
            claim.finished_at = now
            execution.status = ResponseStatus.QUEUED.value
            execution.started_at = None
            execution.lease_expires_at = None
            request.status = ResponseStatus.QUEUED.value
            request.started_at = None
            thread.revision += 1
            thread.updated_at = now
            projections.append(self._projection(space, thread, request, execution, claim))
        return projections

    async def _lock_matching(self) -> None:
        await self._session.execute(select(func.pg_advisory_xact_lock(HUMAN_MATCH_LOCK_KEY)))

    async def _renew_active_claim(self, user_id: UUID, now: datetime) -> bool:
        row = (
            await self._session.execute(
                select(HumanClaimModel, ExecutionModel)
                .join(
                    ExecutionModel,
                    ExecutionModel.id == HumanClaimModel.execution_id,
                )
                .where(
                    HumanClaimModel.performer_user_id == user_id,
                    HumanClaimModel.status == "active",
                )
                .with_for_update(of=(HumanClaimModel, ExecutionModel))
            )
        ).one_or_none()
        if row is None:
            return False
        claim, execution = row
        claim.lease_expires_at = now + CLAIM_LEASE
        execution.lease_expires_at = now + CLAIM_LEASE
        return True

    async def _ensure_wait_entry(self, user_id: UUID, now: datetime) -> None:
        wait_entry = await self._session.scalar(
            select(HumanWaitEntryModel)
            .where(
                HumanWaitEntryModel.performer_user_id == user_id,
                HumanWaitEntryModel.status == "waiting",
            )
            .with_for_update()
        )
        if wait_entry is not None and wait_entry.last_seen_at > now - WAIT_LEASE:
            wait_entry.last_seen_at = now
            return
        if wait_entry is not None:
            wait_entry.status = "stale"
            wait_entry.ended_at = now
        profile = await self._session.get(HumanProfileModel, user_id)
        if profile is None:
            raise RuntimeError("Human readiness requires a profile")
        self._session.add(
            HumanWaitEntryModel(
                id=uuid4(),
                performer_user_id=user_id,
                rank_level=profile.rank_level,
                status="waiting",
                ready_at=now,
                last_seen_at=now,
            )
        )

    @staticmethod
    def _projection(
        space: SpaceModel,
        thread: ThreadModel,
        request: ResponseRequestModel,
        execution: ExecutionModel,
        claim: HumanClaimModel,
    ) -> HumanProjection:
        if space.owner_user_id is None:
            raise RuntimeError("Human tasks require an authenticated thread owner")
        return HumanProjection(
            owner_user_id=space.owner_user_id,
            performer_user_id=claim.performer_user_id,
            space_id=space.id,
            thread_id=thread.id,
            thread_revision=thread.revision,
            response_request_id=request.id,
            execution_id=execution.id,
            claim_id=claim.id,
            target_actor_id=request.target_actor_id,
            result_entry_id=execution.result_entry_id,
        )
