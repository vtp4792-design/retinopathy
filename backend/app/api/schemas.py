from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: UUID


class ErrorResponse(BaseModel):
    error: ErrorDetail


class QualityAccepted(BaseModel):
    status: Literal["acceptable"]
    score: float = Field(ge=0, le=1)


class QualityRejected(BaseModel):
    status: Literal["rejected"]
    reason_code: Literal["LOW_QUALITY"]


class QualityForAbstention(BaseModel):
    status: Literal["acceptable"]


class Prediction(BaseModel):
    grade: int = Field(ge=0, le=4)
    label: str
    confidence: float = Field(ge=0, le=1)
    uncertainty: str


class Explanation(BaseModel):
    status: Literal["available", "not_requested", "unavailable"]
    media_type: str | None = None
    image_base64: str | None = None
    message: str | None = None


class GradedResponse(BaseModel):
    request_id: UUID
    status: Literal["graded"]
    quality: QualityAccepted
    prediction: Prediction
    explanation: Explanation
    model_version: str
    notice: str


class QualityRejectedResponse(BaseModel):
    request_id: UUID
    status: Literal["quality_rejected"]
    quality: QualityRejected
    prediction: Literal[None] = None
    next_step: str
    model_version: str
    notice: str


class AbstainedResponse(BaseModel):
    request_id: UUID
    status: Literal["abstained"]
    quality: QualityForAbstention
    prediction: Literal[None] = None
    abstention: dict[str, str]
    next_step: str
    model_version: str
    notice: str


PredictionResponse = Annotated[
    GradedResponse | QualityRejectedResponse | AbstainedResponse,
    Field(discriminator="status"),
]


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ModelInfoResponse(BaseModel):
    model_version: str
    task: Literal["dr_grading"]
    label_scheme: dict[str, str]
    notice: str
