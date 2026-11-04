BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS model_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version         VARCHAR(80) NOT NULL UNIQUE,
    model_name      VARCHAR(160) NOT NULL,
    task            VARCHAR(80) NOT NULL DEFAULT 'dr_grading',
    label_scheme    JSONB NOT NULL,
    preprocessing   JSONB NOT NULL DEFAULT '{}'::jsonb,
    quality_model   VARCHAR(160),
    grading_model   VARCHAR(160) NOT NULL,
    calibration     JSONB NOT NULL DEFAULT '{}'::jsonb,
    abstention_rule JSONB NOT NULL DEFAULT '{}'::jsonb,
    artifact_digest VARCHAR(160),
    status          VARCHAR(20) NOT NULL DEFAULT 'staging'
                    CHECK (status IN ('staging', 'active', 'retired')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    activated_at    TIMESTAMPTZ,
    CHECK (jsonb_typeof(label_scheme) = 'object'),
    CHECK (jsonb_typeof(preprocessing) = 'object'),
    CHECK (jsonb_typeof(calibration) = 'object'),
    CHECK (jsonb_typeof(abstention_rule) = 'object'),
    CHECK ((status = 'active' AND activated_at IS NOT NULL) OR status <> 'active')
);

CREATE UNIQUE INDEX IF NOT EXISTS one_active_model_version
    ON model_versions (status)
    WHERE status = 'active';

CREATE TABLE IF NOT EXISTS inference_events (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_version_id UUID NOT NULL REFERENCES model_versions(id),
    request_id       UUID NOT NULL UNIQUE,
    outcome          VARCHAR(32) NOT NULL CHECK (outcome IN (
        'graded', 'quality_rejected', 'abstained', 'invalid_input', 'error'
    )),
    predicted_grade  SMALLINT,
    confidence       REAL,
    quality_status   VARCHAR(24) CHECK (quality_status IS NULL OR quality_status IN (
        'acceptable', 'rejected', 'not_assessed'
    )),
    latency_ms       INTEGER CHECK (latency_ms IS NULL OR latency_ms >= 0),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (predicted_grade IS NULL OR predicted_grade BETWEEN 0 AND 4),
    CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    CHECK ((outcome = 'graded' AND predicted_grade IS NOT NULL)
           OR (outcome <> 'graded' AND predicted_grade IS NULL))
);

CREATE INDEX IF NOT EXISTS inference_events_created_at_idx
    ON inference_events (created_at DESC);
CREATE INDEX IF NOT EXISTS inference_events_model_version_idx
    ON inference_events (model_version_id, created_at DESC);

COMMIT;
