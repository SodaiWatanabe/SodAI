import logging

from fastapi import APIRouter, Depends, Response, status

from app.schemas.health import HealthResponse, InferenceHealthResponse, ReadinessResponse
from app.services.health import HealthService, get_health_service
from app.services.inference.operations import (
    InferenceOperationsService,
    get_inference_operations_service,
)
from app.services.readiness import ReadinessService, get_readiness_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health(
    service: HealthService = Depends(get_health_service),
) -> HealthResponse:
    return service.get_status()


@router.get("/ready", response_model=ReadinessResponse)
async def readiness(
    response: Response,
    service: ReadinessService = Depends(get_readiness_service),
) -> ReadinessResponse:
    try:
        await service.check()
    except Exception as error:
        logger.warning("Backend readiness check failed (%s)", type(error).__name__)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="unavailable")
    return ReadinessResponse(status="ready")


@router.get("/inference", response_model=InferenceHealthResponse)
async def inference_health(
    service: InferenceOperationsService = Depends(get_inference_operations_service),
) -> InferenceHealthResponse:
    snapshot = await service.snapshot()
    return InferenceHealthResponse(status=snapshot.status.value)
