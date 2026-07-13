from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    environment: str


class InferenceHealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unavailable"]
