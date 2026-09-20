# Vectra

Vectra is a **Fitness Coach Client Management System** that combines coach account management, client tracking, plan creation, and AI-powered form analysis in a single workspace. It uses a React + Vite frontend, a FastAPI backend, MediaPipe-based pose analysis, Azure Blob Storage for media and generated PDFs, Azure Database for PostgreSQL for persistence, and Azure Queue Storage with a worker for async form-analysis processing.

The current release supports a broader coaching workflow while still shipping **squat analysis first** under the generalized `FormAnalysis` domain.

The current frontend uses a desktop-first **coach workspace** model with a KPI-only dashboard, client-owned operational workflows, and a Slate + Electric Blue visual system with `lucide-react` icons.

## What Vectra Does

- Lets coaches sign up and sign in with email + password
- Lets coaches create and manage their own client roster
- Lets coaches update client profile data and current goal
- Lets coaches upload and review weekly/monthly client progress photos on a timeline
- Lets coaches create **weekly or monthly** nutrition plans
- Lets coaches create **weekly or monthly** workout plans
- Lets coaches download nutrition and workout plans as PDF
- Lets coaches upload client squat videos for async form analysis
- Generates annotated frames, rule-based findings, corrective cues, and coach feedback notes
- Lets coaches review client-specific analysis history and download analysis reports as PDF
- Gives coaches a hover-expanding side navigation rail and a calmer, sport-oriented UI palette

## Current Product Scope

### Coach workspace

- Real coach signup/signin via `/auth/signup` and `/auth/signin`
- Coach-owned clients only; clients do **not** sign in yet
- Dashboard is a KPI and navigation surface only; uploads and dense review workflows live inside client workspaces
- Client profile editing
- Current-goal tracking
- Progress-photo timeline inside the client `Profile` tab
- Client detail workspace split into:
  - `Profile`
  - `Nutrition`
  - `Workout`
  - `Form Analysis`
- `Recent Analysis` remains a cross-client library for reopening past analyses inside the relevant client workspace

### Frontend experience

- React + Vite + TypeScript SPA
- Shared hover-expanding side navigation via `vectra-ui/src/components/SideNav.tsx`
- Shared UI tokens in `vectra-ui/src/theme.ts`
- `lucide-react` icons for navigation, KPI cards, actions, tabs, empty states, and status surfaces
- Slate + Electric Blue palette:
  - slate/navy structure
  - electric-blue primary actions and active states
  - ice-blue muted surfaces
  - gradients used sparingly for page/nav/brand depth

### Plans

- Nutrition plans are managed in a dedicated client `Nutrition` tab
- Workout plans are managed in a dedicated client `Workout` tab
- Nutrition and workout plans are stored as separate versioned snapshots
- Each plan supports:
  - `weekly`
  - `monthly`
- Each plan can be exported as PDF

### Form analysis

- Client-specific form analysis is managed in the client `Form Analysis` tab
- Async queue-driven analysis lifecycle:
  - `queued`
  - `running`
  - `completed`
  - `failed`
- Generalized backend naming now uses **form analyses**
- Squat is the currently implemented analysis type
- Deadlift is a planned extension point, not implemented yet

## Architecture

### Frontend

- React
- TypeScript
- Vite
- lucide-react

### Backend

- FastAPI
- Python
- OpenCV
- MediaPipe Pose Landmarker

### Infra

- Azure Blob Storage for:
  - uploaded videos
  - extracted frames
  - annotated frames
  - client progress photos
  - nutrition plan PDFs
  - workout plan PDFs
- Azure Database for PostgreSQL Flexible Server for:
  - users
  - coaches
  - clients
  - client goals
  - progress photo metadata
  - nutrition plans
  - workout plans
  - form analyses
- Azure Queue Storage for async analysis dispatch
- Azure Container Apps Job or local worker for queue-driven processing
- Poison queue handling through `analysis-jobs-poison` for terminal failures

## Repository Structure

```text
MobilityDetectionSystem/
├── mobility-ai-service/
│   ├── analyzers/
│   ├── config/
│   ├── repositories/
│   ├── services/
│   ├── shared/
│   ├── tests/
│   ├── app.py
│   ├── queue_worker.py
│   ├── Dockerfile.worker
│   └── local.settings.json
├── database/
│   ├── migrations/
│   └── flyway.conf.example
├── vectra-ui/
│   ├── src/
│   └── package.json
├── Specs/
│   ├── BLOB_STORAGE_IMPLEMENTATION.md
│   ├── POSTGRES_IMPLEMENTATION.md
│   ├── QUEUE_STORAGE_IMPLEMENTATION.md
│   ├── UI_PLAN.md
│   ├── UI_PLAN1.md
│   ├── UI_PLAN2.md
│   └── WORKER_ARCHITECTURE.md
└── README.md
```

## Core Data Domains

### Identity and coaching

- `users`
- `coaches`
- `clients`
- `client_goals`
- `client_progress_photos`

### Planning

- `nutrition_plans`
- `workout_plans`

### Analysis

- `form_analyses`

`form_analyses` replaces the older business meaning of `jobs` while preserving the async worker model and historical backfill compatibility.

## Main Request Flows

### Coach auth flow

1. Coach signs up or signs in from the frontend.
2. Backend returns a bearer token plus coach profile data.
3. Frontend stores the token and uses it for protected client, plan, and analysis requests.

### Client and plan flow

1. Coach creates a client.
2. Coach updates profile and current goal.
3. Coach uploads weekly/monthly progress photos with a capture date and optional caption.
4. Coach creates weekly/monthly nutrition plans in the `Nutrition` tab.
5. Coach creates weekly/monthly workout plans in the `Workout` tab.
6. Backend stores progress-photo metadata and each plan as historical snapshots in Postgres.
7. Coach can review prior progress photos and download a PDF version of any saved plan.

### Form analysis flow

1. Coach selects a client in the frontend.
2. Coach opens that client's `Form Analysis` tab.
3. Coach uploads a squat video for that client.
4. Backend stores the uploaded video in Azure Blob Storage.
5. Backend creates a `form_analyses` record with status `queued`.
6. Backend pushes a queue message to Azure Queue Storage.
7. Worker claims the analysis, marks it `running`, and executes the squat pipeline.
8. Frames are extracted and uploaded to Blob Storage.
9. Pose landmarks are analyzed and squat rules are applied.
10. Annotated output frames are uploaded to Blob Storage.
11. Backend stores the structured result JSON and marks the analysis `completed` or `failed`.
12. Frontend polls the analysis endpoint and renders the completed result in the client workspace.

## Worker Behavior

- `app.py` creates form-analysis records and enqueues queue messages.
- `services/job_service.py` currently acts as the form-analysis lifecycle service.
- `services/queue_job_processor.py` validates queue payloads, claims queued analyses, and orchestrates execution.
- `services/job_runner.py` performs the actual squat video processing work.
- `queue_worker.py` is the local and container worker entrypoint.

Retry and poison queue behavior:

- The worker receives messages with a visibility timeout controlled by `ANALYSIS_JOB_VISIBILITY_TIMEOUT`.
- Retryable failures are left on the main queue and retried based on Azure Queue `dequeue_count`.
- Non-retryable failures go straight to `analysis-jobs-poison`.
- When `dequeue_count` reaches `ANALYSIS_JOB_MAX_DEQUEUE_COUNT`, the message is moved to the poison queue and the analysis is marked `failed`.

## Configuration

The backend reads infra settings from environment variables. For local development, `mobility-ai-service/local.settings.json` is auto-loaded by the FastAPI app and the queue worker when those values are not already present in the environment.

### Required Environment Variables

- `AzureWebJobsStorage` or `BLOB_STORAGE_CONNECTION_STRING`
- `QUEUE_STORAGE_CONNECTION_STRING` (optional if `AzureWebJobsStorage` is used)
- `BLOB_UPLOADS_CONTAINER`
- `BLOB_FRAMES_CONTAINER`
- `BLOB_ANNOTATED_FRAMES_CONTAINER`
- `ANALYSIS_JOBS_QUEUE_NAME`
- `ANALYSIS_JOBS_POISON_QUEUE_NAME`
- `ANALYSIS_JOB_VISIBILITY_TIMEOUT`
- `ANALYSIS_JOB_MAX_DEQUEUE_COUNT`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_SSLMODE`

### Flyway Database Migrations

PostgreSQL schema changes are managed by Flyway. The migration files are stored in
`database/migrations/` and are applied before the backend deployment. The backend
does not create or alter tables at runtime.

For local development, start the PostgreSQL Docker container first, copy
`database/flyway.conf.example` to `database/flyway.conf`, and replace its
placeholders with the container connection details. Then run Flyway from the
repository root using the official Docker image:

```bash
docker run --rm \
  -v "$PWD/database:/flyway/project" \
  flyway/flyway:13.0.0 \
  -configFiles=/flyway/project/flyway.conf \
  -workingDirectory=project \
  migrate
```

The local configuration uses `sslmode=disable` by default for a local container.
Use the local database host as reachable from the Flyway container, commonly
`host.docker.internal` when PostgreSQL is published on the host.

The current Azure database is adopted with `baselineOnMigrate=true` at version 1;
Flyway records the baseline without recreating the existing tables. New local
databases execute `V1__baseline.sql`, followed by later migrations. The one-time
`V2__backfill_legacy_jobs.sql` migration preserves the existing compatibility copy
from `jobs` to `form_analyses`.

GitHub Actions reads the Azure JDBC URL and credentials from these repository
secrets:

- `FLYWAY_URL`
- `FLYWAY_USER`
- `FLYWAY_PASSWORD`

The URL should use PostgreSQL JDBC syntax, for example
`jdbc:postgresql://<azure-host>:5432/<database>?sslmode=require`. Do not commit
credentials or populated local Flyway configuration files.

### Optional/Auth Environment Variables

- `AUTH_TOKEN_SECRET`
- `AUTH_TOKEN_EXPIRATION_HOURS`

### Blob Containers Used

- uploads container from `BLOB_UPLOADS_CONTAINER`
- extracted frames container from `BLOB_FRAMES_CONTAINER`
- annotated frames container from `BLOB_ANNOTATED_FRAMES_CONTAINER`
- `client-progress-photos`
- `nutrition-plan-pdfs`
- `workout-plan-pdfs`

## Local Setup

### Prerequisites

- Python 3.11 recommended
- Node.js 18+
- npm

### Local storage and database

Docker Desktop (or Docker Engine with Compose) runs Azurite and PostgreSQL. The API
and worker run on your host machine; no separate Azurite installation is needed.

From the repository root, copy `.env.example` to `.env` if it does not exist and
configure the PostgreSQL values. Then start the infrastructure:

```bash
docker compose up -d --wait
```

To start only storage, use `docker compose up -d --wait azurite`. Apply the local
Flyway migrations described above before using the API with a new database.

Copy `mobility-ai-service/local.settings.json.example` to
`mobility-ai-service/local.settings.json` only if you do not already have one.
For an existing file, set the following value inside `Values` and remove
`BLOB_STORAGE_CONNECTION_STRING` and `QUEUE_STORAGE_CONNECTION_STRING`:

```json
"AzureWebJobsStorage": "UseDevelopmentStorage=true"
```

Both storage clients use this shared setting. In each terminal used to start the
API or worker, clear any previously exported storage settings so the local file
can take effect:

```bash
unset AzureWebJobsStorage BLOB_STORAGE_CONNECTION_STRING QUEUE_STORAGE_CONNECTION_STRING
```

Match the local PostgreSQL settings to `.env`. Configure Azure OpenAI separately
if you need AI plan generation; Azurite replaces only Azure Storage. Existing
cloud data is not copied locally. The development-storage shortcut targets
localhost and is intended for host-run applications, not API/worker containers.

In Azure Storage Explorer, expand **Local & Attached > Storage Accounts >
Emulator - Default Ports**. If needed, add a **Local storage emulator** connection
using HTTP, host `127.0.0.1`, blob port `10000`, queue port `10001`, and table port
`10002`. No Azure sign-in is needed. See the
[Storage Explorer emulator guide](https://learn.microsoft.com/en-us/azure/storage/common/storage-explorer-emulators).

The app creates `analysis-jobs` and `analysis-jobs-poison` when its queue service
initializes. Blob containers appear on first upload: `uploads`, `frames`,
`annotated-frames`, `client-progress-photos`, `nutrition-plan-pdfs`, and
`workout-plan-pdfs`. Start Azurite before the API and worker; restart those
processes if they were started before storage was ready.

Inspect status with `docker compose ps azurite` and logs with
`docker compose logs azurite`. Stop with `docker compose stop azurite`; restart
with `docker compose up -d --wait azurite`. The `azurite_data` volume preserves
blobs and queues across restarts and container recreation.

To deliberately delete **only emulator data**, first stop the API and worker,
then capture the volume name and remove only that volume:

```bash
azurite_container_id=$(docker compose ps -aq azurite)
azurite_volume=$(docker inspect "$azurite_container_id" --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}')
docker compose rm -sf azurite
docker volume rm "$azurite_volume"
docker compose up -d --wait azurite
```

This reset requires an existing Azurite container. PostgreSQL data remains, so
records referencing deleted blobs will no longer load those files. Avoid
`docker compose down -v` for a storage-only reset: it also deletes PostgreSQL data.

### 1. Backend Setup

From `mobility-ai-service`:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Important note:

- The pose model asset is expected at `mobility-ai-service/models/pose_landmarker.task`.

### 2. Start the FastAPI App

From `mobility-ai-service`:

```bash
source venv/bin/activate
uvicorn app:app --reload
```

Backend URL:

```text
http://localhost:8000
```

### 3. Start the Queue Worker

From `mobility-ai-service`:

Run once:

```bash
source venv/bin/activate
python3 queue_worker.py
```

Run in a simple local loop:

```bash
source venv/bin/activate
while true; do python3 queue_worker.py || true; sleep 5; done
```

### 4. Start the Frontend

From `vectra-ui`:

```bash
npm install
npm run dev
```

Frontend URL:

```text
http://localhost:5173
```

### 5. First Local Usage

1. Create a coach account from the login screen.
2. Create a client from the `Clients` tab.
3. Open that client and add profile info, current goal, and progress photos in `Profile`.
4. Create nutrition plans from the client `Nutrition` tab.
5. Create workout plans from the client `Workout` tab.
6. Upload and review squat video analyses from the client `Form Analysis` tab.
7. Use `Dashboard` for KPI summaries and navigation shortcuts.

## API Endpoints

### Health

- `GET /`

### Auth

- `POST /auth/signup`
- `POST /auth/signin`
- `GET /auth/me`

Legacy compatibility:

- `POST /login`

### Clients

- `GET /clients`
- `POST /clients`
- `GET /clients/{client_id}`
- `PUT /clients/{client_id}`
- `POST /clients/{client_id}/goals`
- `GET /clients/{client_id}/progress-photos`
- `POST /clients/{client_id}/progress-photos`
- `GET /client-progress-photos/{blob_name}`

### Nutrition plans

- `GET /clients/{client_id}/nutrition-plans`
- `POST /clients/{client_id}/nutrition-plans`
- `GET /nutrition-plans/{plan_id}`
- `GET /nutrition-plans/{plan_id}/pdf`

### Workout plans

- `GET /clients/{client_id}/workout-plans`
- `POST /clients/{client_id}/workout-plans`
- `GET /workout-plans/{plan_id}`
- `GET /workout-plans/{plan_id}/pdf`

### Form analysis

- `POST /clients/{client_id}/form-analyses`
- `GET /clients/{client_id}/form-analyses`
- `GET /form-analyses`
- `GET /form-analyses/{analysis_id}`
- `PUT /form-analyses/{analysis_id}/feedback`
- `GET /form-analyses/{analysis_id}/pdf`
- `GET /frames/{filename}`

Legacy compatibility:

- `POST /jobs/squat`
- `GET /jobs`
- `GET /jobs/{job_id}`

## Authentication Notes

- Frontend auth now uses bearer tokens.
- Protected endpoints expect `Authorization: Bearer <token>`.
- PDF download endpoints also support `?token=<token>` so browser-open download links work from the SPA.
- Progress photo image URLs also support `?token=<token>` so authenticated image previews can load inside the SPA.

## Testing

### Backend

```bash
cd mobility-ai-service
./venv/bin/python -m unittest tests.test_side_view_squat_logic tests.test_login_service tests.test_job_service
```

### Frontend

```bash
cd vectra-ui
npm run lint
npm run build
```

## Deployment Notes

- `local.settings.json` is for local development only.
- For Azure deployment, configure the same keys as backend/container environment variables.
- `Dockerfile.worker` builds the worker image that starts `queue_worker.py`.
- Do not rely on checked-in local secrets for production.

### GitHub Actions

The repository currently has separate workflows for backend and frontend deployment.

#### Backend API and worker

Workflow:

```text
.github/workflows/deploy-vectra-api.yml
```

Behavior:

- Runs on `push` to `main` when files under `mobility-ai-service/**` change.
- Can also be started manually with `workflow_dispatch`.
- Runs Flyway migrations before building or pushing backend images.
- Builds and pushes two Docker images to Azure Container Registry:
  - `vectra-api`
  - `vectra-worker`
  - Tags each image with both the Git SHA and `latest`.

#### Database migrations

Workflow:

```text
.github/workflows/database-migrations.yml
```

Behavior:

- Runs on `main` pushes affecting `database/**` and can be started manually.
- Is also reusable by the backend deployment workflow.
- Runs Flyway `info`, `migrate`, and `validate` against the configured Azure database.
- Migration failures prevent the backend images from being published.
- The GitHub runner must be able to reach Azure PostgreSQL. If the database is
  private, use a self-hosted runner or the appropriate private-network routing.

Every future schema change must be added as a new immutable migration such as
`V3__description.sql`; do not edit migrations that have already been applied.

#### Frontend Static Web App

Workflow:

```text
.github/workflows/azure-static-web-apps-black-desert-0265d2900.yml
```

Behavior:

- Runs only for changes under `vectra-ui/**` or the frontend workflow file.
- On pull requests to `main`, it validates the frontend only:
  - `npm ci`
  - `npm run lint`
  - `npm run build`
- On `push` to `main`, it deploys the production Azure Static Web App.
- Pull requests do **not** deploy Static Web App preview or production environments.
- Merging a PR to `main` causes a single frontend production deployment from the resulting `push` event.

## Notes

- Squat is the only currently implemented analysis type.
- The backend naming is moving from `jobs` to `form analyses`; some service names still use `job` for compatibility and lower-risk migration.
- Progress-photo timeline is now available in the client `Profile` tab with upload, timeline grouping, and image preview support.
- Nutrition and workout planning are separate client workspace tabs.
- Client-specific form analysis is the primary analysis workflow; `Recent Analysis` is secondary cross-client browsing.
- Dashboard is intentionally KPI/navigation-only.
- Async processing remains queue-driven and does not rely on DB polling or Azure Functions.
