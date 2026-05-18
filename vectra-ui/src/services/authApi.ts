import type { LoginRequest, LoginResponse } from "../types/auth";
import { API_BASE_URL } from "./apiConfig";
import { buildAuthHeaders, setStoredAccessToken } from "./session";

const SIGN_IN_ENDPOINT = `${API_BASE_URL}/auth/signin`;
const SIGN_UP_ENDPOINT = `${API_BASE_URL}/auth/signup`;

export async function loginUser(payload: LoginRequest): Promise<LoginResponse> {
  const response = await fetch(SIGN_IN_ENDPOINT, {
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

  const data = (await response.json()) as LoginResponse;
  setStoredAccessToken(data.access_token);
  return data;
}

export async function signupCoach(payload: {
  email: string;
  password: string;
  coach: {
    first_name: string;
    last_name: string;
  };
}): Promise<LoginResponse> {
  const response = await fetch(SIGN_UP_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(errorData.detail ?? `Signup failed (${response.status})`);
  }

  const data = (await response.json()) as LoginResponse;
  setStoredAccessToken(data.access_token);
  return data;
}

export async function fetchCurrentUser(): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: buildAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Failed to restore session (${response.status})`);
  }

  return (await response.json()) as LoginResponse;
}
