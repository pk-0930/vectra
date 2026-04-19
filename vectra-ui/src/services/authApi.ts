import type { LoginRequest, LoginResponse } from "../types/auth";

const API_BASE_URL = "http://localhost:8000";
const LOGIN_ENDPOINT = `${API_BASE_URL}/login`;

export async function loginUser(payload: LoginRequest): Promise<LoginResponse> {
  const response = await fetch(LOGIN_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorMessage = "Login failed.";

    try {
      const errorData = (await response.json()) as { detail?: string };
      if (errorData.detail) {
        errorMessage = errorData.detail;
      }
    } catch {
      errorMessage = `Login failed (${response.status})`;
    }

    throw new Error(errorMessage);
  }

  return (await response.json()) as LoginResponse;
}
