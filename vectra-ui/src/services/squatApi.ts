import { API_BASE_URL } from "./apiConfig";
import type { SquatJobListResponse, SquatJobResponse } from "../types/squat";
import { buildAuthHeaders } from "./session";

const FORM_ANALYSIS_ENDPOINT = `${API_BASE_URL}/form-analyses`;

export async function createSquatJob(file: File, clientId: number): Promise<SquatJobResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/clients/${clientId}/form-analyses?analysis_type=squat`, {
    method: "POST",
    headers: buildAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      `Squat job creation failed (${response.status}): ${errorText || "Unknown error"}`
    );
  }

  return (await response.json()) as SquatJobResponse;
}

export async function fetchSquatJob(jobId: string): Promise<SquatJobResponse> {
  const response = await fetch(`${FORM_ANALYSIS_ENDPOINT}/${jobId}`, {
    headers: buildAuthHeaders(),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      `Failed to fetch squat job (${response.status}): ${errorText || "Unknown error"}`
    );
  }

  return (await response.json()) as SquatJobResponse;
}

export async function listSquatJobs(limit = 12): Promise<SquatJobListResponse> {
  const response = await fetch(`${FORM_ANALYSIS_ENDPOINT}?limit=${limit}`, {
    headers: buildAuthHeaders(),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      `Failed to load job history (${response.status}): ${errorText || "Unknown error"}`
    );
  }

  return (await response.json()) as SquatJobListResponse;
}

export async function listClientSquatJobs(clientId: number, limit = 12): Promise<SquatJobListResponse> {
  const response = await fetch(`${API_BASE_URL}/clients/${clientId}/form-analyses?limit=${limit}`, {
    headers: buildAuthHeaders(),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      `Failed to load client analysis history (${response.status}): ${errorText || "Unknown error"}`
    );
  }

  return (await response.json()) as SquatJobListResponse;
}

export async function saveAnalysisFeedback(jobId: string, coachFeedbackNote: string): Promise<SquatJobResponse> {
  const response = await fetch(`${FORM_ANALYSIS_ENDPOINT}/${jobId}/feedback`, {
    method: "PUT",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({ coach_feedback_note: coachFeedbackNote }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to save analysis feedback (${response.status}): ${errorText || "Unknown error"}`);
  }

  return (await response.json()) as SquatJobResponse;
}

export function getFormAnalysisPdfUrl(jobId: string) {
  return `${FORM_ANALYSIS_ENDPOINT}/${jobId}/pdf`;
}
