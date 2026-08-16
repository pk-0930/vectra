-- Baseline schema for the current Vectra PostgreSQL database.
-- This migration is executed for new databases. Existing Azure databases are
-- adopted with Flyway baselineOnMigrate at version 1.

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE coaches (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    dob DATE NULL,
    gender TEXT NULL,
    mobile TEXT NULL,
    years_of_experience INT NOT NULL DEFAULT 0,
    associated_gym TEXT NULL,
    clients_trained INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE clients (
    id BIGSERIAL PRIMARY KEY,
    coach_id BIGINT NOT NULL REFERENCES coaches(id) ON DELETE CASCADE,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    dob DATE NULL,
    gender TEXT NULL,
    height_cm INT NULL,
    weight_kg INT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE client_goals (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    goal_type TEXT NOT NULL,
    notes TEXT NULL,
    start_date DATE NULL,
    end_date DATE NULL,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE client_progress_photos (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    blob_name TEXT NOT NULL,
    caption TEXT NULL,
    timeline_type TEXT NOT NULL,
    captured_on DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE nutrition_plans (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    period_type TEXT NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    title TEXT NOT NULL,
    content_json JSONB NOT NULL,
    pdf_blob_name TEXT NULL,
    created_by_coach_id BIGINT NOT NULL REFERENCES coaches(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE workout_plans (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    period_type TEXT NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    title TEXT NOT NULL,
    content_json JSONB NOT NULL,
    pdf_blob_name TEXT NULL,
    created_by_coach_id BIGINT NOT NULL REFERENCES coaches(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE ai_plan_drafts (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    coach_id BIGINT NOT NULL REFERENCES coaches(id) ON DELETE CASCADE,
    plan_kind TEXT NOT NULL,
    status TEXT NOT NULL,
    period_type TEXT NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    title TEXT NOT NULL,
    content_json JSONB NOT NULL,
    source_context_json JSONB NOT NULL,
    generation_preferences_json JSONB NOT NULL,
    coach_prompt TEXT NULL,
    model_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    approved_plan_id BIGINT NULL
);

CREATE TABLE form_analyses (
    id TEXT PRIMARY KEY,
    client_id BIGINT NULL REFERENCES clients(id) ON DELETE SET NULL,
    analysis_type TEXT NOT NULL,
    status TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    video_blob_name TEXT NOT NULL,
    result_json JSONB NULL,
    error_message TEXT NULL,
    coach_feedback_note TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL
);

-- Retained because older deployments and the legacy repository may still
-- contain or reference analysis jobs.
-- TODO: This job has to be deleted. I think it is not used anymore in our workflow.
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    analysis_type TEXT NOT NULL,
    status TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    video_blob_name TEXT NOT NULL,
    result_json JSONB NULL,
    error_message TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL
);
