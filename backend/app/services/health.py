from app.core.config import Settings, get_settings
from app.schemas.health import HealthResponse


class HealthService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_status(self) -> HealthResponse:
        return HealthResponse(
            status="ok",
            service=self._settings.app_name,
            environment=self._settings.app_env,
        )


def get_health_service() -> HealthService:
    return HealthService(get_settings())
