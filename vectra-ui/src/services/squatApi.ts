import type { SquatApiResponse } from "../types/squat";

const API_BASE_URL = "http://localhost:8000";
const SQUAT_ANALYSIS_ENDPOINT = `${API_BASE_URL}/analyze/squat`;

export async function analyzeSquatVideo(file: File): Promise<SquatApiResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(SQUAT_ANALYSIS_ENDPOINT, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      `Squat analysis failed (${response.status}): ${errorText || "Unknown error"}`
    );
  }

  const data = (await response.json()) as SquatApiResponse;
  return data;
}