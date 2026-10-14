// Thin API helper. Uses the Vite proxy in dev (blank VITE_API_URL) or an
// absolute origin in production. Kept intentionally small; the generated client
// in packages/api-client replaces it once the API contract stabilises.
const BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

export async function request(path, { method = "GET", token, body, headers = {} } = {}) {
  const res = await fetch(`${BASE}/api/v1${path}`, {
    method,
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const message = data?.error?.message || data?.detail || res.statusText;
    throw new ApiError(message, res.status, data);
  }
  return data;
}

export const api = {
  health: () => request("/health"),
};
