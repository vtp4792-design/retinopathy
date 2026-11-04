from dataclasses import dataclass
from typing import Protocol

from PIL import Image


@dataclass(frozen=True)
class QualityDecision:
    acceptable: bool
    score: float


@dataclass(frozen=True)
class GradingDecision:
    grade: int
    label: str
    confidence: float
    uncertainty: str


class QualityService(Protocol):
    def assess(self, image: Image.Image) -> QualityDecision: ...


class GradingService(Protocol):
    def predict(self, image: Image.Image) -> GradingDecision: ...


class ExplanationService(Protocol):
    def explain(self, image: Image.Image, grade: int) -> dict[str, str | None]: ...


class DummyQualityService:
    def assess(self, image: Image.Image) -> QualityDecision:
        # A deterministic CPU fallback. Replace with the trained quality model.
        score = min(1.0, max(0.0, min(image.size) / 512))
        return QualityDecision(acceptable=score >= 0.25, score=score)


class DummyGradingService:
    def predict(self, image: Image.Image) -> GradingDecision:
        brightness = sum(image.resize((1, 1)).convert("L").getdata()) / 255
        grade = min(4, int(brightness * 5))
        confidence = 0.8 if 0.2 < brightness < 0.8 else 0.45
        labels = ("No apparent retinopathy", "Mild", "Moderate", "Severe", "Proliferative")
        uncertainty = "low" if confidence >= 0.75 else "high"
        return GradingDecision(grade, labels[grade], confidence, uncertainty)


class DummyExplanationService:
    def explain(self, image: Image.Image, grade: int) -> dict[str, str | None]:
        return {
            "status": "unavailable",
            "media_type": None,
            "image_base64": None,
            "message": "Explanation is not implemented in the CPU fallback.",
        }
