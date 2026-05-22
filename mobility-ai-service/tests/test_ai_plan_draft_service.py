from datetime import UTC, date, datetime
import json
import unittest

from services.ai_plan_draft_service import AiPlanDraftService
from services.plan_service import PlanService


class InMemoryPlanDraftRepository:
    def __init__(self):
        self.drafts: dict[int, dict] = {}
        self.plans: dict[str, dict[int, dict]] = {
            "nutrition_plans": {},
            "workout_plans": {},
        }
        self.next_draft_id = 1
        self.next_plan_id = 1

    def initialize(self):
        return None

    def fetch_client(self, client_id: int, coach_id: int) -> dict | None:
        if client_id != 1 or coach_id != 7:
            return None
        return {
            "id": 1,
            "coach_id": 7,
            "first_name": "Asha",
            "last_name": "Kumar",
            "dob": None,
            "gender": "female",
            "height_cm": 165,
            "weight_kg": 62,
            "is_active": True,
            "current_goal_type": "strength_training",
            "current_goal_notes": "Improve squat confidence",
            "created_at": datetime(2026, 5, 1, tzinfo=UTC),
            "updated_at": datetime(2026, 5, 1, tzinfo=UTC),
        }

    def list_progress_photos(self, client_id: int) -> list[dict]:
        return [
            {
                "id": 1,
                "client_id": client_id,
                "blob_name": "photo.jpg",
                "caption": "Weekly check-in",
                "timeline_type": "weekly",
                "captured_on": date(2026, 5, 20),
                "created_at": datetime(2026, 5, 20, tzinfo=UTC),
            }
        ]

    def fetch_form_analyses(self, coach_id: int, limit: int, client_id: int | None = None) -> list[dict]:
        return [
            {
                "id": "analysis-1",
                "client_id": client_id,
                "analysis_type": "squat",
                "status": "completed",
                "original_filename": "squat.mp4",
                "stored_filename": "squat.mp4",
                "video_blob_name": "squat.mp4",
                "result_json": json.dumps({"recommendation": "Control knee travel"}),
                "error_message": None,
                "coach_feedback_note": "Add ankle mobility before squats",
                "created_at": datetime(2026, 5, 20, tzinfo=UTC),
                "updated_at": datetime(2026, 5, 20, tzinfo=UTC),
                "started_at": datetime(2026, 5, 20, tzinfo=UTC),
                "completed_at": datetime(2026, 5, 20, tzinfo=UTC),
            }
        ]

    def create_plan(self, table_name: str, payload: dict) -> dict:
        plan_id = self.next_plan_id
        self.next_plan_id += 1
        row = {
            "id": plan_id,
            **payload,
            "period_start": date.fromisoformat(payload["period_start"]),
            "period_end": date.fromisoformat(payload["period_end"]),
        }
        self.plans[table_name][plan_id] = row
        return dict(row)

    def list_plans(self, table_name: str, client_id: int, coach_id: int) -> list[dict]:
        return list(self.plans[table_name].values())

    def create_plan_draft(self, payload: dict) -> dict:
        draft_id = self.next_draft_id
        self.next_draft_id += 1
        row = {
            "id": draft_id,
            **payload,
            "period_start": date.fromisoformat(payload["period_start"]),
            "period_end": date.fromisoformat(payload["period_end"]),
        }
        self.drafts[draft_id] = row
        return dict(row)

    def list_plan_drafts(self, client_id: int, coach_id: int, plan_kind: str | None = None) -> list[dict]:
        rows = [
            draft
            for draft in self.drafts.values()
            if draft["client_id"] == client_id and draft["coach_id"] == coach_id
        ]
        if plan_kind is not None:
            rows = [draft for draft in rows if draft["plan_kind"] == plan_kind]
        return [dict(row) for row in rows]

    def fetch_plan_draft(self, draft_id: int, coach_id: int) -> dict | None:
        draft = self.drafts.get(draft_id)
        if draft is None or draft["coach_id"] != coach_id:
            return None
        return dict(draft)

    def update_plan_draft(self, draft_id: int, coach_id: int, payload: dict) -> dict | None:
        draft = self.drafts.get(draft_id)
        if draft is None or draft["coach_id"] != coach_id or draft["status"] != "draft":
            return None
        draft.update(payload)
        draft["period_start"] = date.fromisoformat(payload["period_start"])
        draft["period_end"] = date.fromisoformat(payload["period_end"])
        return dict(draft)

    def set_plan_draft_status(
        self,
        draft_id: int,
        coach_id: int,
        status: str,
        updated_at: datetime,
        approved_plan_id: int | None,
    ) -> dict | None:
        draft = self.drafts.get(draft_id)
        if draft is None or draft["coach_id"] != coach_id:
            return None
        draft["status"] = status
        draft["updated_at"] = updated_at
        draft["approved_plan_id"] = approved_plan_id
        return dict(draft)


class AiPlanDraftServiceTests(unittest.TestCase):
    def build_service(self) -> AiPlanDraftService:
        repository = InMemoryPlanDraftRepository()
        plan_service = PlanService(repository=repository)
        return AiPlanDraftService(repository=repository, plan_service=plan_service)

    def test_create_nutrition_draft_uses_dietary_preference(self):
        service = self.build_service()

        draft = service.create_draft(
            7,
            1,
            {
                "plan_kind": "nutrition",
                "period_type": "weekly",
                "period_start": "2026-05-22",
                "period_end": "2026-05-28",
                "dietary_preference": "vegetarian",
                "coach_prompt": "Keep meals simple.",
            },
        )

        self.assertEqual(draft["status"], "draft")
        self.assertEqual(draft["generation_preferences"]["dietary_preference"], "vegetarian")
        self.assertIn("vegetarian", draft["content"]["notes"])
        self.assertEqual(draft["source_context"]["client"]["current_goal_type"], "strength_training")

    def test_create_workout_draft_includes_mobility_and_stretching_timing(self):
        service = self.build_service()

        draft = service.create_draft(
            7,
            1,
            {
                "plan_kind": "workout",
                "period_type": "weekly",
                "period_start": "2026-05-22",
                "period_end": "2026-05-28",
                "coach_prompt": "Protect squat technique.",
            },
        )

        self.assertIn("Before workout", draft["content"]["mobility_drills"])
        self.assertIn("After workout", draft["content"]["stretching_plan"])
        self.assertIn("Add ankle mobility", draft["content"]["focus"])

    def test_rejects_client_not_owned_by_coach(self):
        service = self.build_service()

        with self.assertRaises(ValueError):
            service.create_draft(
                99,
                1,
                {
                    "plan_kind": "nutrition",
                    "period_type": "weekly",
                    "period_start": "2026-05-22",
                    "period_end": "2026-05-28",
                },
            )

    def test_approve_draft_creates_final_plan(self):
        service = self.build_service()
        draft = service.create_draft(
            7,
            1,
            {
                "plan_kind": "nutrition",
                "period_type": "weekly",
                "period_start": "2026-05-22",
                "period_end": "2026-05-28",
            },
        )

        approved_draft, plan = service.approve_draft(7, draft["id"])

        self.assertEqual(approved_draft["status"], "approved")
        self.assertEqual(approved_draft["approved_plan_id"], plan["id"])
        self.assertEqual(plan["content"]["summary"], draft["content"]["summary"])

    def test_discarded_draft_cannot_be_approved(self):
        service = self.build_service()
        draft = service.create_draft(
            7,
            1,
            {
                "plan_kind": "workout",
                "period_type": "weekly",
                "period_start": "2026-05-22",
                "period_end": "2026-05-28",
            },
        )

        discarded = service.discard_draft(7, draft["id"])

        self.assertEqual(discarded["status"], "discarded")
        with self.assertRaises(ValueError):
            service.approve_draft(7, draft["id"])


if __name__ == "__main__":
    unittest.main()
