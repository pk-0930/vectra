import type { Client, ClientPayload, Goal, GoalPayload, ProgressPhoto } from "../types/client";
import { API_BASE_URL } from "./apiConfig";
import { buildAuthHeaders, getStoredAccessToken } from "./session";

export async function listClients(): Promise<Client[]> {
  const response = await fetch(`${API_BASE_URL}/clients`, {
    headers: buildAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Failed to load clients (${response.status})`);
  }

  return (await response.json()) as Client[];
}

export async function createClient(payload: ClientPayload): Promise<Client> {
  const response = await fetch(`${API_BASE_URL}/clients`, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to create client (${response.status}): ${errorText}`);
  }

  return (await response.json()) as Client;
}

export async function fetchClient(clientId: number): Promise<Client> {
  const response = await fetch(`${API_BASE_URL}/clients/${clientId}`, {
    headers: buildAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Failed to load client (${response.status})`);
  }

  return (await response.json()) as Client;
}

export async function updateClient(clientId: number, payload: ClientPayload): Promise<Client> {
  const response = await fetch(`${API_BASE_URL}/clients/${clientId}`, {
    method: "PUT",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to update client (${response.status}): ${errorText}`);
  }

  return (await response.json()) as Client;
}

export async function addClientGoal(clientId: number, payload: GoalPayload): Promise<Goal> {
  const response = await fetch(`${API_BASE_URL}/clients/${clientId}/goals`, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to save client goal (${response.status}): ${errorText}`);
  }

  return (await response.json()) as Goal;
}

export async function listClientProgressPhotos(clientId: number): Promise<ProgressPhoto[]> {
  const response = await fetch(`${API_BASE_URL}/clients/${clientId}/progress-photos`, {
    headers: buildAuthHeaders(),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to load client progress photos (${response.status}): ${errorText}`);
  }

  return (await response.json()) as ProgressPhoto[];
}

export async function uploadClientProgressPhoto(
  clientId: number,
  payload: {
    file: File;
    timeline_type: string;
    captured_on: string;
    caption?: string;
  }
): Promise<ProgressPhoto> {
  const formData = new FormData();
  formData.append("file", payload.file);

  const searchParams = new URLSearchParams({
    timeline_type: payload.timeline_type,
    captured_on: payload.captured_on,
  });
  if (payload.caption) {
    searchParams.set("caption", payload.caption);
  }

  const response = await fetch(`${API_BASE_URL}/clients/${clientId}/progress-photos?${searchParams.toString()}`, {
    method: "POST",
    headers: buildAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to upload progress photo (${response.status}): ${errorText}`);
  }

  return (await response.json()) as ProgressPhoto;
}

export function getClientProgressPhotoUrl(blobName: string) {
  const token = getStoredAccessToken();
  return `${API_BASE_URL}/client-progress-photos/${blobName}?token=${encodeURIComponent(token)}`;
}
