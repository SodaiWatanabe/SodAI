from fastapi import APIRouter, Depends

from app.schemas.health import HealthResponse
from app.services.health import HealthService, get_health_service

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health(
    service: HealthService = Depends(get_health_service),
) -> HealthResponse:
    return service.get_status()
