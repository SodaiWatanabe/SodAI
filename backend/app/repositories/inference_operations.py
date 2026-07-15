from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.answerers import AnswererId
from app.domain.inference_jobs import GENERATION_OUTBOX_TOPIC
from app.domain.inference_operations import DatabaseInferenceSnapshot
from app.models.platform import ExecutionModel, ModelExecutionModel, OutboxEventModel


class InferenceOperationsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def snapshot(self) -> DatabaseInferenceSnapshot:
        now = datetime.now(timezone.utc)
        status_counts = dict(
            (
                await self._session.execute(
                    select(ExecutionModel.status, func.count())
                    .join(ModelExecutionModel)
                    .group_by(ExecutionModel.status)
                )
            ).all()
        )
        active_rows = (
            await self._session.execute(
                select(
                    ModelExecutionModel.requested_model,
                    ModelExecutionModel.artifact_id,
                    func.count(),
                )
                .join(ExecutionModel)
                .where(ExecutionModel.status.in_(["queued", "running"]))
                .group_by(
                    ModelExecutionModel.requested_model,
                    ModelExecutionModel.artifact_id,
                )
            )
        ).all()
        active_by_answerer: dict[AnswererId, int] = {}
        active_artifacts: dict[tuple[AnswererId, str], int] = {}
        for answerer, artifact_id, count in active_rows:
            try:
                answerer_id = AnswererId(answerer)
            except ValueError:
                continue
            active_by_answerer[answerer_id] = (
                active_by_answerer.get(answerer_id, 0) + count
            )
            active_artifacts[(answerer_id, artifact_id)] = count
        failed_last_hour = await self._session.scalar(
            select(func.count())
            .select_from(ExecutionModel)
            .join(ModelExecutionModel)
            .where(
                ExecutionModel.status == "failed",
                ExecutionModel.finished_at >= now - timedelta(hours=1),
            )
        )
        pending_outbox = await self._session.scalar(
            select(func.count())
            .select_from(OutboxEventModel)
            .where(
                OutboxEventModel.published_at.is_(None),
                OutboxEventModel.discarded_at.is_(None),
                OutboxEventModel.topic == GENERATION_OUTBOX_TOPIC,
            )
        )
        oldest_pending_outbox_at = await self._session.scalar(
            select(func.min(OutboxEventModel.created_at)).where(
                OutboxEventModel.published_at.is_(None),
                OutboxEventModel.discarded_at.is_(None),
                OutboxEventModel.topic == GENERATION_OUTBOX_TOPIC,
            )
        )
        oldest_queued_at = await self._session.scalar(
            select(func.min(ExecutionModel.created_at))
            .join(ModelExecutionModel)
            .where(ExecutionModel.status == "queued")
        )
        schema_revision = await self._session.scalar(
            text("SELECT version_num FROM app.alembic_version LIMIT 1")
        )
        return DatabaseInferenceSnapshot(
            available=True,
            schema_revision=schema_revision,
            queued=status_counts.get("queued", 0),
            running=status_counts.get("running", 0),
            failed_last_hour=failed_last_hour or 0,
            pending_outbox=pending_outbox or 0,
            oldest_pending_outbox_at=oldest_pending_outbox_at,
            oldest_queued_at=oldest_queued_at,
            active_by_answerer=active_by_answerer,
            active_artifacts=active_artifacts,
        )


def unavailable_database_snapshot() -> DatabaseInferenceSnapshot:
    return DatabaseInferenceSnapshot(
        available=False,
        schema_revision=None,
        queued=0,
        running=0,
        failed_last_hour=0,
        pending_outbox=0,
        oldest_pending_outbox_at=None,
        oldest_queued_at=None,
        active_by_answerer={},
        active_artifacts={},
    )
