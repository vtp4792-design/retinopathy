import io
import time
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from .schemas import (
    AbstainedResponse,
    Explanation,
    GradedResponse,
    HealthResponse,
    ModelInfoResponse,
    Prediction,
    PredictionResponse,
    QualityAccepted,
    QualityRejected,
    QualityRejectedResponse,
    QualityForAbstention,
)
from ..core.config import Settings, get_settings
from ..inference.services import (
    DummyExplanationService,
    DummyGradingService,
    DummyQualityService,
)

router = APIRouter(prefix="/api/v1")
NOTICE = "Research prototype only; not for diagnosis or treatment decisions."
LABEL_SCHEME = {
    "0": "No apparent retinopathy",
    "1": "Mild",
    "2": "Moderate",
    "3": "Severe",
    "4": "Proliferative",
}


async def _read_limited(upload: UploadFile, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(1024 * 1024):
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=413, detail="File exceeds configured upload limit.")
        chunks.append(chunk)
    return b"".join(chunks)


def _decode_image(data: bytes, settings: Settings) -> Image.Image:
    try:
        with Image.open(io.BytesIO(data)) as decoded:
            decoded.verify()
        image = Image.open(io.BytesIO(data)).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Unreadable image.") from exc
    if image.width < settings.min_image_width or image.height < settings.min_image_height:
        image.close()
        raise HTTPException(status_code=422, detail="Image dimensions are too small.")
    return image


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/model-info", response_model=ModelInfoResponse)
def model_info(settings: Annotated[Settings, Depends(get_settings)]) -> ModelInfoResponse:
    return ModelInfoResponse(
        model_version=settings.model_version,
        task="dr_grading",
        label_scheme=LABEL_SCHEME,
        notice=NOTICE,
    )


@router.post("/predictions", response_model=PredictionResponse)
async def predict(
    file: Annotated[UploadFile, File(...)],
    include_explanation: Annotated[bool, Form()] = False,
    settings: Settings = Depends(get_settings),
) -> PredictionResponse:
    request_id = uuid4()
    if file.content_type not in settings.supported_media_types:
        raise HTTPException(status_code=415, detail="Upload a supported retinal image format.")

    data: bytes | None = None
    image: Image.Image | None = None
    started = time.perf_counter()
    try:
        data = await _read_limited(file, settings.max_upload_bytes)
        image = _decode_image(data, settings)
        quality = DummyQualityService().assess(image)
        if not quality.acceptable:
            return QualityRejectedResponse(
                request_id=request_id,
                status="quality_rejected",
                quality=QualityRejected(status="rejected", reason_code="LOW_QUALITY"),
                next_step="Please obtain a suitable image or request human review.",
                model_version=settings.model_version,
                notice=NOTICE,
            )

        result = DummyGradingService().predict(image)
        if result.confidence < settings.confidence_threshold:
            return AbstainedResponse(
                request_id=request_id,
                status="abstained",
                quality=QualityForAbstention(status="acceptable"),
                abstention={
                    "reason_code": "LOW_CONFIDENCE",
                    "message": "The model did not return a grade for this image.",
                },
                next_step="Human review is required.",
                model_version=settings.model_version,
                notice=NOTICE,
            )

        explanation = (
            DummyExplanationService().explain(image, result.grade)
            if include_explanation
            else {"status": "not_requested", "media_type": None, "image_base64": None, "message": None}
        )
        return GradedResponse(
            request_id=request_id,
            status="graded",
            quality=QualityAccepted(status="acceptable", score=quality.score),
            prediction=Prediction(
                grade=result.grade,
                label=result.label,
                confidence=result.confidence,
                uncertainty=result.uncertainty,
            ),
            explanation=Explanation(**explanation),
            model_version=settings.model_version,
            notice=NOTICE,
        )
    finally:
        if image is not None:
            image.close()
        data = None
        await file.close()
