# Retinal ML Prototype: Database Schema and API Specification

## 1. Design assumptions

This specification describes a student prototype for retinal-image quality control and diabetic-retinopathy grading. It is not a clinical service. The service should not return treatment advice or claim diagnostic certainty.

The API processes one image per inference request. The image is held temporarily for inference and is not stored in PostgreSQL or retained by default. The database stores model version metadata and optional de-identified inference audit records, not images. For the first prototype, audit logging can be disabled or configured to store only operational metadata.

**Suggested stack:** PostgreSQL; FastAPI; SQLAlchemy or SQLModel; Pydantic request/response models; a model service that loads a versioned preprocessing, quality-control, and grading pipeline.

## 2. Database schema

### Entity relationship overview

- `model_versions` identifies released versions of the inference pipeline.
- `inference_events` optionally records non-image operational outcomes, each associated with the model version used.
- No patient table, image table, or direct patient identifier is required for the prototype.

### PostgreSQL DDL

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE model_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version         VARCHAR(80) NOT NULL UNIQUE,
    model_name      VARCHAR(160) NOT NULL,
    task             VARCHAR(80) NOT NULL DEFAULT 'dr_grading',
    label_scheme     JSONB NOT NULL,
    preprocessing    JSONB NOT NULL DEFAULT '{}'::jsonb,
    quality_model    VARCHAR(160),
    grading_model    VARCHAR(160) NOT NULL,
    calibration      JSONB NOT NULL DEFAULT '{}'::jsonb,
    abstention_rule  JSONB NOT NULL DEFAULT '{}'::jsonb,
    artifact_digest  VARCHAR(160),
    status           VARCHAR(20) NOT NULL DEFAULT 'staging'
                     CHECK (status IN ('staging', 'active', 'retired')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    activated_at     TIMESTAMPTZ,
    CHECK (jsonb_typeof(label_scheme) = 'object'),
    CHECK (jsonb_typeof(preprocessing) = 'object'),
    CHECK (jsonb_typeof(calibration) = 'object'),
    CHECK (jsonb_typeof(abstention_rule) = 'object')
);

CREATE UNIQUE INDEX one_active_model_version
    ON model_versions (status)
    WHERE status = 'active';

CREATE TABLE inference_events (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_version_id UUID NOT NULL REFERENCES model_versions(id),
    request_id       UUID NOT NULL UNIQUE,
    outcome          VARCHAR(32) NOT NULL
                     CHECK (outcome IN (
                         'graded', 'quality_rejected', 'abstained', 'invalid_input', 'error'
                     )),
    predicted_grade  SMALLINT,
    confidence       REAL,
    quality_status   VARCHAR(24)
                     CHECK (quality_status IS NULL OR quality_status IN (
                         'acceptable', 'rejected', 'not_assessed'
                     )),
    latency_ms       INTEGER CHECK (latency_ms IS NULL OR latency_ms >= 0),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (predicted_grade IS NULL OR predicted_grade BETWEEN 0 AND 4),
    CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    CHECK (
        (outcome = 'graded' AND predicted_grade IS NOT NULL)
        OR (outcome <> 'graded' AND predicted_grade IS NULL)
    )
);

CREATE INDEX inference_events_created_at_idx
    ON inference_events (created_at DESC);
CREATE INDEX inference_events_model_version_idx
    ON inference_events (model_version_id, created_at DESC);
```

### Schema notes

- The `0–4` grade constraint assumes the commonly used five-level ordinal format; change it to match the chosen dataset's documented labels before implementation.
- `label_scheme` should record the exact class-to-label mapping and display text for the model version.
- `calibration` and `abstention_rule` should record the method and validation-selected settings, not patient-specific data.
- `artifact_digest` can hold a hash or immutable identifier for the model package. Do not store model weights in PostgreSQL.
- `inference_events` is optional. Set a retention period, restrict access, and avoid logging uploaded filenames, image bytes, patient names, dates of birth, or free-text clinical notes.
- If a research evaluation requires labels linked to predictions, use a separately governed, de-identified evaluation dataset and keep that analysis outside the production-style inference audit table.

## 3. API conventions

- Base path: `/api/v1`
- Content type for image submission: `multipart/form-data`
- Response format: JSON
- Authentication: optional for a local classroom demo; required for any shared deployment. Use role-based access for administrative model operations.
- Do not send or return patient identifiers. Do not include uploaded image bytes in logs or responses.
- The API response is an experimental model output, not a diagnosis.

### Common error response

```json
{
  "error": {
    "code": "UNSUPPORTED_MEDIA_TYPE",
    "message": "Upload a supported retinal image format.",
    "request_id": "7dca2a10-6464-4c03-bca6-8d395c0c93b6"
  }
}
```

## 4. Endpoint specification

### `GET /api/v1/health`

Liveness check for the API process. It should not reveal secrets, file paths, or detailed infrastructure configuration.

**200 response**

```json
{
  "status": "ok"
}
```

### `GET /api/v1/model-info`

Returns non-sensitive information about the active model and its output label scheme.

**200 response**

```json
{
  "model_version": "prototype-0.1.0",
  "task": "dr_grading",
  "label_scheme": {
    "0": "No apparent retinopathy",
    "1": "Mild",
    "2": "Moderate",
    "3": "Severe",
    "4": "Proliferative"
  },
  "notice": "Research prototype only; not for diagnosis or treatment decisions."
}
```

The label names above are placeholders. Replace them with the selected dataset's documented definitions and ensure the model's training labels match the API display mapping.

### `POST /api/v1/predictions`

Accepts one image, runs input validation, image quality assessment, grading when appropriate, uncertainty/abstention logic, and an explanation method when available. The uploaded image is processed in memory or temporary storage and deleted after processing.

**Request**

`multipart/form-data`

| Field | Type | Required | Description |
|---|---|---:|---|
| `file` | image file | Yes | One retinal fundus image in a supported format. |
| `include_explanation` | boolean | No | Request an explanation image or explanation metadata; defaults to `false`. |

**Graded response — 200**

```json
{
  "request_id": "7dca2a10-6464-4c03-bca6-8d395c0c93b6",
  "status": "graded",
  "quality": {
    "status": "acceptable",
    "score": 0.94
  },
  "prediction": {
    "grade": 2,
    "label": "Moderate",
    "confidence": 0.78,
    "uncertainty": "moderate"
  },
  "explanation": {
    "status": "available",
    "media_type": "image/png",
    "image_base64": null,
    "message": "Explanation is an approximate model-visualization aid, not clinical evidence."
  },
  "model_version": "prototype-0.1.0",
  "notice": "Research prototype only; not for diagnosis or treatment decisions."
}
```

For a browser UI, prefer returning an explanation through a short-lived, access-controlled endpoint rather than embedding a large base64 image in JSON. If no explanation is requested or generated, return `"explanation": {"status": "not_requested"}` or `"status": "unavailable"`.

**Quality rejection — 200**

```json
{
  "request_id": "7dca2a10-6464-4c03-bca6-8d395c0c93b6",
  "status": "quality_rejected",
  "quality": {
    "status": "rejected",
    "reason_code": "LOW_QUALITY"
  },
  "prediction": null,
  "next_step": "Please obtain a suitable image or request human review.",
  "model_version": "prototype-0.1.0",
  "notice": "Research prototype only; not for diagnosis or treatment decisions."
}
```

**Uncertainty abstention — 200**

```json
{
  "request_id": "7dca2a10-6464-4c03-bca6-8d395c0c93b6",
  "status": "abstained",
  "quality": {
    "status": "acceptable"
  },
  "prediction": null,
  "abstention": {
    "reason_code": "LOW_CONFIDENCE",
    "message": "The model did not return a grade for this image."
  },
  "next_step": "Human review is required.",
  "model_version": "prototype-0.1.0",
  "notice": "Research prototype only; not for diagnosis or treatment decisions."
}
```

**Errors**

- `400 Bad Request`: unreadable image or malformed request.
- `413 Payload Too Large`: file exceeds configured upload limit.
- `415 Unsupported Media Type`: unsupported file type.
- `422 Unprocessable Entity`: valid request structure but invalid image dimensions or content.
- `429 Too Many Requests`: configured request limit exceeded.
- `500 Internal Server Error`: unexpected processing failure; return a request ID but no stack trace or sensitive details.
- `503 Service Unavailable`: model not loaded or inference service unavailable.

### `GET /api/v1/predictions/{request_id}` (optional)

Only implement this if the application needs to retrieve an audit record. It returns operational metadata, not the original image. Restrict access and apply retention controls.

**200 response**

```json
{
  "request_id": "7dca2a10-6464-4c03-bca6-8d395c0c93b6",
  "status": "graded",
  "predicted_grade": 2,
  "quality_status": "acceptable",
  "model_version": "prototype-0.1.0",
  "created_at": "2026-01-15T12:00:00Z"
}
```

**404 response:** record not found or unavailable to the caller. Do not expose whether another user's request ID exists.

### `GET /api/v1/admin/model-versions` (optional)

Restricted endpoint for authorized administrators to list model versions and their activation status. Do not expose secrets or downloadable model weights.

### `POST /api/v1/admin/model-versions/{version_id}/activate` (optional)

Restricted operation to activate a validated model version. Require an explicit administrative role and record the activation event. For a student prototype, model activation may instead be managed through a deployment configuration file.

## 5. Pydantic response model outline

```python
from typing import Literal
from pydantic import BaseModel, Field

class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str

class QualityResult(BaseModel):
    status: Literal["acceptable", "rejected", "not_assessed"]
    score: float | None = Field(default=None, ge=0, le=1)
    reason_code: str | None = None

class PredictionResult(BaseModel):
    grade: int = Field(ge=0, le=4)
    label: str
    confidence: float = Field(ge=0, le=1)
    uncertainty: str

class PredictionResponse(BaseModel):
    request_id: str
    status: Literal["graded", "quality_rejected", "abstained"]
    quality: QualityResult
    prediction: PredictionResult | None = None
    model_version: str
    notice: str
```

In production code, use a discriminated union of separate `GradedResponse`, `QualityRejectedResponse`, and `AbstainedResponse` models so invalid combinations—such as a rejected image with a predicted grade—cannot be serialized.

## 6. Processing sequence

1. FastAPI validates request size and accepted media types.
2. The API decodes the file and checks basic image dimensions and readability.
3. The preprocessing pipeline converts the image to the model's expected representation.
4. The quality model returns an acceptable/rejected outcome; rejected images stop here.
5. The grading model generates class scores for acceptable images.
6. Calibration and the validation-selected abstention rule determine whether to return a grade or abstain.
7. If requested and supported, the explanation module creates an approximate visualization.
8. The API returns a typed response with model version and non-diagnostic notice.
9. Temporary image data is removed. If audit logging is enabled, only the allow-listed operational fields are written.

## 7. Minimum acceptance tests

- Reject unsupported file types and over-limit uploads without storing the file.
- Reject unreadable or invalid-dimension images with a stable error response.
- Confirm that quality-rejected images never receive a severity grade.
- Confirm that low-confidence predictions return `abstained`, not a grade.
- Confirm that successful responses identify the model version and include the non-diagnostic notice.
- Confirm that explanation output is optional and that explanation failure does not silently change the predicted grade.
- Confirm that uploaded image bytes, filenames, and request payloads are absent from application logs and database records.
- Confirm that database constraints reject invalid grades, confidence values, and outcome/prediction combinations.
- Confirm that the optional audit endpoint requires authorization and does not return image content.
