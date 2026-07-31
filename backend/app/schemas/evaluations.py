from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.responses import ResponseEvaluationValue


class SetResponseEvaluationRequest(BaseModel):
    value: ResponseEvaluationValue


class ResponseEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    execution_id: UUID
    value: ResponseEvaluationValue
    created_at: datetime
    updated_at: datetime
