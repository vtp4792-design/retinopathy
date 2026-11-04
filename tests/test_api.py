import io

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.main import app


client = TestClient(app)


def image_bytes(size=(128, 128), color=(128, 128, 128)) -> bytes:
    image = Image.new("RGB", size, color)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_health_and_model_info() -> None:
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    assert client.get("/api/v1/model-info").json()["task"] == "dr_grading"


def test_low_quality_never_contains_prediction() -> None:
    response = client.post(
        "/api/v1/predictions",
        files={"file": ("retina.png", image_bytes(size=(64, 64)), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "quality_rejected"
    assert body["prediction"] is None


def test_graded_response_has_prediction() -> None:
    response = client.post(
        "/api/v1/predictions",
        files={"file": ("retina.png", image_bytes(), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "graded"
    assert 0 <= body["prediction"]["grade"] <= 4


def test_low_confidence_abstains_without_prediction() -> None:
    response = client.post(
        "/api/v1/predictions",
        files={"file": ("retina.png", image_bytes(color=(0, 0, 0)), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "abstained"
    assert body["abstention"]["reason_code"] == "LOW_CONFIDENCE"
    assert body["prediction"] is None


def test_unsupported_type_is_rejected() -> None:
    response = client.post(
        "/api/v1/predictions",
        files={"file": ("retina.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 415
