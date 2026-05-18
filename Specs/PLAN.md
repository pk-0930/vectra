# Fitness Coach Client Management System — Product Direction Plan

## Summary
Evolve the current squat-analysis MVP into a **coach-only client management platform** with three integrated domains: **coach account management**, **client/program management**, and **form analysis**. Keep the current async analysis pipeline and Azure storage architecture, but refactor the product model so form analysis becomes one feature inside a broader coaching workspace.

The first release should support:
- Real coach signup/signin with email + password
- Coach-owned clients
- Client profile, goals, and progress photo timeline
- Versioned weekly/monthly nutrition and workout plans
- PDF export for plans and analyses
- Form analysis generalized at the domain/model level, while **shipping squat flow first**
- One persisted coach feedback note per analysis, editable and included in exports

## Key Changes

### 1) Domain and data model
Use a normalized coach-owned model instead of extending the current demo login flow.

**Core tables/entities**
- `users`: `id`, `email` (unique), `password_hash`, `created_at`, `updated_at`
- `coaches`: `id`, `user_id` (unique FK), `first_name`, `last_name`, `dob`, `gender`, `mobile`, `years_of_experience`, `associated_gym`, `clients_trained`, `created_at`, `updated_at`
- `clients`: `id`, `coach_id` (FK), `first_name`, `last_name`, `dob`, `gender`, `height_cm`, `weight_kg`, `created_at`, `updated_at`, `is_active`
- `client_goals`: `id`, `client_id`, `goal_type`, `notes`, `start_date`, `end_date`, `is_current`
- `client_progress_photos`: `id`, `client_id`, `blob_name`, `caption`, `timeline_type`, `captured_on`, `created_at`
- `nutrition_plans`: `id`, `client_id`, `period_type`, `period_start`, `period_end`, `title`, `content_json`, `pdf_blob_name`, `created_by_coach_id`, `created_at`, `updated_at`
- `workout_plans`: `id`, `client_id`, `period_type`, `period_start`, `period_end`, `title`, `content_json`, `pdf_blob_name`, `created_by_coach_id`, `created_at`, `updated_at`

**Form analysis**
Replace the `jobs` business concept with `form_analyses`, but preserve async-processing fields needed by the worker:
- `id` (text/uuid string to match current queue/blob usage)
- `client_id` (FK)
- `analysis_type` (`squat`, later extensible to `deadlift`)
- `status` (`queued`, `running`, `completed`, `failed`)
- `original_filename`, `stored_filename`, `video_blob_name`
- `result_json`, `error_message`
- `coach_feedback_note`
- `created_at`, `updated_at`, `started_at`, `completed_at`

**Important modeling decisions**
- Do **not** keep `nutrition_plan_id` / `workout_plan_id` on `clients`; plans are historical snapshots, so client→plans is one-to-many.
- Do **not** keep `goal` only on `clients`; use a separate `client_goals` history table to support changing goals over time.
- Treat progress photos as a separate timeline entity, not fields on `clients`.
- Store plan bodies as **structured JSON snapshots** in v1, not plain text, so UI rendering and PDF output use the same source of truth.

### 2) Backend architecture and API direction
Refactor the FastAPI backend from MVP endpoints into coach-scoped resource APIs.

**Auth**
- Replace `/login` demo auth with:
  - `POST /auth/signup`
  - `POST /auth/signin`
  - `GET /auth/me`
- Use password hashing for stored credentials.
- Use token-based auth for the SPA; all business endpoints are coach-scoped from the authenticated user.

**Coach/client management**
- `GET /clients`
- `POST /clients`
- `GET /clients/{client_id}`
- `PUT /clients/{client_id}`
- `POST /clients/{client_id}/goals`
- `GET /clients/{client_id}/progress-photos`
- `POST /clients/{client_id}/progress-photos`

**Plans**
- `GET /clients/{client_id}/nutrition-plans`
- `POST /clients/{client_id}/nutrition-plans`
- `GET /nutrition-plans/{plan_id}`
- `GET /nutrition-plans/{plan_id}/pdf`
- `GET /clients/{client_id}/workout-plans`
- `POST /clients/{client_id}/workout-plans`
- `GET /workout-plans/{plan_id}`
- `GET /workout-plans/{plan_id}/pdf`

**Form analysis**
- `POST /clients/{client_id}/form-analyses`
- `GET /clients/{client_id}/form-analyses`
- `GET /form-analyses/{analysis_id}`
- `PUT /form-analyses/{analysis_id}/feedback`
- `GET /form-analyses/{analysis_id}/pdf`
- Keep the existing queue/worker orchestration pattern, but rename service/repository concepts from `job` to `form_analysis`.

**Migration strategy**
- Add new tables rather than in-place semantic overloading where possible.
- Migrate the current `jobs` table to `form_analyses` via a one-time schema migration or dual-read transition layer.
- Recommended approach: create `form_analyses` with the new shape, backfill from `jobs`, switch API/service code, then remove `jobs` only after verification.
- Keep current Azure Blob and Queue usage patterns; only rename payload semantics from `job_id` to `analysis_id` if done consistently across API, queue worker, and storage paths.

### 3) Frontend product structure
Replace the current single dashboard demo with a coach workspace SPA.

**Primary navigation**
- Dashboard
- Clients
- Client Detail
- Nutrition Plans
- Workout Plans
- Form Analysis Library
- Settings/Profile

**Key screens**
- Auth: signup + signin
- Client list: searchable coach-owned roster
- Client detail: profile, current goal, progress photo timeline, recent plans, recent analyses
- Nutrition/workout plan editor: create snapshot for weekly or monthly period; view prior plans for the same client
- Form analysis upload/review: upload video under a selected client, poll async status, view result, save coach note, export PDF
- Analysis history: per-client and coach-wide recent analyses

**Frontend state direction**
- Replace local session-storage “logged in” toggle with authenticated API session/token handling.
- Generalize current squat-only types into `FormAnalysis` response types while keeping squat-specific result rendering under the `squat` analysis subtype.
- Reuse the existing analysis polling UX pattern, but move it under client-scoped analysis workflows.

## Public Interfaces / Types
Introduce these explicit shared contracts:
- `Gender`: `male | female | other`
- `GoalType`: `weight_gain | weight_loss | strength_training | performance_improvement`
- `PlanPeriodType`: `weekly | monthly`
- `FormAnalysisType`: `squat | deadlift`
- `FormAnalysisStatus`: `queued | running | completed | failed`

Response models should separate:
- generic analysis metadata (`id`, `client_id`, `analysis_type`, `status`, timestamps, feedback note)
- analysis result payload (`result_json`) with subtype-specific result schema, starting with squat

## Test Plan
- Auth: signup success, duplicate email rejection, signin success/failure, protected endpoint access
- Authorization: coach cannot access another coach’s clients, plans, photos, or analyses
- Client lifecycle: create client, update profile, add goal, add progress photo, list timeline
- Plan lifecycle: create weekly plan, create monthly plan, retrieve historical plans in descending period order, generate/download PDF
- Form analysis lifecycle: create queued analysis, worker marks running/completed/failed, fetch completed result, save/edit coach note, export PDF with note
- Migration: existing `jobs` rows backfill correctly into `form_analyses` without breaking current blob references
- Frontend: auth flow, client creation, historical plan browsing, analysis polling, feedback note persistence, PDF download actions

## Assumptions and defaults
- V1 is **coach-only**; clients do not sign in.
- Coach auth is **email + password** with hashed passwords.
- Nutrition/workout plans are **versioned snapshots**, one record per weekly/monthly period.
- Coach feedback on form analysis is **one saved editable note per analysis**.
- Form analysis is generalized in naming/schema now, but **only squat is fully implemented in the first release**; deadlift remains a planned enum value and extension point.
- Progress photos are stored in Azure Blob Storage and referenced from Postgres by blob name/path.
- PDF generation uses stored snapshot data and analysis result payloads; PDFs are downloadable artifacts, with optional blob persistence for reuse.

## Newly Created Blob Container for Reference
- client-progress-photos
- nutrition-plan-pdfs
- workout-plan-pdfs

These blob containers can be used to store the client progress photos, nutrition and workout plan pdfs respectively.
