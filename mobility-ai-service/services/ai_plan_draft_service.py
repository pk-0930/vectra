import json
from datetime import UTC, datetime
from typing import Any

from config.postgres_config import get_postgres_config
from repositories.platform_repository import PostgresPlatformRepository
from services.plan_service import PlanService


def utc_now() -> datetime:
    return datetime.now(UTC)


class MockPlanDraftGenerator:
    def generate(self, plan_kind: str, request: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        client = context["client"]
        goal = client.get("current_goal_type")
        goal_text = goal.replace("_", " ") if goal else "general fitness"
        coach_prompt = request.get("coach_prompt") or "No extra coach instructions."
        title = f"AI draft {plan_kind} plan for {client['first_name']}"

        if plan_kind == "nutrition":
            dietary_preference = request["generation_preferences"].get("dietary_preference", "no_preference")
            content = {
                "summary": (
                    f"Draft nutrition structure for {client['first_name']} focused on {goal_text}. "
                    "Coach approval required before sharing."
                ),
                "focus": f"Support {goal_text} with consistent meals, hydration, and protein distribution.",
                "meals": self._nutrition_meals(dietary_preference),
                "notes": f"Dietary preference: {dietary_preference.replace('_', ' ')}. Coach instruction: {coach_prompt}",
            }
        else:
            analysis_note = self._analysis_note(context.get("latest_form_analysis"))
            content = {
                "summary": (
                    f"Draft workout structure for {client['first_name']} focused on {goal_text}. "
                    "Review movement readiness before approval."
                ),
                "focus": f"Build training consistency while addressing form-analysis context. {analysis_note}",
                "workout_days": (
                    "Day 1: lower-body strength with squat pattern practice.\n"
                    "Day 2: upper-body push/pull and trunk stability.\n"
                    "Day 3: full-body conditioning with controlled tempo work."
                ),
                "mobility_drills": (
                    "Before workout: 6-8 minutes of ankle rocks, hip flexor mobilization, and thoracic rotations.\n"
                    "Between warm-up and main sets: 2 light technique sets using the day's main pattern.\n"
                    "Recovery day: 10 minutes of easy hips, ankles, and breathing-based mobility."
                ),
                "stretching_plan": (
                    "After workout: 5-7 minutes of calf, hip flexor, hamstring, and chest stretches.\n"
                    "Hold each stretch for 30-45 seconds without forcing range."
                ),
                "notes": f"Coach instruction: {coach_prompt}",
            }

        return {
            "title": title,
            "content": content,
        }

    def _nutrition_meals(self, dietary_preference: str) -> str:
        protein_examples = {
            "vegetarian": "paneer, curd, dal, sprouts, tofu",
            "non_vegetarian": "eggs, chicken, fish, curd, dal",
            "eggetarian": "eggs, curd, dal, paneer, sprouts",
            "vegan": "tofu, tempeh, dal, beans, sprouts",
            "no_preference": "eggs, curd, dal, paneer, chicken, tofu",
        }
        proteins = protein_examples.get(dietary_preference, protein_examples["no_preference"])
        return (
            f"Breakfast: balanced meal with one protein source such as {proteins}.\n"
            "Lunch: whole-grain or rice base, vegetables, and a palm-sized protein serving.\n"
            "Snack: fruit plus a protein or fiber-rich option.\n"
            "Dinner: lighter plate with vegetables, protein, and hydration check."
        )

    def _analysis_note(self, latest_form_analysis: dict[str, Any] | None) -> str:
        if latest_form_analysis is None:
            return "No completed form analysis was available, so mobility work is conservative."
        feedback = latest_form_analysis.get("coach_feedback_note")
        if feedback:
            return f"Latest coach feedback noted: {feedback}"
        return "Latest completed form analysis is available for coach review."


class AiPlanDraftService:
    VALID_KINDS = {"nutrition", "workout"}
    DRAFT_STATUS = "draft"
    APPROVED_STATUS = "approved"
    DISCARDED_STATUS = "discarded"

    def __init__(self, repository=None, plan_service: PlanService | None = None, generator=None):
        self.repository = repository or PostgresPlatformRepository(get_postgres_config())
        self.repository.initialize()
        self.plan_service = plan_service or PlanService(repository=self.repository)
        self.generator = generator or MockPlanDraftGenerator()

    def create_draft(self, coach_id: int, client_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        plan_kind = self._validate_kind(payload["plan_kind"])
        client = self.repository.fetch_client(client_id, coach_id)
        if client is None:
            raise ValueError("Client not found.")

        preferences = self._build_generation_preferences(plan_kind, payload)
        request = {
            **payload,
            "generation_preferences": preferences,
        }
        source_context = self._build_source_context(plan_kind, client_id, coach_id, client)
        generated = self.generator.generate(plan_kind, request, source_context)

        timestamp = utc_now()
        row = self.repository.create_plan_draft(
            {
                "client_id": client_id,
                "coach_id": coach_id,
                "plan_kind": plan_kind,
                "status": self.DRAFT_STATUS,
                "period_type": payload["period_type"],
                "period_start": payload["period_start"],
                "period_end": payload["period_end"],
                "title": generated["title"].strip(),
                "content_json": json.dumps(generated["content"]),
                "source_context_json": json.dumps(source_context),
                "generation_preferences_json": json.dumps(preferences),
                "coach_prompt": payload.get("coach_prompt"),
                "model_name": "deterministic_mock_v1",
                "created_at": timestamp,
                "updated_at": timestamp,
                "approved_plan_id": None,
            }
        )
        return self._serialize_draft(row)

    def list_drafts(self, coach_id: int, client_id: int, plan_kind: str | None = None) -> list[dict[str, Any]]:
        client = self.repository.fetch_client(client_id, coach_id)
        if client is None:
            raise ValueError("Client not found.")
        if plan_kind is not None:
            plan_kind = self._validate_kind(plan_kind)
        return [
            self._serialize_draft(row)
            for row in self.repository.list_plan_drafts(client_id, coach_id, plan_kind)
        ]

    def get_draft(self, coach_id: int, draft_id: int) -> dict[str, Any] | None:
        row = self.repository.fetch_plan_draft(draft_id, coach_id)
        return self._serialize_draft(row) if row else None

    def update_draft(self, coach_id: int, draft_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
        draft = self.repository.fetch_plan_draft(draft_id, coach_id)
        if draft is None:
            return None
        if draft["status"] != self.DRAFT_STATUS:
            raise ValueError("Only draft plans can be edited.")

        row = self.repository.update_plan_draft(
            draft_id,
            coach_id,
            {
                "period_type": payload["period_type"],
                "period_start": payload["period_start"],
                "period_end": payload["period_end"],
                "title": payload["title"].strip(),
                "content_json": json.dumps(payload["content"]),
                "coach_prompt": payload.get("coach_prompt"),
                "updated_at": utc_now(),
            },
        )
        return self._serialize_draft(row) if row else None

    def approve_draft(self, coach_id: int, draft_id: int) -> tuple[dict[str, Any], dict[str, Any]] | None:
        draft = self.repository.fetch_plan_draft(draft_id, coach_id)
        if draft is None:
            return None
        if draft["status"] != self.DRAFT_STATUS:
            raise ValueError("Only draft plans can be approved.")

        serialized = self._serialize_draft(draft)
        plan = self.plan_service.create_plan(
            serialized["plan_kind"],
            coach_id,
            serialized["client_id"],
            {
                "period_type": serialized["period_type"],
                "period_start": serialized["period_start"],
                "period_end": serialized["period_end"],
                "title": serialized["title"],
                "content": serialized["content"],
            },
        )
        row = self.repository.set_plan_draft_status(
            draft_id,
            coach_id,
            self.APPROVED_STATUS,
            utc_now(),
            plan["id"],
        )
        return (self._serialize_draft(row), plan) if row else None

    def discard_draft(self, coach_id: int, draft_id: int) -> dict[str, Any] | None:
        draft = self.repository.fetch_plan_draft(draft_id, coach_id)
        if draft is None:
            return None
        if draft["status"] != self.DRAFT_STATUS:
            raise ValueError("Only draft plans can be discarded.")
        row = self.repository.set_plan_draft_status(
            draft_id,
            coach_id,
            self.DISCARDED_STATUS,
            utc_now(),
            None,
        )
        return self._serialize_draft(row) if row else None

    def _build_source_context(
        self,
        plan_kind: str,
        client_id: int,
        coach_id: int,
        client: dict[str, Any],
    ) -> dict[str, Any]:
        recent_photos = self.repository.list_progress_photos(client_id)[:5]
        latest_plans = self.repository.list_plans(PlanService.TABLES[plan_kind], client_id, coach_id)
        completed_analyses = [
            row
            for row in self.repository.fetch_form_analyses(coach_id, 12, client_id)
            if row["status"] == "completed"
        ]
        return {
            "client": self._serialize_client_context(client),
            "recent_progress_photos": [
                {
                    "id": row["id"],
                    "caption": row["caption"],
                    "timeline_type": row["timeline_type"],
                    "captured_on": row["captured_on"].isoformat(),
                }
                for row in recent_photos
            ],
            "latest_form_analysis": self._serialize_form_analysis(completed_analyses[0])
            if completed_analyses
            else None,
            "latest_plan": self._serialize_plan_context(latest_plans[0]) if latest_plans else None,
        }

    def _build_generation_preferences(self, plan_kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        if plan_kind != "nutrition":
            return {}
        return {"dietary_preference": payload.get("dietary_preference") or "no_preference"}

    def _validate_kind(self, plan_kind: str) -> str:
        if plan_kind not in self.VALID_KINDS:
            raise ValueError("Unsupported plan kind.")
        return plan_kind

    def _serialize_draft(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "client_id": row["client_id"],
            "coach_id": row["coach_id"],
            "plan_kind": row["plan_kind"],
            "status": row["status"],
            "period_type": row["period_type"],
            "period_start": row["period_start"].isoformat(),
            "period_end": row["period_end"].isoformat(),
            "title": row["title"],
            "content": self._json_value(row["content_json"]),
            "source_context": self._json_value(row["source_context_json"]),
            "generation_preferences": self._json_value(row["generation_preferences_json"]),
            "coach_prompt": row["coach_prompt"],
            "model_name": row["model_name"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
            "approved_plan_id": row["approved_plan_id"],
        }

    def _serialize_client_context(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "gender": row["gender"],
            "height_cm": row["height_cm"],
            "weight_kg": row["weight_kg"],
            "current_goal_type": row.get("current_goal_type"),
            "current_goal_notes": row.get("current_goal_notes"),
        }

    def _serialize_form_analysis(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "analysis_type": row["analysis_type"],
            "result": self._json_value(row["result_json"]),
            "coach_feedback_note": row.get("coach_feedback_note"),
            "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
        }

    def _serialize_plan_context(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "period_type": row["period_type"],
            "period_start": row["period_start"].isoformat(),
            "period_end": row["period_end"].isoformat(),
            "title": row["title"],
            "content": self._json_value(row["content_json"]),
        }

    def _json_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return json.loads(value)
        return value
