import { API_BASE_URL } from "./apiConfig";
import { buildAuthHeaders } from "./session";
import type {
  Plan,
  PlanDraft,
  PlanDraftApproval,
  PlanDraftCreatePayload,
  PlanDraftUpdatePayload,
  PlanKind,
  PlanPayload,
} from "../types/plan";

async function readJsonOrThrow<T>(response: Response, fallback: string): Promise<T> {
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`${fallback} (${response.status}): ${errorText || "Unknown error"}`);
  }

  return (await response.json()) as T;
}

export async function listNutritionPlans(clientId: number): Promise<Plan[]> {
  const response = await fetch(`${API_BASE_URL}/clients/${clientId}/nutrition-plans`, {
    headers: buildAuthHeaders(),
  });

  return readJsonOrThrow<Plan[]>(response, "Failed to load nutrition plans");
}

export async function createNutritionPlan(clientId: number, payload: PlanPayload): Promise<Plan> {
  const response = await fetch(`${API_BASE_URL}/clients/${clientId}/nutrition-plans`, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
  });

  return readJsonOrThrow<Plan>(response, "Failed to create nutrition plan");
}

export async function listWorkoutPlans(clientId: number): Promise<Plan[]> {
  const response = await fetch(`${API_BASE_URL}/clients/${clientId}/workout-plans`, {
    headers: buildAuthHeaders(),
  });

  return readJsonOrThrow<Plan[]>(response, "Failed to load workout plans");
}

export async function createWorkoutPlan(clientId: number, payload: PlanPayload): Promise<Plan> {
  const response = await fetch(`${API_BASE_URL}/clients/${clientId}/workout-plans`, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
  });

  return readJsonOrThrow<Plan>(response, "Failed to create workout plan");
}

export async function createPlanDraft(clientId: number, payload: PlanDraftCreatePayload): Promise<PlanDraft> {
  const response = await fetch(`${API_BASE_URL}/clients/${clientId}/plan-drafts`, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
  });

  return readJsonOrThrow<PlanDraft>(response, "Failed to create AI draft");
}

export async function listPlanDrafts(clientId: number, planKind: PlanKind): Promise<PlanDraft[]> {
  const response = await fetch(`${API_BASE_URL}/clients/${clientId}/plan-drafts?plan_kind=${planKind}`, {
    headers: buildAuthHeaders(),
  });

  return readJsonOrThrow<PlanDraft[]>(response, "Failed to load AI drafts");
}

export async function updatePlanDraft(draftId: number, payload: PlanDraftUpdatePayload): Promise<PlanDraft> {
  const response = await fetch(`${API_BASE_URL}/plan-drafts/${draftId}`, {
    method: "PUT",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
  });

  return readJsonOrThrow<PlanDraft>(response, "Failed to update AI draft");
}

export async function approvePlanDraft(draftId: number): Promise<PlanDraftApproval> {
  const response = await fetch(`${API_BASE_URL}/plan-drafts/${draftId}/approve`, {
    method: "POST",
    headers: buildAuthHeaders(),
  });

  return readJsonOrThrow<PlanDraftApproval>(response, "Failed to approve AI draft");
}

export async function discardPlanDraft(draftId: number): Promise<PlanDraft> {
  const response = await fetch(`${API_BASE_URL}/plan-drafts/${draftId}/discard`, {
    method: "POST",
    headers: buildAuthHeaders(),
  });

  return readJsonOrThrow<PlanDraft>(response, "Failed to discard AI draft");
}

export function getNutritionPlanPdfUrl(planId: number) {
  return `${API_BASE_URL}/nutrition-plans/${planId}/pdf`;
}

export function getWorkoutPlanPdfUrl(planId: number) {
  return `${API_BASE_URL}/workout-plans/${planId}/pdf`;
}
