export type PlanPeriodType = "weekly" | "monthly";

export type PlanContent = {
  summary: string;
  focus: string;
  meals?: string;
  workout_days?: string;
  mobility_drills?: string;
  stretching_plan?: string;
  notes?: string;
  [key: string]: string | undefined;
};

export type Plan = {
  id: number;
  client_id: number;
  period_type: PlanPeriodType;
  period_start: string;
  period_end: string;
  title: string;
  content: PlanContent;
  pdf_blob_name: string | null;
  created_by_coach_id: number;
  created_at: string;
  updated_at: string;
};

export type PlanPayload = {
  period_type: PlanPeriodType;
  period_start: string;
  period_end: string;
  title: string;
  content: PlanContent;
};

export type PlanKind = "nutrition" | "workout";

export type DietaryPreference =
  | "vegetarian"
  | "non_vegetarian"
  | "eggetarian"
  | "vegan"
  | "no_preference";

export type PlanDraftStatus = "draft" | "approved" | "discarded";

export type PlanDraft = {
  id: number;
  client_id: number;
  coach_id: number;
  plan_kind: PlanKind;
  status: PlanDraftStatus;
  period_type: PlanPeriodType;
  period_start: string;
  period_end: string;
  title: string;
  content: PlanContent;
  source_context: Record<string, unknown>;
  generation_preferences: Record<string, unknown>;
  coach_prompt: string | null;
  model_name: string;
  created_at: string;
  updated_at: string;
  approved_plan_id: number | null;
};

export type PlanDraftCreatePayload = {
  plan_kind: PlanKind;
  period_type: PlanPeriodType;
  period_start: string;
  period_end: string;
  dietary_preference?: DietaryPreference;
  coach_prompt?: string;
};

export type PlanDraftUpdatePayload = {
  period_type: PlanPeriodType;
  period_start: string;
  period_end: string;
  title: string;
  content: PlanContent;
  coach_prompt?: string;
};

export type PlanDraftApproval = {
  draft: PlanDraft;
  plan: Plan;
};
