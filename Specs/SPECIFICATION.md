# Mobility Detection System Specification

## Overview

The Mobility Detection System is a two-part application for analyzing squat videos and presenting coach-friendly feedback.

- The backend service processes uploaded videos, extracts frames, runs pose analysis, classifies camera view, and applies squat-specific movement rules.
- The frontend provides a trainer workspace for uploading a video, reviewing analysis results, and inspecting highlighted frame images.

The current implementation is focused on squat analysis and supports different outputs depending on whether the recording is captured from the side or front view.

## Goals

- Accept a squat video upload from a web interface.
- Analyze the movement using pose landmarks extracted from video frames.
- Detect the most likely camera perspective.
- Return structured squat analysis results that the UI can render directly.
- Surface coach-facing feedback, corrective recommendations, and key visual frames.

## System Components

### Backend

Location: `mobility-ai-service`

Primary responsibilities:

- Receive uploaded video files through FastAPI endpoints.
- Store uploaded videos in the local `uploads` directory.
- Extract video frames.
- Run pose analysis on extracted frames.
- Apply squat analysis rules.
- Generate and serve frame images from `outputs/frames`.

Key backend entry point:

- `mobility-ai-service/app.py`

Key backend modules:

- `analyzers/squat_analyzer.py`
- `shared/frame_extractor.py`
- `shared/pose_analyzer.py`
- `shared/view_classifier.py`
- `rules/squat/rep_detection_rule.py`
- `rules/squat/depth_rule.py`
- `rules/squat/torso_lean_rule.py`
- `rules/squat/knee_tracking_rule.py`
- `rules/squat/feedback_engine.py`
- `rules/squat/recommendation_engine.py`

### Frontend

Location: `vectra-ui`

Primary responsibilities:

- Present a login gate for the trainer workspace.
- Allow the user to upload a video file.
- Submit the file to the backend squat-analysis endpoint.
- Render returned metrics, recommendations, and frames.
- Highlight an important rep or a knee-tracking frame depending on detected view.

Key frontend entry points:

- `vectra-ui/src/App.tsx`
- `vectra-ui/src/pages/DashboardPage.tsx`
- `vectra-ui/src/services/squatApi.ts`
- `vectra-ui/src/types/squat.ts`

## Functional Scope

### Included

- Single video upload for squat analysis.
- Squat analysis endpoint at `POST /analyze/squat`.
- Legacy general analysis endpoint at `POST /analyze`.
- Side-view squat analysis:
  - rep detection
  - depth classification
  - torso lean classification
  - representative bottom-frame images per rep
- Front-view squat analysis:
  - knee tracking evaluation
  - representative knee-analysis frame
- Text feedback and corrective recommendations.
- Snapshot image serving through `/frames/...`.

### Not Included

- User authentication backed by a server or database.
- Persistent storage for users, sessions, or reports.
- Multi-exercise analysis beyond squat.
- Production-grade job queueing or asynchronous background processing.
- Cloud file storage.
- Versioned API contracts.
- Audit logging, analytics, or role-based access control.

## User Flow

1. A trainer opens the frontend application.
2. The trainer logs in using the current demo login flow.
3. The trainer uploads a squat video.
4. The frontend sends the file to the backend using multipart form data.
5. The backend stores the file locally and extracts frames.
6. Pose analysis runs across extracted frames.
7. The squat analyzer classifies the video as side view, front view, or unknown confidence output.
8. Rule engines produce movement findings, recommendations, and frames.
9. The frontend renders the analysis and highlights the most relevant frame.

## API Specification

### `GET /`

Purpose:

- Health-style confirmation that the backend is running.

Response:

```json
{
  "message": "Vectra AI Service Running..."
}
```

### `POST /analyze/squat`

Purpose:

- Accept a squat video file and return structured squat analysis.

Request:

- Content type: `multipart/form-data`
- Field name: `file`
- Accepted input: a video file supported by the local processing pipeline

Success response shape:

```json
{
  "status": "Video processed",
  "analysis_type": "squat",
  "filename": "example.mp4",
  "frames_extracted": 0,
  "pose_frames_detected": 0,
  "squat_analysis": {
    "video_view": "side_view",
    "confidence": "medium",
    "message": "This video appears to be a side-view squat recording.",
    "supported_analysis": ["rep_detection", "depth", "torso_lean"],
    "unsupported_analysis": ["knee_tracking"],
    "recommendation": "This video is detected as side view. Rep count, depth, and torso lean are available. Upload a front-view squat video to analyze knee tracking."
  }
}
```

Primary top-level response fields:

- `status`: processing status text
- `analysis_type`: currently `squat`
- `filename`: original uploaded filename
- `frames_extracted`: total extracted frames
- `pose_frames_detected`: frames where pose landmarks were detected
- `squat_analysis`: structured analysis payload

### `POST /analyze`

Purpose:

- Legacy prototype endpoint for older mobility-analysis experiments.

Status:

- Maintained for reference but not the primary product path.

## Squat Analysis Contract

### Common Fields

The `squat_analysis` object may include:

- `video_view`: `side_view`, `front_view`, or `unknown`
- `confidence`: classifier confidence string
- `message`: human-readable view message
- `supported_analysis`: list of active analyses for the detected view
- `unsupported_analysis`: list of analyses not available for the detected view
- `recommendation`: next-step guidance for the user
- `feedback`: structured coach-facing summary and recommendations
- `corrective_recommendations`: issue-based intervention guidance
- `frames`: frame image references generated by the backend

### Side-View Analysis

When the system identifies a side-view squat video, it should provide:

- `squat_detected`
- `rep_count`
- `movement_range`
- `reps`
- `rep_depths`
- `rep_torso_lean`
- `frames.rep_frames`

Supported side-view analyses:

- rep detection
- depth assessment
- torso lean assessment

Unsupported side-view analysis:

- knee tracking

### Front-View Analysis

When the system identifies a front-view squat video, it should provide:

- `knee_tracking`
- `frames.knee_frame`

Supported front-view analysis:

- knee tracking

Unsupported front-view analyses may include:

- rep detection
- depth assessment
- torso lean assessment

### Snapshot Contract

Side-view frames:

- One image may be generated for each detected rep.
- Each rep frame includes:
  - `rep_number`
  - `frame`
  - `image_path`

Front-view frame:

- One highlighted frame may be generated for knee tracking review.
- The frame includes:
  - `frame`
  - `image_path`

All frame image paths are expected to be served by the backend under `/frames/...`.

## Frontend Behavior Specification

### Login

The current login behavior is a local demo flow:

- Username: `admin`
- Password: `admin`

This is a UI-only gate and is not validated by the backend.

### Dashboard

The dashboard should:

- allow video selection via file input
- submit the selected file to the squat-analysis endpoint
- show loading state while analysis is in progress
- show an error message if the request fails
- render a summary panel using `squat_analysis.feedback.summary`
- show coach recommendations and issue highlights
- display a key frame image based on detected view
- allow rep inspection for side-view analysis

### Frontend-to-Backend Integration

The current frontend service target is:

- `http://localhost:8000/analyze/squat`

The frontend also expects frame images to be available from:

- `http://localhost:8000/frames/...`

## Non-Functional Requirements

### Performance

- Analysis is currently synchronous within the request lifecycle.
- The system should remain usable for short-form local testing videos.
- Long-running uploads may cause the UI to wait until the backend completes processing.

### Reliability

- The backend should create required local directories if they do not exist.
- Failures during upload or analysis should result in an error surfaced to the frontend.

### Deployment Assumptions

- Backend runs locally on port `8000`.
- Frontend runs locally on port `5173`.
- CORS is currently configured to allow requests from `http://localhost:5173`.

## Data and Storage

The system currently uses local filesystem storage for runtime artifacts:

- uploaded videos: `mobility-ai-service/uploads`
- generated frames: `mobility-ai-service/outputs/frames`
- model asset: `mobility-ai-service/models/pose_landmarker.task`

There is no current database requirement in the implementation.

## Constraints and Risks

- The system is tightly coupled to local filesystem paths and local development ports.
- CORS configuration is limited to a single local frontend origin.
- The UI assumes the backend is reachable at a fixed localhost URL.
- Uploaded and generated files may accumulate over time without cleanup.
- Runtime artifacts and virtual environment files are stored inside the project tree.
- Error handling and validation behavior are minimal for production use.

## Recommended Future Enhancements

- Add environment-based API configuration for the frontend.
- Add backend configuration management for allowed origins and storage paths.
- Introduce persistent report storage and retrieval.
- Add authentication and user/session management.
- Support additional mobility exercises beyond squat.
- Add background job processing for long videos.
- Add automated cleanup or retention policies for uploads and frame images.
- Document supported video formats and size limits explicitly.
- Add formal API schema validation and OpenAPI examples.

## Acceptance Criteria

A working implementation satisfies this specification when:

- the frontend can upload a squat video to the backend
- the backend processes the file without manual intervention
- the system returns a structured squat-analysis payload
- the frontend renders the returned analysis without requiring mock data
- side-view videos produce rep/depth/torso outputs with rep frames
- front-view videos produce knee-tracking output with a highlighted frame
- user-facing recommendations are included in the response payload

## Document Status

- Version: 1.0
- Status: Initial implementation specification
- Scope basis: current local codebase as of 2026-04-16
