from fastapi import FastAPI, UploadFile, File, HTTPException
import shutil
import os

from analyzers.mobility_analyzer import analyze_mobility

from shared.frame_extractor import FrameExtractor
from shared.pose_analyzer import PoseAnalyzer
from analyzers.squat_analyzer import SquatAnalyzer
from services.login_service import LoginService

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

app.mount("/frames", StaticFiles(directory="outputs/frames"), name="frames")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_FOLDER = "uploads"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

frame_extractor = FrameExtractor()
pose_analyzer = PoseAnalyzer()
squat_analyzer = SquatAnalyzer()
login_service = LoginService()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    authenticated: bool
    message: str
    username: str


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

# Legacy prototype endpoint kept for reference from initial gait-analysis experiment
@app.post("/analyze")
async def analyze_video(file: UploadFile = File(...)):
    
    file_location = f"{UPLOAD_FOLDER}/{file.filename}"

    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Extract frames
    frame_count, frame_folder = frame_extractor.extract_frames(file_location)

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
    file_location = os.path.join(UPLOAD_FOLDER, file.filename)

    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    frame_count, frame_folder = frame_extractor.extract_frames(file_location)
    pose_results = pose_analyzer.analyze_frames(frame_folder)
    squat_report = squat_analyzer.analyze(
        pose_results=pose_results,
        video_path=file_location,
        frames_folder=frame_folder,
    )

    return {
        "status": "Video processed",
        "analysis_type": "squat",
        "filename": file.filename,
        "frames_extracted": frame_count,
        "pose_frames_detected": len(pose_results),
        "squat_analysis": squat_report
    }
