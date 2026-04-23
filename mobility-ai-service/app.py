from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
import os
import tempfile
from uuid import uuid4

from analyzers.mobility_analyzer import analyze_mobility
from analyzers.squat_analyzer import SquatAnalyzer
from services.blob_storage_service import BlobStorageService
from services.job_runner import JobRunner
from services.job_store import JobStore
from services.login_service import LoginService
from services.queue_service import QueueService
from shared.frame_extractor import FrameExtractor
from shared.pose_analyzer import PoseAnalyzer

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frame_extractor = FrameExtractor()
pose_analyzer = PoseAnalyzer()
squat_analyzer = SquatAnalyzer()
login_service = LoginService()
job_runner = JobRunner()
job_store = JobStore()
blob_storage_service = BlobStorageService()
queue_service = QueueService()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    authenticated: bool
    message: str
    username: str


class JobSummaryResponse(BaseModel):
    id: str
    analysis_type: str
    status: str
    original_filename: str
    result: dict | None
    error_message: str | None
    created_at: str
    updated_at: str
    started_at: str | None
    completed_at: str | None


class JobListResponse(BaseModel):
    jobs: list[JobSummaryResponse]


def build_job_response(job: dict) -> JobSummaryResponse:
    return JobSummaryResponse(
        id=job["id"],
        analysis_type=job["analysis_type"],
        status=job["status"],
        original_filename=job["original_filename"],
        result=job["result"],
        error_message=job["error_message"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        started_at=job["started_at"],
        completed_at=job["completed_at"],
    )


def build_job_filename(job_id: str, original_filename: str) -> str:
    safe_name = "".join(
        character if character.isalnum() or character in ("_", "-", ".") else "_"
        for character in original_filename
    )
    return f"{job_id}_{safe_name}"


def read_upload_file(file: UploadFile) -> bytes:
    return file.file.read()


@app.get("/")
def home():
    return {"message": "Vectra AI Service Running..."}


@app.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest):
    result = login_service.authenticate(
        username=payload.username,
        password=payload.password,
    )

    if not result["authenticated"]:
        raise HTTPException(status_code=401, detail=result["message"])

    return result


@app.post("/jobs/squat", response_model=JobSummaryResponse)
async def create_squat_job(file: UploadFile = File(...)):
    job_id = str(uuid4())
    original_filename = file.filename or "upload.mp4"
    stored_filename = build_job_filename(job_id, original_filename)
    file_bytes = read_upload_file(file)
    video_blob_name = job_runner.upload_video_for_job(
        job_id=job_id,
        stored_filename=stored_filename,
        data=file_bytes,
        content_type=file.content_type,
    )

    job = job_store.create_job(
        job_id=job_id,
        analysis_type="squat",
        original_filename=original_filename,
        stored_filename=stored_filename,
        video_blob_name=video_blob_name,
    )
    queue_service.enqueue_analysis_job(job_id=job_id, analysis_type="squat")

    return build_job_response(job)


@app.get("/jobs/{job_id}", response_model=JobSummaryResponse)
async def get_job(job_id: str):
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    return build_job_response(job)


@app.get("/jobs", response_model=JobListResponse)
async def list_jobs(limit: int = 20):
    jobs = job_store.list_jobs(limit=limit)
    return JobListResponse(jobs=[build_job_response(job) for job in jobs])


@app.get("/frames/{filename}")
async def get_annotated_frame(filename: str):
    try:
        payload, media_type = blob_storage_service.get_annotated_frame(filename)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Annotated frame not found: {filename}") from exc
    return Response(content=payload, media_type=media_type)

# Legacy prototype endpoint kept for reference from initial gait-analysis experiment
@app.post("/analyze")
async def analyze_video(file: UploadFile = File(...)):
    original_filename = file.filename or "upload.mp4"
    temp_job_id = str(uuid4())
    stored_filename = build_job_filename(temp_job_id, original_filename)
    video_blob_name = job_runner.upload_video_for_job(
        job_id=temp_job_id,
        stored_filename=stored_filename,
        data=read_upload_file(file),
        content_type=file.content_type,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        local_video_path = os.path.join(temp_dir, stored_filename)
        blob_storage_service.download_video_to_file(
            blob_name=video_blob_name,
            destination_path=local_video_path,
        )

        frame_count, frame_folder = frame_extractor.extract_frames_to_folder(
            local_video_path,
            os.path.join(temp_dir, "frames"),
        )

        blob_storage_service.upload_extracted_frames(
            source_directory=frame_folder,
            blob_prefix=f"{temp_job_id}/{os.path.splitext(stored_filename)[0]}",
        )

        pose_results = pose_analyzer.analyze_frames(frame_folder)

        mobility_report = analyze_mobility(pose_results)

        return {
            "status": "Video processed",
            "frames_extracted": frame_count,
            "pose_frames_detected": len(pose_results),
            "mobility_analysis": mobility_report
        }

@app.post("/analyze/squat")
async def analyze_squat_video(file: UploadFile = File(...)):
    original_filename = file.filename or "upload.mp4"
    temp_job_id = str(uuid4())
    stored_filename = build_job_filename(temp_job_id, original_filename)
    video_blob_name = job_runner.upload_video_for_job(
        job_id=temp_job_id,
        stored_filename=stored_filename,
        data=read_upload_file(file),
        content_type=file.content_type,
    )

    return job_runner.run_squat_job(
        video_blob_name=video_blob_name,
        original_filename=original_filename,
        stored_filename=stored_filename,
        job_id=temp_job_id,
    )
