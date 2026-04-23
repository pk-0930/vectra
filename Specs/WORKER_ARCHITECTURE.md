# Worker Implementation

## Overview

Worker implementation to handle video processing in the background with API and container Apps which can poll a Azure Storage Queue when a new video is uploaded.

### First Iteration - API

The first worker slice is now implemented. We have a real async job path in place without breaking the current UI flow.

In the backend, I added a SQLite-backed job store in job_store.py, a shared processing runner in job_runner.py, a polling worker entrypoint in worker.py, and new API endpoints in app.py. The new flow is:

POST /jobs/squat uploads the file, creates a queued job, and returns job_id
GET /jobs/{job_id} returns the job status plus result or error once available
python worker.py polls for queued jobs and processes them in a separate process
I kept POST /analyze/squat working synchronously for now so the current React app does not break while we migrate the frontend to the job-based flow.

That gives the worker architecture immediately, and we can “lift and shift” to Azure Service Bus + Postgres after.

### Second Iteration - UI

The React app now uses the async worker flow. I updated DashboardPage.tsx to create a squat job, poll GET /jobs/{id} every 2 seconds, show queued/running/completed/failed status, and render the completed analysis exactly like before once the job finishes.

I also added a shared frontend API base config in apiConfig.ts, switched squatApi.ts to the new POST /jobs/squat + GET /jobs/{id} endpoints, updated authApi.ts to use the same base URL, and added job response types in squat.ts.

Verification: npm run build passed in vectra-ui.

For this to work end to end locally, we now need both processes running:

API: uvicorn app:app --reload
Worker: python worker.py