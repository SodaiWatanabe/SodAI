from fastapi import APIRouter, Depends

from app.schemas.health import HealthResponse, InferenceHealthResponse
from app.services.health import HealthService, get_health_service
from app.services.inference.operations import (
    InferenceOperationsService,
    get_inference_operations_service,
)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health(
    service: HealthService = Depends(get_health_service),
) -> HealthResponse:
    return service.get_status()


@router.get("/inference", response_model=InferenceHealthResponse)
async def inference_health(
    service: InferenceOperationsService = Depends(get_inference_operations_service),
) -> InferenceHealthResponse:
    snapshot = await service.snapshot()
    return InferenceHealthResponse(status=snapshot.status.value)
