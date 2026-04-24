# Vectra

Vectra is a squat video analysis system for coaches and trainers. It combines a React + Vite frontend with a FastAPI backend, MediaPipe-based pose analysis, blob-backed media storage, Postgres-backed job persistence, and queue-driven async processing.

The current product scope is focused on squat analysis.

## What Vectra Does

- Accepts squat videos from the UI
- Classifies the recording as side view, front view, or not sufficient
- Runs side-view analysis for rep detection, depth, and torso lean
- Runs front-view analysis for knee tracking
- Generates annotated analysis frames and serves them through the backend
- Stores media in Azure Blob Storage
- Persists jobs in Azure Database for PostgreSQL
- Dispatches async analysis jobs through Azure Queue Storage and an Azure Function entrypoint
- Includes a simple demo login flow using `admin / admin`

## Architecture

### Frontend

- React
- TypeScript
- Vite

### Backend

- FastAPI
- Python
- OpenCV
- MediaPipe Pose Landmarker

### Infra

- Azure Blob Storage for uploaded videos, extracted frames, and annotated frames
- Azure Database for PostgreSQL Flexible Server for job persistence
- Azure Queue Storage for job dispatch
- Azure Functions queue trigger scaffold for event-driven analysis processing

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
│   ├── function_app.py
│   ├── host.json
│   └── local.settings.json
├── vectra-ui/
│   ├── src/
│   └── package.json
├── Specs/
│   ├── BLOB_STORAGE_IMPLEMENTATION.md
│   ├── POSTGRES_IMPLEMENTATION.md
│   ├── QUEUE_STORAGE_IMPLEMENTATION.md
│   └── ...
└── README.md
```

## Request Flow

1. A user signs in from the frontend.
2. The frontend uploads a squat video to the backend.
3. The backend stores the uploaded video in Azure Blob Storage.
4. The backend creates a job record in Postgres.
5. The backend pushes a queue message to Azure Queue Storage.
6. A queue-triggered worker/function processes the job.
7. Frames are extracted and uploaded to Blob Storage.
8. Pose landmarks are analyzed and squat rules are applied.
9. Annotated output frames are uploaded to Blob Storage.
10. The frontend polls the backend for job status and renders the completed result.

## Analysis Behavior

### Side View

- Rep count
- Bottom frame selection per rep
- Depth status:
  - below parallel
  - at parallel
  - above parallel
- Torso lean status:
  - upright
  - moderate lean
  - excessive lean

### Front View

- Knee tracking status:
  - tracking well
  - mild knee cave
  - moderate knee cave
  - severe knee cave

### Output Frames

- Annotated rep frames for side-view analysis
- An annotated representative frame for front-view knee tracking

## Configuration

The backend now reads infra settings from environment variables. For local Azure Functions runs, these are supplied through `mobility-ai-service/local.settings.json`. For Azure deployment, the same values should be configured as Function App Application Settings.

For local development, `mobility-ai-service/local.settings.json` is now auto-loaded by the FastAPI app, the queue worker, and the Azure Function entrypoint when those values are not already present in the environment.

### Required Environment Variables

- `AzureWebJobsStorage` or `BLOB_STORAGE_CONNECTION_STRING`
- `QUEUE_STORAGE_CONNECTION_STRING` (optional if `AzureWebJobsStorage` is used)
- `BLOB_UPLOADS_CONTAINER`
- `BLOB_FRAMES_CONTAINER`
- `BLOB_ANNOTATED_FRAMES_CONTAINER`
- `ANALYSIS_JOBS_QUEUE_NAME`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_SSLMODE`

## Local Setup

### Prerequisites

- Python 3.11 recommended
- Node.js 18+
- npm
- Azure Functions Core Tools if you want to run the queue-triggered function locally

### 1. Backend Setup

From [`mobility-ai-service`](/Users/padmakumar0930/Vectra/MobilityDetectionSystem/mobility-ai-service):

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Important note:

- The pose model asset is expected at [`mobility-ai-service/models/pose_landmarker.task`](/Users/padmakumar0930/Vectra/MobilityDetectionSystem/mobility-ai-service/models/pose_landmarker.task).

### 2. Start the FastAPI App

From [`mobility-ai-service`](/Users/padmakumar0930/Vectra/MobilityDetectionSystem/mobility-ai-service):

```bash
source venv/bin/activate
uvicorn app:app --reload
```

Backend URL:

```text
http://localhost:8000
```

### 3. Start the Queue-Triggered Function

From [`mobility-ai-service`](/Users/padmakumar0930/Vectra/MobilityDetectionSystem/mobility-ai-service):

```bash
source venv/bin/activate
func start
```

This uses:

- `function_app.py` as the Azure Function entrypoint
- `host.json` for the function host
- `local.settings.json` for local-only environment variables

The same `local.settings.json` file is also used automatically when running `uvicorn app:app --reload` or `python worker.py` locally.

Important note:

- `host.json` configures Azure Queue processing with `"messageEncoding": "none"` because the backend currently enqueues plain JSON text messages rather than Base64-encoded payloads.

### 4. Start the Frontend

From [`vectra-ui`](/Users/padmakumar0930/Vectra/MobilityDetectionSystem/vectra-ui):

```bash
npm install
npm run dev
```

Frontend URL:

```text
http://localhost:5173
```

## API Endpoints

Useful backend endpoints:

- `GET /`
- `POST /login`
- `POST /jobs/squat`
- `GET /jobs/{job_id}`
- `GET /jobs`
- `GET /frames/{filename}`
- `POST /analyze/squat` for direct synchronous processing
- `POST /analyze` for the earlier legacy prototype flow

## Demo Login

```text
username: admin
password: admin
```

Authentication is still demo-only and does not yet use a real user store.

## Testing

### Backend

```bash
cd mobility-ai-service
./venv/bin/python -m unittest tests.test_side_view_squat_logic tests.test_login_service tests.test_job_store
```

### Frontend

```bash
cd vectra-ui
npm run build
```

## Deployment Notes

- `local.settings.json` is for local development only.
- After Azure deployment, configure the same keys as Azure Function App Application Settings.
- Do not rely on checked-in local secrets for production.
- The current Azure Function scaffold is queue-triggered and reuses the same job-processing path as the local worker entrypoint.
- Keep the `host.json` queue extension setting aligned with the current producer format:
  - `"extensions": { "queues": { "messageEncoding": "none" } }`

## Notes

- The current implementation is focused on squat analysis only.
- Authentication is still demo-only.
- Frame annotation is handled in the backend so it can be reused for future lifts or assessments.
- The system now uses event-driven async processing instead of DB polling.
