export type PlanPeriodType = "weekly" | "monthly";

export type PlanContent = {
  summary: string;
  focus: string;
  meals?: string;
  workout_days?: string;
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
