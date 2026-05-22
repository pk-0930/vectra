# AI-Assisted Draft Plans

## Summary

Add AI-generated draft nutrition and workout plans inside the client workspace. The system should use the selected client's available data:

- profile details
- current goal
- latest nutrition/workout plan history
- progress-photo metadata, captions, and optionally original images through a vision-summary step
- latest completed form-analysis result
- coach feedback notes

The AI output must stay as a **draft** until the coach reviews, edits, and approves it. Approval converts the draft into the existing finalized nutrition/workout plan records, which can already be exported as PDFs.

Core product principle:

> AI creates a draft. The coach owns the final plan.

## Product Flow

### Nutrition Tab

Add a secondary CTA:

```text
AI Draft
```

Flow:

1. Coach opens a client's `Nutrition` tab.
2. Coach clicks the `AI Draft` action.
3. A drawer opens with:
   - plan period type
   - start date
   - end date
   - dietary preference
   - optional coach instruction field
4. Backend builds client context.
5. AI returns a draft nutrition plan.
6. UI shows editable draft fields.
7. Coach can:
   - edit draft
   - regenerate
   - discard
   - approve as plan
8. Approval creates a normal nutrition plan.
9. Existing PDF export works as-is.

### Workout Tab

Add the same secondary CTA:

```text
AI Draft
```

Workout drafts should factor in latest form-analysis findings more heavily, especially corrective cues, movement issues, mobility limitations, and recommended corrective work.

Workout drafts must include stretches and mobility drills, with clear timing for when the client should perform them during each workout session.

## Backend Plan

### New Data Model

Add a new table:

```text
ai_plan_drafts
```

Fields:

- `id`
- `client_id`
- `coach_id`
- `plan_kind`: `nutrition | workout`
- `status`: `draft | approved | discarded`
- `period_type`
- `period_start`
- `period_end`
- `title`
- `content_json`
- `source_context_json`
- `generation_preferences_json`
- `coach_prompt`
- `model_name`
- `created_at`
- `updated_at`
- `approved_plan_id`

Reasons to store drafts separately:

- avoids polluting final plan history
- supports review/edit before approval
- preserves traceability of what AI saw
- lets coaches return to unfinished drafts

### New Backend Endpoints

Recommended endpoints:

```text
POST /clients/{client_id}/plan-drafts
GET /clients/{client_id}/plan-drafts?plan_kind=nutrition
GET /plan-drafts/{draft_id}
PUT /plan-drafts/{draft_id}
POST /plan-drafts/{draft_id}/approve
POST /plan-drafts/{draft_id}/discard
```

Example `POST /clients/{client_id}/plan-drafts` payload:

```json
{
  "plan_kind": "nutrition",
  "period_type": "weekly",
  "period_start": "2026-05-20",
  "period_end": "2026-05-26",
  "dietary_preference": "vegetarian",
  "coach_prompt": "Keep this plan vegetarian and simple."
}
```

Approval should reuse the existing `PlanService.create_plan(...)` so final plans remain unchanged.

## AI Service Plan

Add a backend service:

```text
services/ai_plan_draft_service.py
```

Responsibilities:

1. Verify coach owns client.
2. Gather context:
   - client profile
   - current goal
   - recent progress photo metadata/captions
   - optional progress photo visual summaries generated from original images
   - latest completed form analysis
   - latest plan history for the same plan kind
3. Apply generation preferences such as dietary preference for nutrition drafts.
4. Build a structured prompt.
5. Call the AI provider.
6. Validate and normalize response into the existing `PlanPayload` shape.
7. Store the draft.

Given the app is already Azure-heavy, use **Azure OpenAI** as the default provider, with environment variables such as:

```text
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_API_KEY
AZURE_OPENAI_DEPLOYMENT
AZURE_OPENAI_API_VERSION
```

Keep AI integration behind one service class so the provider can be swapped later.

## Progress Photo Vision Context

Progress photos can provide useful coaching context beyond metadata and captions. To use them safely, the system should not simply attach raw images directly to the plan-generation prompt. Instead, use a separate vision-summary step.

Recommended flow:

1. Select a limited set of recent and relevant progress photos for the client.
2. Fetch original images from Blob Storage.
3. Send images to a vision-capable AI model with strict, coaching-safe instructions.
4. Convert image observations into a structured visual summary.
5. Feed the structured visual summary into the plan-draft generator along with profile, goal, captions, analysis, and plan history.

Example visual summary shape:

```json
{
  "photos_reviewed": 3,
  "date_range": "2026-05-01 to 2026-05-20",
  "quality_notes": "Lighting is inconsistent across images.",
  "visible_trends": [
    "Posture appears more upright in the latest front-view image.",
    "Midsection outline appears slightly reduced, but confidence is limited by clothing and lighting."
  ],
  "coaching_relevance": [
    "Continue progressive strength work and consistent nutrition targets.",
    "Use future photos with consistent lighting, distance, and pose."
  ],
  "confidence": "moderate",
  "limitations": [
    "Do not infer body fat percentage.",
    "Do not make medical or diagnostic claims."
  ]
}
```

Guardrails:

- Avoid medical claims.
- Avoid body-fat estimates or precise weight-change claims from images.
- Avoid judgmental or sensitive body language.
- Phrase observations as visual trend signals, not facts.
- Include confidence and image-quality limitations.
- Let the coach review any AI-generated visual observations.
- Prefer storing the derived visual summary in `source_context_json`; do not store raw image payloads in draft records.

Provider note:

- Azure OpenAI vision-capable deployments are preferred if available.
- If no vision-capable model is configured, draft generation should fall back to metadata/captions only.

## Draft Content Shape

Use the existing plan content shape for v1:

```ts
{
  summary: string;
  focus: string;
  meals?: string;
  workout_days?: string;
  notes?: string;
}
```

For nutrition:

- `summary`
- `focus`
- `meals`
- `notes`

For workout:

- `summary`
- `focus`
- `workout_days`
- `mobility_drills`
- `stretching_plan`
- `notes`

This avoids a PDF and UI redesign for v1.

Workout draft content should describe:

- workout structure by day
- warm-up sequence
- mobility drills before main lifts or movement blocks
- corrective drills tied to form-analysis findings
- cool-down stretches after training
- rest-day or low-intensity mobility recommendations when useful

Mobility and stretching guidance should clearly state timing, for example:

- before workout
- between warm-up and main sets
- between sets, only when appropriate
- after workout
- on recovery/rest days

## Nutrition Generation Preferences

For v1, dietary preference should be collected per nutrition draft instead of being added to the permanent client profile.

Recommended field:

```ts
type DietaryPreference =
  | "vegetarian"
  | "non_vegetarian"
  | "eggetarian"
  | "vegan"
  | "no_preference";
```

Nutrition draft generation should respect the selected dietary preference when suggesting meals and protein sources.

Out of scope for now:

- cuisine or regional food preferences
- Tamil Nadu-specific food plans
- allergy or medical restriction management
- permanent storage of dietary preference on the client profile

These can be added later as separate generation preferences or profile fields.

## Frontend Plan

Update `vectra-ui/src/services/planApi.ts` with draft APIs:

- create draft
- list drafts
- update draft
- approve draft
- discard draft

Update the client `Nutrition` and `Workout` tabs:

- Add an icon-led `AI Draft` button.
- Add draft drawer:
  - generation inputs
  - loading state
  - editable generated content
  - approve/discard/regenerate actions
- Show latest draft card if an unapproved draft exists.
- After approval, refresh finalized plan history.

Nutrition draft drawer inputs:

- plan period type
- start date
- end date
- dietary preference
- optional coach instructions

Workout draft drawer inputs:

- plan period type
- start date
- end date
- optional coach instructions

Workout AI generation rules:

- Include stretches and mobility drills in every generated workout draft.
- Use latest completed form-analysis results when available.
- Prefer mobility drills that address detected movement limitations, corrective recommendations, and coach feedback notes.
- Clearly state when each mobility drill or stretch should be performed within the workout session.
- Keep mobility work practical and coach-reviewable, not clinical or medical.
- If no form analysis exists, include general mobility work appropriate to the client's profile and goal.

AI draft CTA requirements:

- Use `lucide-react` `WandSparkles` or `Sparkles` icon.
- Button text should be `AI Draft`.
- Use a secondary or outline style, not the primary plan-approval style.
- Tooltip or accessible title: `Create an AI-assisted draft for coach review`.
- The action should appear in both `Nutrition` and `Workout` tab headers near the manual create-plan action.

## Safety and UX Rules

Use clear UI wording:

- `AI draft`
- `Review before approving`
- `Coach approval required`

Do not present AI output as final automatically.

Missing-data behavior:

- If no form analysis exists, still generate the plan but note that movement analysis was unavailable.
- If no progress photos exist, omit that context.
- If profile data is sparse, generate a conservative draft and tell the coach which inputs were missing.
- If no dietary preference is selected for a nutrition draft, use `no_preference`.

## Testing Plan

Backend:

- create draft for nutrition
- create nutrition draft with dietary preference
- create draft for workout
- create workout draft with mobility drills and stretch timing
- reject draft creation for clients not owned by coach
- approve draft creates final plan
- discarded draft cannot be approved
- AI service response normalization tests
- missing-context tests

Frontend:

- generate draft drawer renders in Nutrition and Workout
- nutrition draft drawer includes dietary preference
- loading/error states
- edit draft fields
- approve creates final plan and refreshes history
- discard removes active draft
- existing manual create/export flows still work
- workout drafts render mobility and stretching content clearly before approval

## Recommended Implementation Slices

Build this in three slices:

### Slice 1: Draft infrastructure without AI

- draft table
- draft endpoints
- approve/discard flow
- frontend draft UI
- deterministic mock draft generator

### Slice 2: AI generation

- add Azure OpenAI service
- replace mock generator
- add prompt/context handling
- add response validation

### Slice 3: Progress photo vision context

- add image retrieval for selected progress photos
- add vision-summary prompt and response validation
- include visual summary in `source_context_json`
- feed visual summary into nutrition/workout draft generation
- add fallback behavior when images are unavailable or no vision model is configured

This should come after text-based AI draft generation is working, unless a vision-capable model and image-safety review are already available.

This reduces implementation risk because the feature becomes testable before AI is introduced.
