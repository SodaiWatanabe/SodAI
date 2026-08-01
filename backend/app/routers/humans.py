from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.auth.principal import get_principal
from app.domain.principals import Principal, PrincipalKind
from app.repositories.human_answers import HumanAnswerNotFoundError
from app.repositories.humans import (
    HumanClaimNotFoundError,
    HumanClaimSkipWindowClosedError,
)
from app.schemas.human import (
    BrainStateResponse,
    HumanAnswerDetailResponse,
    HumanAnswerListResponse,
    HumanAnswerRequest,
    HumanDraftRequest,
    HumanDraftResponse,
)
from app.services.human import HumanService, get_human_service
from app.services.human_answers import (
    HumanAnswerHistoryService,
    get_human_answer_history_service,
)

router = APIRouter(prefix="/human", tags=["human"])


def _user_id(principal: Principal) -> UUID:
    if principal.kind is not PrincipalKind.USER:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required",
        )
    return principal.id


@router.get("/state", response_model=BrainStateResponse)
async def read_brain_state(
    principal: Principal = Depends(get_principal),
    service: HumanService = Depends(get_human_service),
) -> BrainStateResponse:
    return BrainStateResponse.model_validate(
        await service.state(_user_id(principal)), from_attributes=True
    )


@router.get("/answers", response_model=HumanAnswerListResponse)
async def list_human_answers(
    response: Response,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    principal: Principal = Depends(get_principal),
    service: HumanAnswerHistoryService = Depends(get_human_answer_history_service),
) -> HumanAnswerListResponse:
    response.headers["Cache-Control"] = "private, no-store"
    try:
        page = await service.page(_user_id(principal), limit=limit, cursor=cursor)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return HumanAnswerListResponse(items=list(page.items), next_cursor=page.next_cursor)


@router.get("/answers/{execution_id}", response_model=HumanAnswerDetailResponse)
async def read_human_answer(
    execution_id: UUID,
    response: Response,
    principal: Principal = Depends(get_principal),
    service: HumanAnswerHistoryService = Depends(get_human_answer_history_service),
) -> HumanAnswerDetailResponse:
    response.headers["Cache-Control"] = "private, no-store"
    try:
        answer = await service.get(_user_id(principal), execution_id)
    except HumanAnswerNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Human answer not found") from exc
    return HumanAnswerDetailResponse.model_validate(answer, from_attributes=True)


@router.put("/readiness", response_model=BrainStateResponse)
async def become_ready(
    principal: Principal = Depends(get_principal),
    service: HumanService = Depends(get_human_service),
) -> BrainStateResponse:
    return BrainStateResponse.model_validate(
        await service.ready(_user_id(principal)), from_attributes=True
    )


@router.delete("/readiness", response_model=BrainStateResponse)
async def stop_waiting(
    principal: Principal = Depends(get_principal),
    service: HumanService = Depends(get_human_service),
) -> BrainStateResponse:
    return BrainStateResponse.model_validate(
        await service.stop(_user_id(principal)), from_attributes=True
    )


@router.post("/claims/{claim_id}/skip", response_model=BrainStateResponse)
async def skip_claim(
    claim_id: UUID,
    principal: Principal = Depends(get_principal),
    service: HumanService = Depends(get_human_service),
) -> BrainStateResponse:
    try:
        state = await service.skip(_user_id(principal), claim_id)
    except HumanClaimSkipWindowClosedError as exc:
        raise HTTPException(status_code=409, detail="Skip window has closed") from exc
    except HumanClaimNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Active assignment not found") from exc
    return BrainStateResponse.model_validate(state, from_attributes=True)


@router.post("/claims/{claim_id}/answer", response_model=BrainStateResponse)
async def answer_claim(
    claim_id: UUID,
    payload: HumanAnswerRequest,
    principal: Principal = Depends(get_principal),
    service: HumanService = Depends(get_human_service),
) -> BrainStateResponse:
    try:
        state = await service.answer(_user_id(principal), claim_id, payload.content)
    except HumanClaimNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Active assignment not found") from exc
    return BrainStateResponse.model_validate(state, from_attributes=True)


@router.put("/claims/{claim_id}/draft", response_model=HumanDraftResponse)
async def save_claim_draft(
    claim_id: UUID,
    payload: HumanDraftRequest,
    principal: Principal = Depends(get_principal),
    service: HumanService = Depends(get_human_service),
) -> HumanDraftResponse:
    try:
        revision = await service.save_draft(
            _user_id(principal),
            claim_id,
            payload.content,
            payload.revision,
        )
    except HumanClaimNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Active assignment not found") from exc
    return HumanDraftResponse(revision=revision)
