from typing import Any
from functools import lru_cache
from datetime import date
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config.local_settings_loader import load_local_settings
from services.auth_service import AuthService
from repositories.pt_repository import PtRepository
from services.pt_service import PtService
from repositories.membership_repository import MembershipRepository
from services.membership_service import MembershipService
from repositories.gym_repository import GymRepository
from services.gym_service import GymService, CatalogueChanged, MAX_IMAGE_BYTES
from services.gym_registration_media import registration_qr, reception_poster
from repositories.identity_repository import IdentityRepository
from repositories.billing_repository import BillingRepository
from services.billing_service import BillingService
from services.identity_service import IdentityService, GENERIC_MESSAGE
from repositories.access_repository import AccessRepository, AccessDenied, ResourceNotFound
from fastapi.responses import JSONResponse
from services.ai_plan_generation_service import PlanDraftGenerationError
from services.ai_plan_draft_service import AiPlanDraftService
from services.blob_storage_service import BlobStorageService
from services.client_service import ClientService
from services.job_runner import JobRunner
from services.job_service import JobService
from services.pdf_service import PdfService
from services.plan_service import PlanService
from services.queue_service import QueueService
from services.storage_asset_service import StorageAssetService
from services.web_workspace_service import WebWorkspaceService

load_local_settings()

from config.features import analysis_enabled, public_features

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def require_analysis():
    if not analysis_enabled():
        raise HTTPException(status_code=404, detail="Form analysis is disabled.")


@app.get("/features")
def features(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return public_features()


auth_service = AuthService()
identity_service = IdentityService(IdentityRepository(auth_service.repository.config), auth_service.security_service)
billing_service = BillingService(BillingRepository(auth_service.repository.config))
gym_service = GymService(GymRepository(auth_service.repository.config), billing_service)
membership_service = MembershipService(MembershipRepository(auth_service.repository.config))
pt_service = PtService(PtRepository(auth_service.repository.config))
client_service = ClientService()
job_service = JobService()
blob_storage_service = BlobStorageService()
plan_service = PlanService()
ai_plan_draft_service = AiPlanDraftService()
pdf_service = PdfService()
storage_asset_service = StorageAssetService()
web_workspace_service = WebWorkspaceService()


@lru_cache(maxsize=1)
def get_analysis_runner():
    return JobRunner()


@lru_cache(maxsize=1)
def get_analysis_queue():
    return QueueService()


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
    password: str = Field(min_length=12, max_length=256)
    coach: CoachProfilePayload


class SignInRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    email_verified: bool = False
    verification_required: bool = False


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


class OrganizationContextResponse(BaseModel):
    organization_id: int
    name: str
    organization_type: str
    relationship_id: int
    staff_roles: list[str]
    client_id: int | None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse
    coach: CoachResponse | None
    organizations: list[OrganizationContextResponse]


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


class PlanDraftCreatePayload(BaseModel):
    plan_kind: str
    period_type: str
    period_start: str
    period_end: str
    dietary_preference: str | None = None
    coach_prompt: str | None = None


class PlanDraftUpdatePayload(BaseModel):
    period_type: str
    period_start: str
    period_end: str
    title: str
    content: dict[str, Any]
    coach_prompt: str | None = None


class PlanDraftRegeneratePayload(BaseModel):
    period_type: str
    period_start: str
    period_end: str
    dietary_preference: str | None = None
    coach_prompt: str | None = None


class PlanDraftResponse(BaseModel):
    id: int
    client_id: int
    coach_id: int
    plan_kind: str
    status: str
    period_type: str
    period_start: str
    period_end: str
    title: str
    content: dict[str, Any]
    source_context: dict[str, Any]
    generation_preferences: dict[str, Any]
    coach_prompt: str | None
    model_name: str
    created_at: str
    updated_at: str
    approved_plan_id: int | None


class PlanDraftApprovalResponse(BaseModel):
    draft: PlanDraftResponse
    plan: PlanResponse


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


def authenticate_token(raw_token: str | None) -> dict:
    if not raw_token:
        raise HTTPException(status_code=401, detail="Authorization token is required.")
    auth_context = auth_service.get_authenticated_user(raw_token)
    if auth_context is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return auth_context


def bearer_token(authorization: str | None) -> str | None:
    if authorization:
        scheme, separator, value = authorization.partition(" ")
        if separator and scheme.lower() == "bearer":
            return value.strip() or None
    return None


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    # Identity endpoints never accept reusable credentials in URLs.
    return authenticate_token(bearer_token(authorization))


@app.exception_handler(AccessDenied)
async def access_denied_handler(request: Request, exc: AccessDenied):
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(ResourceNotFound)
async def missing_resource_handler(request: Request, exc: ResourceNotFound):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.middleware("http")
async def private_responses(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


def get_current_coach(
    request: Request,
    auth_context: dict = Depends(get_current_user),
    x_organization_id: int | None = Header(default=None),
    x_access_mode: str = Header(default="staff"),
):
    if x_access_mode not in {"staff", "member"}:
        raise AccessDenied("Unsupported access mode.")
    if auth_context["user"].get("verification_required"):
        raise HTTPException(status_code=403, detail="Verify your email before opening your business.")
    contexts = auth_context["organizations"]
    organization_id = x_organization_id
    if organization_id is None and len(contexts) == 1:
        organization_id = contexts[0]["organization_id"]
    if organization_id is None:
        raise AccessDenied("Select a business to continue.")
    if not any(c["organization_id"] == organization_id for c in contexts):
        raise AccessDenied("Business access is unavailable.")
    with auth_service.repository._connect() as connection:
        try:
            repository = AccessRepository(connection, organization_id, auth_context["user"]["id"], member_mode=x_access_mode == "member")
            billing = billing_service.state(connection, organization_id)
            security_revocation = request.method == 'DELETE' and (
                request.url.path.startswith('/organization/people/') or request.url.path.startswith('/organization/invitations/'))
            if not security_revocation and (billing['access'] == 'pending' or
                    (billing['access'] == 'read_only' and request.method not in {'GET', 'HEAD'})):
                raise HTTPException(status_code=402, detail='Software subscription requires payment. Existing records remain available after expiry.')
            plans = PlanService(repository)
            yield {
                "id": auth_context["coach"]["id"] if auth_context["coach"] else auth_context["user"]["id"],
                "repository": repository,
                "client_service": ClientService(repository),
                "plan_service": plans,
                "job_service": JobService(repository),
                "ai_plan_draft_service": AiPlanDraftService(repository, plans),
            }
            connection.commit()
        except Exception:
            connection.rollback()
            raise


@app.get("/")
def home():
    return {"message": "Vectra AI Service Running..."}

@app.get('/health/ready')
def web_readiness():
    ready = web_workspace_service.ready(auth_service.repository)
    return JSONResponse(status_code=200 if ready else 503, content={'ready': ready})


@app.post("/auth/signup", response_model=AuthResponse)
async def sign_up(payload: SignUpRequest, request: Request):
    identity_request_allowed(request)
    try:
        user, coach = identity_service.register_coach(payload.model_dump())
        token = auth_service.security_service.create_access_token(user_id=user['id'], email=user['email'], session_version=user['session_version'])
        return auth_service._build_auth_payload(user, coach, token)
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
    return auth_service.session_response(auth_context)


@app.post("/login", response_model=AuthResponse)
async def legacy_login(payload: SignInRequest):
    return await sign_in(payload)


@app.get("/clients", response_model=list[ClientResponse])
async def list_clients(coach: dict = Depends(get_current_coach, scope="function")):
    return coach["client_service"].list_clients(coach["id"])


@app.post("/clients", response_model=ClientResponse)
async def create_client(payload: ClientPayload, coach: dict = Depends(get_current_coach, scope="function")):
    return coach["client_service"].create_client(coach["id"], payload.model_dump())


@app.get("/clients/{client_id}", response_model=ClientResponse)
async def get_client(client_id: int, coach: dict = Depends(get_current_coach, scope="function")):
    client = coach["client_service"].get_client(client_id, coach["id"])
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")
    return client


@app.put("/clients/{client_id}", response_model=ClientResponse)
async def update_client(client_id: int, payload: ClientPayload, coach: dict = Depends(get_current_coach, scope="function")):
    client = coach["client_service"].update_client(client_id, coach["id"], payload.model_dump())
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")
    return client


@app.post("/clients/{client_id}/goals", response_model=GoalResponse)
async def add_client_goal(client_id: int, payload: GoalPayload, coach: dict = Depends(get_current_coach, scope="function")):
    try:
        return coach["client_service"].add_goal(client_id, coach["id"], payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/clients/{client_id}/progress-photos", response_model=list[ProgressPhotoResponse])
async def list_progress_photos(client_id: int, coach: dict = Depends(get_current_coach, scope="function")):
    try:
        return coach["client_service"].list_progress_photos(client_id, coach["id"])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/clients/{client_id}/progress-photos", response_model=ProgressPhotoResponse)
async def upload_progress_photo(
    client_id: int,
    timeline_type: str = Query(...),
    captured_on: str = Query(...),
    caption: str | None = Query(default=None),
    file: UploadFile = File(...),
    coach: dict = Depends(get_current_coach, scope="function"),
):
    client = coach["client_service"].get_client(client_id, coach["id"])
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")

    coach["repository"].require_coaching_upload(client_id)
    blob_name = storage_asset_service.upload_progress_photo(
        client_id=client_id,
        filename=file.filename or f"{uuid4()}.jpg",
        data=read_upload_file(file),
        content_type=file.content_type,
    )
    photo = coach["client_service"].add_progress_photo(
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
async def get_progress_photo(blob_name: str, coach: dict = Depends(get_current_coach, scope="function")):
    coach["repository"].resolve_photo(blob_name)
    try:
        payload, media_type = storage_asset_service.get_progress_photo(blob_name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Progress photo not found: {blob_name}") from exc
    return Response(content=payload, media_type=media_type)


@app.get("/clients/{client_id}/nutrition-plans", response_model=list[PlanResponse])
async def list_nutrition_plans(client_id: int, coach: dict = Depends(get_current_coach, scope="function")):
    try:
        return coach["plan_service"].list_plans("nutrition", coach["id"], client_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/clients/{client_id}/nutrition-plans", response_model=PlanResponse)
async def create_nutrition_plan(client_id: int, payload: PlanPayload, coach: dict = Depends(get_current_coach, scope="function")):
    try:
        return coach["plan_service"].create_plan("nutrition", coach["id"], client_id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/nutrition-plans/{plan_id}", response_model=PlanResponse)
async def get_nutrition_plan(plan_id: int, coach: dict = Depends(get_current_coach, scope="function")):
    plan = coach["plan_service"].get_plan("nutrition", coach["id"], plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Nutrition plan not found.")
    return plan


@app.get("/clients/{client_id}/workout-plans", response_model=list[PlanResponse])
async def list_workout_plans(client_id: int, coach: dict = Depends(get_current_coach, scope="function")):
    try:
        return coach["plan_service"].list_plans("workout", coach["id"], client_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/clients/{client_id}/workout-plans", response_model=PlanResponse)
async def create_workout_plan(client_id: int, payload: PlanPayload, coach: dict = Depends(get_current_coach, scope="function")):
    try:
        return coach["plan_service"].create_plan("workout", coach["id"], client_id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/workout-plans/{plan_id}", response_model=PlanResponse)
async def get_workout_plan(plan_id: int, coach: dict = Depends(get_current_coach, scope="function")):
    plan = coach["plan_service"].get_plan("workout", coach["id"], plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Workout plan not found.")
    return plan


@app.post("/clients/{client_id}/plan-drafts", response_model=PlanDraftResponse)
async def create_plan_draft(
    client_id: int,
    payload: PlanDraftCreatePayload,
    coach: dict = Depends(get_current_coach, scope="function"),
):
    coach["repository"].require_client(client_id, staff=True)
    try:
        return coach["ai_plan_draft_service"].create_draft(coach["id"], client_id, payload.model_dump())
    except PlanDraftGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        status_code = 400 if "Unsupported" in str(exc) else 404
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@app.get("/clients/{client_id}/plan-drafts", response_model=list[PlanDraftResponse])
async def list_plan_drafts(
    client_id: int,
    plan_kind: str | None = Query(default=None),
    coach: dict = Depends(get_current_coach, scope="function"),
):
    try:
        return coach["ai_plan_draft_service"].list_drafts(coach["id"], client_id, plan_kind)
    except ValueError as exc:
        status_code = 400 if "Unsupported" in str(exc) else 404
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@app.get("/plan-drafts/{draft_id}", response_model=PlanDraftResponse)
async def get_plan_draft(draft_id: int, coach: dict = Depends(get_current_coach, scope="function")):
    draft = coach["ai_plan_draft_service"].get_draft(coach["id"], draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Plan draft not found.")
    return draft


@app.put("/plan-drafts/{draft_id}", response_model=PlanDraftResponse)
async def update_plan_draft(
    draft_id: int,
    payload: PlanDraftUpdatePayload,
    coach: dict = Depends(get_current_coach, scope="function"),
):
    try:
        draft = coach["ai_plan_draft_service"].update_draft(coach["id"], draft_id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if draft is None:
        raise HTTPException(status_code=404, detail="Plan draft not found.")
    return draft


@app.post("/plan-drafts/{draft_id}/regenerate", response_model=PlanDraftResponse)
async def regenerate_plan_draft(
    draft_id: int,
    payload: PlanDraftRegeneratePayload,
    coach: dict = Depends(get_current_coach, scope="function"),
):
    try:
        draft = coach["ai_plan_draft_service"].regenerate_draft(coach["id"], draft_id, payload.model_dump())
    except PlanDraftGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        status_code = 400 if "Unsupported" in str(exc) or "Only draft" in str(exc) else 404
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    if draft is None:
        raise HTTPException(status_code=404, detail="Plan draft not found.")
    return draft


@app.post("/plan-drafts/{draft_id}/approve", response_model=PlanDraftApprovalResponse)
async def approve_plan_draft(draft_id: int, coach: dict = Depends(get_current_coach, scope="function")):
    try:
        approval = coach["ai_plan_draft_service"].approve_draft(coach["id"], draft_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if approval is None:
        raise HTTPException(status_code=404, detail="Plan draft not found.")
    draft, plan = approval
    return {"draft": draft, "plan": plan}


@app.post("/plan-drafts/{draft_id}/discard", response_model=PlanDraftResponse)
async def discard_plan_draft(draft_id: int, coach: dict = Depends(get_current_coach, scope="function")):
    try:
        draft = coach["ai_plan_draft_service"].discard_draft(coach["id"], draft_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if draft is None:
        raise HTTPException(status_code=404, detail="Plan draft not found.")
    return draft


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
async def download_nutrition_plan_pdf(plan_id: int, coach: dict = Depends(get_current_coach, scope="function")):
    plan = coach["plan_service"].get_plan("nutrition", coach["id"], plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Nutrition plan not found.")
    payload = build_plan_pdf("nutrition", plan)
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="nutrition-plan-{plan_id}.pdf"'},
    )


@app.get("/workout-plans/{plan_id}/pdf")
async def download_workout_plan_pdf(plan_id: int, coach: dict = Depends(get_current_coach, scope="function")):
    plan = coach["plan_service"].get_plan("workout", coach["id"], plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Workout plan not found.")
    payload = build_plan_pdf("workout", plan)
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="workout-plan-{plan_id}.pdf"'},
    )


@app.post("/clients/{client_id}/form-analyses", response_model=FormAnalysisResponse, dependencies=[Depends(require_analysis)])
async def create_form_analysis(
    client_id: int,
    analysis_type: str = Query(default="squat"),
    file: UploadFile = File(...),
    coach: dict = Depends(get_current_coach, scope="function"),
):
    client = coach["client_service"].get_client(client_id, coach["id"])
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")
    if analysis_type != "squat":
        raise HTTPException(status_code=400, detail="Only squat analysis is supported right now.")

    coach["repository"].require_coaching_upload(client_id)
    analysis_id = str(uuid4())
    original_filename = file.filename or "upload.mp4"
    stored_filename = build_job_filename(analysis_id, original_filename)
    file_bytes = read_upload_file(file)
    video_blob_name = get_analysis_runner().upload_video_for_job(
        job_id=analysis_id,
        stored_filename=stored_filename,
        data=file_bytes,
        content_type=file.content_type,
    )

    analysis = coach["job_service"].create_job(
        job_id=analysis_id,
        client_id=client_id,
        analysis_type=analysis_type,
        original_filename=original_filename,
        stored_filename=stored_filename,
        video_blob_name=video_blob_name,
    )
    # Publish only after the row is visible to a separate worker connection.
    coach["repository"].connection.commit()
    get_analysis_queue().enqueue_analysis_job(job_id=analysis_id, analysis_type=analysis_type,
                                       organization_id=coach["repository"].organization_id)
    return build_form_analysis_response(analysis)


@app.get("/clients/{client_id}/form-analyses", response_model=FormAnalysisListResponse, dependencies=[Depends(require_analysis)])
async def list_client_form_analyses(
    client_id: int,
    limit: int = 20,
    coach: dict = Depends(get_current_coach, scope="function"),
):
    analyses = coach["job_service"].list_jobs(limit=limit, coach_id=coach["id"], client_id=client_id)
    return FormAnalysisListResponse(analyses=[build_form_analysis_response(job) for job in analyses])


@app.get("/form-analyses", response_model=FormAnalysisListResponse, dependencies=[Depends(require_analysis)])
async def list_form_analyses(limit: int = 20, coach: dict = Depends(get_current_coach, scope="function")):
    analyses = coach["job_service"].list_jobs(limit=limit, coach_id=coach["id"])
    return FormAnalysisListResponse(analyses=[build_form_analysis_response(job) for job in analyses])


@app.get("/form-analyses/{analysis_id}", response_model=FormAnalysisResponse, dependencies=[Depends(require_analysis)])
async def get_form_analysis(analysis_id: str, coach: dict = Depends(get_current_coach, scope="function")):
    analysis = coach["job_service"].get_job_for_coach(analysis_id, coach["id"])
    if analysis is None:
        raise HTTPException(status_code=404, detail="Form analysis not found.")
    return build_form_analysis_response(analysis)


@app.put("/form-analyses/{analysis_id}/feedback", response_model=FormAnalysisResponse, dependencies=[Depends(require_analysis)])
async def update_form_analysis_feedback(
    analysis_id: str,
    payload: FeedbackPayload,
    coach: dict = Depends(get_current_coach, scope="function"),
):
    analysis = coach["job_service"].get_job_for_coach(analysis_id, coach["id"])
    if analysis is None:
        raise HTTPException(status_code=404, detail="Form analysis not found.")
    updated = coach["job_service"].update_feedback(analysis_id, payload.coach_feedback_note)
    if updated is None:
        raise HTTPException(status_code=404, detail="Form analysis not found.")
    return build_form_analysis_response(updated)


@app.get("/form-analyses/{analysis_id}/pdf", dependencies=[Depends(require_analysis)])
async def download_form_analysis_pdf(analysis_id: str, coach: dict = Depends(get_current_coach, scope="function")):
    analysis = coach["job_service"].get_job_for_coach(analysis_id, coach["id"])
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


@app.get("/jobs", response_model=FormAnalysisListResponse, dependencies=[Depends(require_analysis)])
async def legacy_list_jobs(limit: int = 20, coach: dict = Depends(get_current_coach, scope="function")):
    return await list_form_analyses(limit=limit, coach=coach)


@app.get("/jobs/{job_id}", response_model=FormAnalysisResponse, dependencies=[Depends(require_analysis)])
async def legacy_get_job(job_id: str, coach: dict = Depends(get_current_coach, scope="function")):
    return await get_form_analysis(job_id, coach)


@app.post("/jobs/squat", response_model=FormAnalysisResponse, dependencies=[Depends(require_analysis)])
async def legacy_create_squat_job(
    client_id: int = Query(...),
    file: UploadFile = File(...),
    coach: dict = Depends(get_current_coach, scope="function"),
):
    return await create_form_analysis(client_id=client_id, analysis_type="squat", file=file, coach=coach)


@app.get("/frames/{filename:path}", dependencies=[Depends(require_analysis)])
async def get_annotated_frame(filename: str, coach: dict = Depends(get_current_coach, scope="function")):
    coach["repository"].resolve_frame(filename)
    try:
        payload, media_type = blob_storage_service.get_annotated_frame(filename)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Annotated frame not found: {filename}") from exc
    return Response(content=payload, media_type=media_type)


@app.get('/organization/people')
async def list_business_people(coach: dict = Depends(get_current_coach, scope="function")):
    return coach['repository'].list_people()


@app.delete('/organization/people/{relationship_id}/roles/{role}')
async def revoke_business_role(relationship_id: int, role: str, coach: dict = Depends(get_current_coach, scope="function")):
    coach['repository'].revoke_role(relationship_id, role)
    return {'status': 'revoked'}


class AssignmentPayload(BaseModel):
    relationship_id: int
    active: bool


@app.put('/clients/{client_id}/trainer-assignment')
async def set_trainer_assignment(client_id: int, payload: AssignmentPayload, coach: dict = Depends(get_current_coach, scope="function")):
    coach['repository'].assign_trainer(client_id, payload.relationship_id, payload.active)
    return {'status': 'updated'}


class EmailRequest(BaseModel):
    email: str = Field(max_length=254)


class IdentityActionRequest(BaseModel):
    token: str = Field(min_length=1, max_length=200)
    password: str | None = Field(default=None, min_length=12, max_length=256)
    email: str | None = Field(default=None, max_length=254)


class InvitationRequest(EmailRequest):
    role: str
    client_id: int | None = Field(default=None, gt=0)


def identity_request_allowed(request: Request):
    # Only direct peer address is trusted; deployments must configure trusted proxies explicitly.
    if not identity_service.rate_limit(f'identity:{request.client.host if request.client else "unknown"}'):
        raise HTTPException(status_code=429, detail='Too many requests. Try again in an hour.')


@app.post('/auth/email/{kind}/request')
def request_identity_email(kind: str, payload: EmailRequest, request: Request):
    identity_request_allowed(request)
    try:
        return identity_service.request_email(payload.email, kind)
    except ValueError:
        return {'message': GENERIC_MESSAGE}


@app.post('/auth/email/{kind}/confirm')
def confirm_identity_action(kind: str, payload: IdentityActionRequest, request: Request,
                            authorization: str | None = Header(default=None)):
    identity_request_allowed(request)
    current_user = None
    if authorization:
        current_user = authenticate_token(bearer_token(authorization))['user']
    try:
        return identity_service.consume(payload.token, kind, password=payload.password,
                                        email=payload.email, current_user=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post('/organization/invitations')
def invite_staff(payload: InvitationRequest, coach: dict = Depends(get_current_coach, scope='function')):
    try:
        return identity_service.create_invitation(coach['repository'], payload.email, payload.role, payload.client_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get('/organization/invitations')
def list_invitations(coach: dict = Depends(get_current_coach, scope='function')):
    return identity_service.list_invitations(coach['repository'])


@app.delete('/organization/invitations/{invitation_id}')
def revoke_invitation(invitation_id: UUID, coach: dict = Depends(get_current_coach, scope='function')):
    return identity_service.revoke_invitation(coach['repository'], invitation_id)


class BusinessOnboardingRequest(BaseModel):
    request_id: UUID
    business_name: str = Field(min_length=1, max_length=120)
    business_type: str


class BusinessRegistrationRequest(BusinessOnboardingRequest):
    email: str = Field(max_length=254)
    password: str = Field(min_length=12, max_length=256)


class SoftwareCheckoutRequest(BaseModel):
    plan_code: str = Field(max_length=80)
    terms_version: str = Field(max_length=100)
    accept_terms: bool


class SoftwareCallbackRequest(BaseModel):
    razorpay_payment_id: str = Field(max_length=100)
    razorpay_subscription_id: str = Field(max_length=100)
    razorpay_signature: str = Field(max_length=100)


def billing_call(operation, *args):
    try:
        return operation(*args)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post('/auth/register-business', response_model=AuthResponse)
def register_business(payload: BusinessRegistrationRequest, request: Request):
    identity_request_allowed(request)
    user = billing_call(identity_service.register_business, payload.model_dump())
    token = auth_service.security_service.create_access_token(user_id=user['id'], email=user['email'], session_version=user['session_version'])
    return auth_service._build_auth_payload(user, None, token)


@app.post('/organizations')
def create_business(payload: BusinessOnboardingRequest, auth: dict = Depends(get_current_user)):
    return billing_call(billing_service.create_business, auth['user'], payload.request_id, payload.business_name, payload.business_type)


@app.get('/organizations/{organization_id}/billing')
def software_billing(organization_id: int, auth: dict = Depends(get_current_user)):
    return billing_service.summary(auth['user'], organization_id)


@app.post('/organizations/{organization_id}/billing/checkout')
def software_checkout(organization_id: int, payload: SoftwareCheckoutRequest, auth: dict = Depends(get_current_user)):
    if not payload.accept_terms:
        raise HTTPException(status_code=400, detail='Review and accept the billing terms before continuing.')
    return billing_call(billing_service.start_subscription, auth['user'], organization_id, payload.plan_code, payload.terms_version)


@app.post('/organizations/{organization_id}/billing/verify')
def software_verify(organization_id: int, payload: SoftwareCallbackRequest, auth: dict = Depends(get_current_user)):
    return billing_call(billing_service.refresh, auth['user'], organization_id, payload.model_dump())


@app.post('/organizations/{organization_id}/billing/refresh')
def software_refresh(organization_id: int, auth: dict = Depends(get_current_user)):
    return billing_call(billing_service.refresh, auth['user'], organization_id)


@app.post('/organizations/{organization_id}/billing/cancel')
def software_cancel(organization_id: int, auth: dict = Depends(get_current_user)):
    return billing_service.cancel(auth['user'], organization_id)


@app.post('/webhooks/razorpay')
async def razorpay_webhook(request: Request, x_razorpay_signature: str | None = Header(default=None),
                           x_razorpay_event_id: str | None = Header(default=None)):
    chunks = bytearray()
    async for chunk in request.stream():
        chunks.extend(chunk)
        if len(chunks) > 262144:
            raise HTTPException(status_code=413, detail='Webhook payload is too large.')
    return billing_call(billing_service.webhook, bytes(chunks), x_razorpay_signature, x_razorpay_event_id)

# Step 5: public discovery stays separate from scoped operational APIs.



@app.exception_handler(CatalogueChanged)
async def gym_conflict_handler(request: Request, exc: CatalogueChanged):
    return JSONResponse(status_code=409, content={'detail': str(exc)})


def gym_call(operation, *args):
    try:
        return operation(*args)
    except CatalogueChanged:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class GymSetupRequest(BaseModel):
    revision: int = Field(ge=0, strict=True)
    configuration: dict
    confirm_payment: bool = False


class GymJoinRequest(BaseModel):
    request_id: UUID
    revision: int = Field(ge=1, strict=True)
    plan_ids: list[str] = Field(min_length=1, max_length=2)
    member_name: str = Field(min_length=1, max_length=120)
    mobile: str = Field(min_length=7, max_length=25)
    accept_terms: bool
    replaces_id: UUID | None = None


class MemberRegistrationRequest(BaseModel):
    public_id: UUID
    email: str = Field(max_length=254)
    password: str = Field(min_length=12, max_length=256)


@app.post('/auth/register-member', response_model=AuthResponse)
def register_member(payload: MemberRegistrationRequest, request: Request):
    identity_request_allowed(request)
    if not gym_service.public(payload.public_id)['available']:
        raise HTTPException(status_code=400, detail='Registration is unavailable. Contact the gym.')
    user = gym_call(identity_service.register_member, payload.model_dump())
    token = auth_service.security_service.create_access_token(user_id=user['id'], email=user['email'], session_version=user['session_version'])
    return auth_service._build_auth_payload(user, None, token)


@app.get('/gym/setup')
def gym_setup(coach: dict = Depends(get_current_coach)):
    return gym_call(gym_service.setup, coach['repository'])


@app.put('/gym/setup')
def save_gym_setup(payload: GymSetupRequest, coach: dict = Depends(get_current_coach)):
    return gym_call(gym_service.save, coach['repository'], payload.revision, payload.configuration, payload.confirm_payment)


@app.post('/gym/assets/{kind}')
async def upload_gym_asset(kind: str, file: UploadFile = File(...), coach: dict = Depends(get_current_coach)):
    try:
        raw = await file.read(MAX_IMAGE_BYTES + 1)
        return gym_call(gym_service.upload, coach['repository'], kind, raw)
    finally:
        await file.close()


@app.get('/gym/assets/{asset_id}')
def gym_private_asset(asset_id: UUID, coach: dict = Depends(get_current_coach)):
    return Response(gym_service.asset(asset_id, coach['repository']), media_type='image/png', headers={'X-Content-Type-Options': 'nosniff'})


@app.get('/public/gym-assets/{asset_id}')
def gym_public_asset(asset_id: UUID):
    return Response(gym_service.asset(asset_id), media_type='image/png', headers={'X-Content-Type-Options': 'nosniff'})


@app.get('/public/gyms/{public_id}')
def public_gym(public_id: UUID):
    return gym_call(gym_service.public, public_id)


@app.get('/public/gyms/{public_id}/purchases')
def own_gym_purchases(public_id: UUID, auth: dict = Depends(get_current_user)):
    return gym_service.history(public_id, auth['user'])


@app.post('/public/gyms/{public_id}/join')
def join_gym(public_id: UUID, payload: GymJoinRequest, request: Request, auth: dict = Depends(get_current_user)):
    identity_request_allowed(request)
    if not payload.accept_terms:
        raise HTTPException(status_code=400, detail='Review and accept the plan terms and payment instructions.')
    return gym_call(gym_service.join, public_id, auth['user'], payload.model_dump())


@app.get('/gym/registration/{format}')
def gym_registration_download(format: str, coach: dict = Depends(get_current_coach)):
    access = coach['repository']
    gym_service.require_admin(access)
    row = gym_service.repository.profile(access.connection, access.organization_id)
    if not row or not row['configuration'].get('display_name'):
        raise HTTPException(status_code=400, detail='Save gym setup before downloading registration materials.')
    url = gym_call(gym_service.join_url, row)
    if format == 'qr.png':
        data, content_type = registration_qr(url), 'image/png'
    elif format == 'poster.pdf':
        data, content_type = reception_poster(row['configuration']['display_name'], url), 'application/pdf'
    else:
        raise HTTPException(status_code=404, detail='Download not found.')
    return Response(data, media_type=content_type, headers={'Content-Disposition': f'attachment; filename="gym-registration-{format}"'})


@app.get('/gym/registrations')
def gym_registrations(coach: dict = Depends(get_current_coach)):
    access = coach['repository']
    gym_service.require_admin(access)
    return gym_service.repository.admin_purchases(access.connection, access.organization_id)


@app.get('/member/gym-registrations')
def member_gym_registrations(coach: dict = Depends(get_current_coach)):
    access = coach['repository']
    row = gym_service.repository.profile(access.connection, access.organization_id)
    if not row:
        return []
    return [gym_service.purchase_view(p, row['revision']) for p in gym_service.repository.purchases(access.connection, access.organization_id, access.user_id)]


# Manual gym collections are independent of Vectra's software billing provider.


class MembershipActionRequest(BaseModel):
    note: str = Field(min_length=1, max_length=2000)
    reference: str = Field(default='', max_length=120)
    method: str | None = None
    amount_paise: int | None = Field(default=None, strict=True, gt=0)
    received_on: str | None = None
    starts_on: str | None = None
    receipt_checked: bool = False
    pt_terms_consent: bool = False
    external_refund_completed: bool = False
    entitlement: str | None = None


@app.get('/member/purchases/{purchase_id}')
def member_purchase_detail(purchase_id: UUID, coach: dict = Depends(get_current_coach)):
    return gym_call(membership_service.details, coach['repository'], purchase_id)


@app.get('/gym/purchases/{purchase_id}')
def admin_purchase_detail(purchase_id: UUID, coach: dict = Depends(get_current_coach)):
    return gym_call(membership_service.details, coach['repository'], purchase_id, True)


@app.post('/member/purchases/{purchase_id}/{action}')
def member_purchase_action(purchase_id: UUID, action: str, payload: MembershipActionRequest, coach: dict = Depends(get_current_coach)):
    return gym_call(membership_service.act, coach['repository'], purchase_id, action, payload.model_dump())


class PtReassignmentRequest(BaseModel):
    trainer_relationship_id: int = Field(gt=0, strict=True)
    member_consent: bool
    note: str = Field(min_length=1, max_length=2000)


@app.post('/gym/purchases/{purchase_id}/reassign-pt')
def reassign_pt_purchase(purchase_id: UUID, payload: PtReassignmentRequest, coach: dict = Depends(get_current_coach, scope='function')):
    return gym_call(pt_service.reassign, coach['repository'], purchase_id, payload.trainer_relationship_id, payload.member_consent, payload.note)


@app.post('/gym/purchases/{purchase_id}/{action}')
def admin_purchase_action(purchase_id: UUID, action: str, payload: MembershipActionRequest, coach: dict = Depends(get_current_coach)):
    return gym_call(membership_service.act, coach['repository'], purchase_id, action, payload.model_dump(), True)


@app.put('/member/purchases/{purchase_id}/evidence')
async def member_purchase_evidence(purchase_id: UUID, file: UploadFile = File(...), coach: dict = Depends(get_current_coach)):
    try:
        return gym_call(membership_service.evidence, coach['repository'], purchase_id, await file.read(MAX_IMAGE_BYTES + 1))
    finally:
        await file.close()


@app.get('/gym/purchases/{purchase_id}/evidence/{event_id}')
def admin_purchase_evidence(purchase_id: UUID, event_id: int, coach: dict = Depends(get_current_coach)):
    access = coach['repository']
    membership_service.details(access, purchase_id, True)
    row = access.connection.execute('SELECT evidence FROM gym_payment_events WHERE organization_id=%s AND purchase_id=%s AND id=%s', (access.organization_id, purchase_id, event_id)).fetchone()
    if not row or not row['evidence']:
        raise HTTPException(status_code=404, detail='Evidence not found.')
    return Response(bytes(row['evidence']), media_type='image/png', headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


class AppointmentCreateRequest(BaseModel):
    request_id: UUID
    entitlement_id: UUID | None = None
    client_id: int | None = Field(default=None, gt=0)
    trainer_relationship_id: int | None = Field(default=None, gt=0)
    starts_at: str = Field(max_length=50)


class AppointmentChangeRequest(BaseModel):
    version: int = Field(gt=0, strict=True)
    starts_at: str | None = Field(default=None, max_length=50)


@app.get('/pt/workspace')
def pt_workspace(coach: dict = Depends(get_current_coach, scope='function')):
    return gym_call(pt_service.list, coach['repository'])


@app.get('/member/pt-options')
def pt_options(coach: dict = Depends(get_current_coach, scope='function')):
    return gym_call(pt_service.options, coach['repository'])


@app.get('/public/gyms/{public_id}/pt-options')
def public_member_pt_options(public_id: UUID, auth: dict = Depends(get_current_user)):
    with pt_service.repository.transaction() as db:
        profile = pt_service.repository.public_profile(db, public_id)
        if not profile:
            raise ResourceNotFound('Gym not found.')
        access = AccessRepository(db, profile['organization_id'], auth['user']['id'], member_mode=True)
        return gym_call(pt_service.options, access)


@app.post('/appointments')
def book_appointment(payload: AppointmentCreateRequest, coach: dict = Depends(get_current_coach, scope='function')):
    return gym_call(pt_service.book, coach['repository'], payload.model_dump())


@app.post('/appointments/{appointment_id}/{action}')
def change_appointment(appointment_id: UUID, action: str, payload: AppointmentChangeRequest, coach: dict = Depends(get_current_coach, scope='function')):
    return gym_call(pt_service.change_appointment, coach['repository'], appointment_id, action, payload.version, payload.starts_at)


class AnnouncementRequest(BaseModel):
    request_id: UUID
    audience: str
    subject: str = Field(min_length=1, max_length=160)
    message: str = Field(min_length=1, max_length=4000)


class WebRolloutRequest(BaseModel):
    purchases_enabled: bool = Field(strict=True)


@app.get('/inbox')
def notification_inbox(before: int | None = Query(default=None, gt=0), limit: int = Query(default=30, ge=1, le=100),
                       coach: dict = Depends(get_current_coach, scope='function')):
    return web_workspace_service.inbox(coach['repository'], before, limit)


@app.post('/inbox/{notification_id}/read')
def read_notification(notification_id: int, coach: dict = Depends(get_current_coach, scope='function')):
    return web_workspace_service.mark_read(coach['repository'], notification_id)


@app.post('/organization/announcements')
def announce(payload: AnnouncementRequest, coach: dict = Depends(get_current_coach, scope='function')):
    return gym_call(web_workspace_service.announce, coach['repository'], payload.request_id,
                    payload.audience, payload.subject, payload.message)


@app.get('/organization/reports')
def owner_reports(start: date | None = None, end: date | None = None,
                  coach: dict = Depends(get_current_coach, scope='function')):
    return gym_call(web_workspace_service.reports, coach['repository'], start, end)


@app.put('/organization/web-rollout')
def web_rollout(payload: WebRolloutRequest, coach: dict = Depends(get_current_coach, scope='function')):
    return web_workspace_service.set_rollout(coach['repository'], payload.purchases_enabled)


@app.get('/clients/{client_id}/coaching-access')
def member_coaching_access(client_id: int, coach: dict = Depends(get_current_coach, scope='function')):
    return coach['repository'].coaching_access(client_id)


@app.get('/clients/{client_id}/goals', response_model=list[GoalResponse])
def member_goals(client_id: int, coach: dict = Depends(get_current_coach, scope='function')):
    return coach['repository'].list_goals(client_id)
