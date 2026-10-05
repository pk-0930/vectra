const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

if (!configuredApiBaseUrl) {
  throw new Error("VITE_API_BASE_URL must be configured for this build");
}

export const API_BASE_URL = configuredApiBaseUrl.replace(/\/$/, "");
