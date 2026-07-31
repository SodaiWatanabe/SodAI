from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.principal import get_principal
from app.domain.principals import Principal
from app.repositories.evaluations import (
    ResponseEvaluationNotFoundError,
    ResponseEvaluationNotReadyError,
)
from app.schemas.evaluations import (
    ResponseEvaluationResponse,
    SetResponseEvaluationRequest,
)
from app.services.evaluations import (
    ResponseEvaluationService,
    get_response_evaluation_service,
)

router = APIRouter(tags=["collaboration"])


@router.put(
    "/executions/{execution_id}/evaluation",
    response_model=ResponseEvaluationResponse,
)
async def set_response_evaluation(
    execution_id: UUID,
    payload: SetResponseEvaluationRequest,
    principal: Principal = Depends(get_principal),
    service: ResponseEvaluationService = Depends(get_response_evaluation_service),
) -> ResponseEvaluationResponse:
    try:
        evaluation = await service.set(principal, execution_id, payload.value)
    except ResponseEvaluationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Execution not found") from exc
    except ResponseEvaluationNotReadyError as exc:
        raise HTTPException(
            status_code=409,
            detail="Response evaluation requires a completed execution",
        ) from exc
    return ResponseEvaluationResponse.model_validate(evaluation, from_attributes=True)


@router.delete(
    "/executions/{execution_id}/evaluation",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def clear_response_evaluation(
    execution_id: UUID,
    principal: Principal = Depends(get_principal),
    service: ResponseEvaluationService = Depends(get_response_evaluation_service),
) -> None:
    try:
        await service.clear(principal, execution_id)
    except ResponseEvaluationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Execution not found") from exc
    except ResponseEvaluationNotReadyError as exc:
        raise HTTPException(
            status_code=409,
            detail="Response evaluation requires a completed execution",
        ) from exc
