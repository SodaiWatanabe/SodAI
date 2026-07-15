from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.principal import get_principal
from app.domain.principals import Principal, PrincipalKind
from app.repositories.humans import HumanClaimNotFoundError
from app.schemas.human import BrainStateResponse, HumanAnswerRequest
from app.services.human import HumanService, get_human_service

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
