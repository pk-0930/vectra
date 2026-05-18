from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config.local_settings_loader import load_local_settings
from services.auth_service import AuthService
from services.blob_storage_service import BlobStorageService
from services.client_service import ClientService
from services.job_runner import JobRunner
from services.job_service import JobService
from services.pdf_service import PdfService
from services.plan_service import PlanService
from services.queue_service import QueueService
from services.storage_asset_service import StorageAssetService

load_local_settings()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

auth_service = AuthService()
client_service = ClientService()
job_service = JobService()
job_runner = JobRunner()
blob_storage_service = BlobStorageService()
queue_service = QueueService()
plan_service = PlanService()
pdf_service = PdfService()
storage_asset_service = StorageAssetService()


class CoachProfilePayload(BaseModel):
    first_name: str
    last_name: str
    dob: str | None = None
    gender: str | None = None
    mobile: str | None = None
    years_of_experience: int = 0
    associated_gym: str | None = None
    clients_trained: int = 0


class SignUpRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    coach: CoachProfilePayload


class SignInRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str


class CoachResponse(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    dob: str | None
    gender: str | None
    mobile: str | None
    years_of_experience: int
    associated_gym: str | None
    clients_trained: int


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse
    coach: CoachResponse | None


class ClientPayload(BaseModel):
    first_name: str
    last_name: str
    dob: str | None = None
    gender: str | None = None
    height_cm: int | None = None
    weight_kg: int | None = None
    is_active: bool = True


class ClientResponse(BaseModel):
    id: int
    coach_id: int
    first_name: str
    last_name: str
    dob: str | None
    gender: str | None
    height_cm: int | None
    weight_kg: int | None
    is_active: bool
    current_goal_type: str | None
    current_goal_notes: str | None
    created_at: str
    updated_at: str


class GoalPayload(BaseModel):
    goal_type: str
    notes: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class GoalResponse(BaseModel):
    id: int
    client_id: int
    goal_type: str
    notes: str | None
    start_date: str | None
    end_date: str | None
    is_current: bool


class ProgressPhotoResponse(BaseModel):
    id: int
    client_id: int
    blob_name: str
    caption: str | None
    timeline_type: str
    captured_on: str
    created_at: str


class PlanPayload(BaseModel):
    period_type: str
    period_start: str
    period_end: str
    title: str
    content: dict[str, Any]


class PlanResponse(BaseModel):
    id: int
    client_id: int
    period_type: str
    period_start: str
    period_end: str
    title: str
    content: dict[str, Any]
    pdf_blob_name: str | None
    created_by_coach_id: int
    created_at: str
    updated_at: str


class FormAnalysisResponse(BaseModel):
    id: str
    client_id: int | None
    analysis_type: str
    status: str
    original_filename: str
    result: dict | None
    error_message: str | None
    coach_feedback_note: str | None
    created_at: str
    updated_at: str
    started_at: str | None
    completed_at: str | None


class FormAnalysisListResponse(BaseModel):
    analyses: list[FormAnalysisResponse]


class FeedbackPayload(BaseModel):
    coach_feedback_note: str


def build_job_filename(job_id: str, original_filename: str) -> str:
    safe_name = "".join(
        character if character.isalnum() or character in ("_", "-", ".") else "_"
        for character in original_filename
    )
    return f"{job_id}_{safe_name}"


def read_upload_file(file: UploadFile) -> bytes:
    return file.file.read()


def build_form_analysis_response(job: dict) -> FormAnalysisResponse:
    return FormAnalysisResponse(
        id=job["id"],
        client_id=job.get("client_id"),
        analysis_type=job["analysis_type"],
        status=job["status"],
        original_filename=job["original_filename"],
        result=job["result"],
        error_message=job["error_message"],
        coach_feedback_note=job.get("coach_feedback_note"),
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        started_at=job["started_at"],
        completed_at=job["completed_at"],
    )


def get_current_user(
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
) -> dict:
    raw_token = token
    if raw_token is None and authorization and authorization.startswith("Bearer "):
        raw_token = authorization.removeprefix("Bearer ").strip()

    if not raw_token:
        raise HTTPException(status_code=401, detail="Authorization token is required.")

    auth_context = auth_service.get_authenticated_user(raw_token)
    if auth_context is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    if auth_context["coach"] is None:
        raise HTTPException(status_code=403, detail="Coach profile not found.")

    return auth_context


def get_current_coach(auth_context: dict = Depends(get_current_user)) -> dict:
    return auth_context["coach"]


@app.get("/")
def home():
    return {"message": "Vectra AI Service Running..."}


@app.post("/auth/signup", response_model=AuthResponse)
async def sign_up(payload: SignUpRequest):
    try:
        return auth_service.sign_up_coach(
            email=payload.email,
            password=payload.password,
            first_name=payload.coach.first_name,
            last_name=payload.coach.last_name,
            dob=payload.coach.dob,
            gender=payload.coach.gender,
            mobile=payload.coach.mobile,
            years_of_experience=payload.coach.years_of_experience,
            associated_gym=payload.coach.associated_gym,
            clients_trained=payload.coach.clients_trained,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/auth/signin", response_model=AuthResponse)
async def sign_in(payload: SignInRequest):
    try:
        return auth_service.sign_in(email=payload.email, password=payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/auth/me", response_model=AuthResponse)
async def get_me(auth_context: dict = Depends(get_current_user)):
    user = auth_context["user"]
    coach = auth_context["coach"]
    return {
        "access_token": "",
        "token_type": "bearer",
        "user": {"id": user["id"], "email": user["email"]},
        "coach": {
            "id": coach["id"],
            "user_id": coach["user_id"],
            "first_name": coach["first_name"],
            "last_name": coach["last_name"],
            "dob": coach["dob"].isoformat() if coach["dob"] else None,
            "gender": coach["gender"],
            "mobile": coach["mobile"],
            "years_of_experience": coach["years_of_experience"],
            "associated_gym": coach["associated_gym"],
            "clients_trained": coach["clients_trained"],
        },
    }


@app.post("/login", response_model=AuthResponse)
async def legacy_login(payload: SignInRequest):
    return await sign_in(payload)


@app.get("/clients", response_model=list[ClientResponse])
async def list_clients(coach: dict = Depends(get_current_coach)):
    return client_service.list_clients(coach["id"])


@app.post("/clients", response_model=ClientResponse)
async def create_client(payload: ClientPayload, coach: dict = Depends(get_current_coach)):
    return client_service.create_client(coach["id"], payload.model_dump())


@app.get("/clients/{client_id}", response_model=ClientResponse)
async def get_client(client_id: int, coach: dict = Depends(get_current_coach)):
    client = client_service.get_client(client_id, coach["id"])
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")
    return client


@app.put("/clients/{client_id}", response_model=ClientResponse)
async def update_client(client_id: int, payload: ClientPayload, coach: dict = Depends(get_current_coach)):
    client = client_service.update_client(client_id, coach["id"], payload.model_dump())
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")
    return client


@app.post("/clients/{client_id}/goals", response_model=GoalResponse)
async def add_client_goal(client_id: int, payload: GoalPayload, coach: dict = Depends(get_current_coach)):
    try:
        return client_service.add_goal(client_id, coach["id"], payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/clients/{client_id}/progress-photos", response_model=list[ProgressPhotoResponse])
async def list_progress_photos(client_id: int, coach: dict = Depends(get_current_coach)):
    try:
        return client_service.list_progress_photos(client_id, coach["id"])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/clients/{client_id}/progress-photos", response_model=ProgressPhotoResponse)
async def upload_progress_photo(
    client_id: int,
    timeline_type: str = Query(...),
    captured_on: str = Query(...),
    caption: str | None = Query(default=None),
    file: UploadFile = File(...),
    coach: dict = Depends(get_current_coach),
):
    client = client_service.get_client(client_id, coach["id"])
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")

    blob_name = storage_asset_service.upload_progress_photo(
        client_id=client_id,
        filename=file.filename or f"{uuid4()}.jpg",
        data=read_upload_file(file),
        content_type=file.content_type,
    )
    photo = client_service.add_progress_photo(
        client_id,
        coach["id"],
        {
            "blob_name": blob_name,
            "caption": caption,
            "timeline_type": timeline_type,
            "captured_on": captured_on,
        }
    )
    return photo


@app.get("/client-progress-photos/{blob_name:path}")
async def get_progress_photo(blob_name: str, coach: dict = Depends(get_current_coach)):
    try:
        payload, media_type = storage_asset_service.get_progress_photo(blob_name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Progress photo not found: {blob_name}") from exc
    return Response(content=payload, media_type=media_type)


@app.get("/clients/{client_id}/nutrition-plans", response_model=list[PlanResponse])
async def list_nutrition_plans(client_id: int, coach: dict = Depends(get_current_coach)):
    try:
        return plan_service.list_plans("nutrition", coach["id"], client_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/clients/{client_id}/nutrition-plans", response_model=PlanResponse)
async def create_nutrition_plan(client_id: int, payload: PlanPayload, coach: dict = Depends(get_current_coach)):
    try:
        return plan_service.create_plan("nutrition", coach["id"], client_id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/nutrition-plans/{plan_id}", response_model=PlanResponse)
async def get_nutrition_plan(plan_id: int, coach: dict = Depends(get_current_coach)):
    plan = plan_service.get_plan("nutrition", coach["id"], plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Nutrition plan not found.")
    return plan


@app.get("/clients/{client_id}/workout-plans", response_model=list[PlanResponse])
async def list_workout_plans(client_id: int, coach: dict = Depends(get_current_coach)):
    try:
        return plan_service.list_plans("workout", coach["id"], client_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/clients/{client_id}/workout-plans", response_model=PlanResponse)
async def create_workout_plan(client_id: int, payload: PlanPayload, coach: dict = Depends(get_current_coach)):
    try:
        return plan_service.create_plan("workout", coach["id"], client_id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/workout-plans/{plan_id}", response_model=PlanResponse)
async def get_workout_plan(plan_id: int, coach: dict = Depends(get_current_coach)):
    plan = plan_service.get_plan("workout", coach["id"], plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Workout plan not found.")
    return plan


def build_plan_pdf(plan_kind: str, plan: dict) -> bytes:
    lines = [
        f"Period: {plan['period_type']}",
        f"Start: {plan['period_start']}",
        f"End: {plan['period_end']}",
    ]
    for key, value in plan["content"].items():
        lines.append(f"{key}: {value}")
    return pdf_service.render_simple_pdf(f"{plan_kind.title()} Plan - {plan['title']}", lines)


@app.get("/nutrition-plans/{plan_id}/pdf")
async def download_nutrition_plan_pdf(plan_id: int, coach: dict = Depends(get_current_coach)):
    plan = plan_service.get_plan("nutrition", coach["id"], plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Nutrition plan not found.")
    payload = build_plan_pdf("nutrition", plan)
    if not plan.get("pdf_blob_name"):
        blob_name = storage_asset_service.upload_plan_pdf(plan_kind="nutrition", plan_id=plan_id, data=payload)
        plan_service.set_pdf_blob_name("nutrition", plan_id, blob_name)
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="nutrition-plan-{plan_id}.pdf"'},
    )


@app.get("/workout-plans/{plan_id}/pdf")
async def download_workout_plan_pdf(plan_id: int, coach: dict = Depends(get_current_coach)):
    plan = plan_service.get_plan("workout", coach["id"], plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Workout plan not found.")
    payload = build_plan_pdf("workout", plan)
    if not plan.get("pdf_blob_name"):
        blob_name = storage_asset_service.upload_plan_pdf(plan_kind="workout", plan_id=plan_id, data=payload)
        plan_service.set_pdf_blob_name("workout", plan_id, blob_name)
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="workout-plan-{plan_id}.pdf"'},
    )


@app.post("/clients/{client_id}/form-analyses", response_model=FormAnalysisResponse)
async def create_form_analysis(
    client_id: int,
    analysis_type: str = Query(default="squat"),
    file: UploadFile = File(...),
    coach: dict = Depends(get_current_coach),
):
    client = client_service.get_client(client_id, coach["id"])
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")
    if analysis_type != "squat":
        raise HTTPException(status_code=400, detail="Only squat analysis is supported right now.")

    analysis_id = str(uuid4())
    original_filename = file.filename or "upload.mp4"
    stored_filename = build_job_filename(analysis_id, original_filename)
    file_bytes = read_upload_file(file)
    video_blob_name = job_runner.upload_video_for_job(
        job_id=analysis_id,
        stored_filename=stored_filename,
        data=file_bytes,
        content_type=file.content_type,
    )

    analysis = job_service.create_job(
        job_id=analysis_id,
        client_id=client_id,
        analysis_type=analysis_type,
        original_filename=original_filename,
        stored_filename=stored_filename,
        video_blob_name=video_blob_name,
    )
    queue_service.enqueue_analysis_job(job_id=analysis_id, analysis_type=analysis_type)
    return build_form_analysis_response(analysis)


@app.get("/clients/{client_id}/form-analyses", response_model=FormAnalysisListResponse)
async def list_client_form_analyses(
    client_id: int,
    limit: int = 20,
    coach: dict = Depends(get_current_coach),
):
    analyses = job_service.list_jobs(limit=limit, coach_id=coach["id"], client_id=client_id)
    return FormAnalysisListResponse(analyses=[build_form_analysis_response(job) for job in analyses])


@app.get("/form-analyses", response_model=FormAnalysisListResponse)
async def list_form_analyses(limit: int = 20, coach: dict = Depends(get_current_coach)):
    analyses = job_service.list_jobs(limit=limit, coach_id=coach["id"])
    return FormAnalysisListResponse(analyses=[build_form_analysis_response(job) for job in analyses])


@app.get("/form-analyses/{analysis_id}", response_model=FormAnalysisResponse)
async def get_form_analysis(analysis_id: str, coach: dict = Depends(get_current_coach)):
    analysis = job_service.get_job_for_coach(analysis_id, coach["id"])
    if analysis is None:
        raise HTTPException(status_code=404, detail="Form analysis not found.")
    return build_form_analysis_response(analysis)


@app.put("/form-analyses/{analysis_id}/feedback", response_model=FormAnalysisResponse)
async def update_form_analysis_feedback(
    analysis_id: str,
    payload: FeedbackPayload,
    coach: dict = Depends(get_current_coach),
):
    analysis = job_service.get_job_for_coach(analysis_id, coach["id"])
    if analysis is None:
        raise HTTPException(status_code=404, detail="Form analysis not found.")
    updated = job_service.update_feedback(analysis_id, payload.coach_feedback_note)
    if updated is None:
        raise HTTPException(status_code=404, detail="Form analysis not found.")
    return build_form_analysis_response(updated)


@app.get("/form-analyses/{analysis_id}/pdf")
async def download_form_analysis_pdf(analysis_id: str, coach: dict = Depends(get_current_coach)):
    analysis = job_service.get_job_for_coach(analysis_id, coach["id"])
    if analysis is None:
        raise HTTPException(status_code=404, detail="Form analysis not found.")

    lines = [
        f"Analysis type: {analysis['analysis_type']}",
        f"Status: {analysis['status']}",
        f"Filename: {analysis['original_filename']}",
    ]
    if analysis.get("coach_feedback_note"):
        lines.append(f"Coach feedback: {analysis['coach_feedback_note']}")
    if analysis.get("result"):
        lines.append(f"Result summary: {analysis['result'].get('status', 'Completed')}")

    payload = pdf_service.render_simple_pdf("Form Analysis Report", lines)
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="form-analysis-{analysis_id}.pdf"'},
    )


@app.get("/jobs", response_model=FormAnalysisListResponse)
async def legacy_list_jobs(limit: int = 20, coach: dict = Depends(get_current_coach)):
    return await list_form_analyses(limit=limit, coach=coach)


@app.get("/jobs/{job_id}", response_model=FormAnalysisResponse)
async def legacy_get_job(job_id: str, coach: dict = Depends(get_current_coach)):
    return await get_form_analysis(job_id, coach)


@app.post("/jobs/squat", response_model=FormAnalysisResponse)
async def legacy_create_squat_job(
    client_id: int = Query(...),
    file: UploadFile = File(...),
    coach: dict = Depends(get_current_coach),
):
    return await create_form_analysis(client_id=client_id, analysis_type="squat", file=file, coach=coach)


@app.get("/frames/{filename:path}")
async def get_annotated_frame(filename: str):
    try:
        payload, media_type = blob_storage_service.get_annotated_frame(filename)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Annotated frame not found: {filename}") from exc
    return Response(content=payload, media_type=media_type)
