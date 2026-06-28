import json
from typing import Any, Protocol
from urllib import request
from urllib.error import HTTPError, URLError

from config.azure_openai_config import AzureOpenAIConfig, get_azure_openai_config


class PlanDraftGenerationError(ValueError):
    pass


class PlanDraftGenerator(Protocol):
    model_name: str

    def generate(self, plan_kind: str, request_payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        ...


class DeterministicPlanDraftGenerator:
    model_name = "deterministic_mock_v1"

    def generate(self, plan_kind: str, request_payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        client = context["client"]
        goal = client.get("current_goal_type")
        goal_text = goal.replace("_", " ") if goal else "general fitness"
        coach_prompt = request_payload.get("coach_prompt") or "No extra coach instructions."
        title = f"AI draft {plan_kind} plan for {client['first_name']}"

        if plan_kind == "nutrition":
            dietary_preference = request_payload["generation_preferences"].get("dietary_preference", "no_preference")
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

        return normalize_generated_plan(plan_kind, {"title": title, "content": content})

    def _nutrition_meals(self, dietary_preference: str) -> str:
        protein_examples = {
            "vegetarian": "paneer, curd, dal, sprouts, tofu",
            "non_vegetarian": "eggs, chicken, fish, curd",
            "eggetarian": "eggs, curd, dal, paneer, sprouts",
            "vegan": "tofu, tempeh, dal, beans, sprouts",
            "no_preference": "eggs, curd, dal, paneer, chicken",
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


class AzureOpenAIPlanDraftGenerator:
    def __init__(self, config: AzureOpenAIConfig, timeout_seconds: int = 45):
        self.config = config
        self.timeout_seconds = timeout_seconds
        self.model_name = f"azure_openai:{config.deployment}"

    def generate(self, plan_kind: str, request_payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        prompt = build_plan_prompt(plan_kind, request_payload, context)
        payload = {
            "messages": [
                {"role": "system", "content": build_system_prompt(plan_kind)},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.25,
            "response_format": {"type": "json_object"},
        }
        response_payload = self._post_chat_completion(payload)
        content = self._extract_message_content(response_payload)
        try:
            generated = json.loads(content)
        except json.JSONDecodeError as exc:
            raise PlanDraftGenerationError("AI provider returned invalid JSON.") from exc
        return normalize_generated_plan(plan_kind, generated)

    def _post_chat_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            self.config.chat_completions_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "api-key": self.config.api_key,
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise PlanDraftGenerationError(f"AI provider request failed ({exc.code}): {detail}") from exc
        except (URLError, TimeoutError) as exc:
            raise PlanDraftGenerationError(f"AI provider request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise PlanDraftGenerationError("AI provider returned an unreadable response.") from exc

    def _extract_message_content(self, payload: dict[str, Any]) -> str:
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise PlanDraftGenerationError("AI provider response did not include message content.") from exc
        if not isinstance(content, str) or not content.strip():
            raise PlanDraftGenerationError("AI provider response content was empty.")
        return content


def build_default_plan_draft_generator() -> PlanDraftGenerator:
    config = get_azure_openai_config()
    if config is None:
        return DeterministicPlanDraftGenerator()
    return AzureOpenAIPlanDraftGenerator(config)


def build_system_prompt(plan_kind: str) -> str:
    base_rules = [
        "You create coach-reviewable fitness plan drafts only.",
        "The output is not final until a coach approves it.",
        "Return only valid JSON with keys title and content.",
        "Do not make medical claims, diagnoses, body-fat estimates, or injury treatment claims.",
        "Be practical, concise, and safe for a fitness coach to review.",
    ]
    if plan_kind == "workout":
        base_rules.extend(
            [
                "Workout drafts must include mobility_drills and stretching_plan.",
                "Every mobility drill or stretch must state when to perform it.",
                "Use form-analysis findings and coach feedback when available.",
            ]
        )
    return "\n".join(base_rules)


def build_plan_prompt(plan_kind: str, request_payload: dict[str, Any], context: dict[str, Any]) -> str:
    required_shape = {
        "nutrition": {
            "title": "string",
            "content": {
                "summary": "string",
                "focus": "string",
                "meals": "string",
                "notes": "string",
            },
        },
        "workout": {
            "title": "string",
            "content": {
                "summary": "string",
                "focus": "string",
                "workout_days": "string",
                "mobility_drills": "string",
                "stretching_plan": "string",
                "notes": "string",
            },
        },
    }[plan_kind]
    prompt_payload = {
        "plan_kind": plan_kind,
        "request": request_payload,
        "available_client_context": context,
        "required_response_shape": required_shape,
        "normalization_rules": [
            "Use empty strings only when source context is unavailable.",
            "Mention missing movement analysis only if latest_form_analysis is null.",
            "Respect nutrition dietary_preference when plan_kind is nutrition.",
            "Do not include raw source_context in the response.",
        ],
    }
    return json.dumps(prompt_payload, ensure_ascii=True, indent=2)


def normalize_generated_plan(plan_kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise PlanDraftGenerationError("Generated plan must be a JSON object.")

    title = payload.get("title")
    content = payload.get("content")
    if not isinstance(title, str) or not title.strip():
        raise PlanDraftGenerationError("Generated plan title is required.")
    if not isinstance(content, dict):
        raise PlanDraftGenerationError("Generated plan content is required.")

    required_keys = {
        "nutrition": ("summary", "focus", "meals", "notes"),
        "workout": ("summary", "focus", "workout_days", "mobility_drills", "stretching_plan", "notes"),
    }.get(plan_kind)
    if required_keys is None:
        raise PlanDraftGenerationError("Unsupported plan kind.")

    normalized_content: dict[str, str] = {}
    for key in required_keys:
        value = content.get(key)
        if value is None:
            raise PlanDraftGenerationError(f"Generated plan content is missing {key}.")
        if not isinstance(value, str):
            raise PlanDraftGenerationError(f"Generated plan content field {key} must be text.")
        normalized_content[key] = value.strip()

    return {
        "title": title.strip(),
        "content": normalized_content,
    }
