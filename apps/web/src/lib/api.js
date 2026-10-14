// Thin API helper. Uses the Vite proxy in dev (blank VITE_API_URL) or an
// absolute origin in production. Kept intentionally small; the generated client
// in packages/api-client replaces it once the API contract stabilises.
import { buildQuery } from "./format";

const BASE = ((import.meta.env?.VITE_API_URL) || "").replace(/\/$/, "");

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

  // Auth (console)
  signup: (body) => request("/auth/signup", { method: "POST", body }),
  login: (body) => request("/auth/login", { method: "POST", body }),
  me: (token) => request("/auth/me", { token }),

  // Tickets
  listTickets: (token, params = {}) => request(`/tickets${buildQuery(params)}`, { token }),
  getTicket: (token, id) => request(`/tickets/${id}`, { token }),
  updateTicket: (token, id, body) => request(`/tickets/${id}`, { method: "PATCH", token, body }),
  replyTicket: (token, id, body) =>
    request(`/tickets/${id}/messages`, { method: "POST", token, body }),
  resolveTicket: (token, id) => request(`/tickets/${id}/resolve`, { method: "POST", token }),
  reopenTicket: (token, id) => request(`/tickets/${id}/reopen`, { method: "POST", token }),
  ticketEvents: (token, id) => request(`/tickets/${id}/events`, { token }),

  // Integrations & API keys
  listIntegrations: (token) => request("/integrations", { token }),
  createIntegration: (token, body) => request("/integrations", { method: "POST", token, body }),
  listKeys: (token, integrationId) => request(`/integrations/${integrationId}/keys`, { token }),
  createKey: (token, integrationId, body) =>
    request(`/integrations/${integrationId}/keys`, { method: "POST", token, body }),
  revokeKey: (token, keyId) =>
    request(`/integrations/keys/${keyId}/revoke`, { method: "POST", token }),

  // Console settings
  getSettings: (token) => request("/console/settings", { token }),
  updateAISettings: (token, body) =>
    request("/console/settings/ai", { method: "PATCH", token, body }),
  updateNotificationSettings: (token, body) =>
    request("/console/settings/notifications", { method: "PATCH", token, body }),

  // Knowledge base
  listKnowledge: (token, params = {}) =>
    request(`/knowledge/articles${buildQuery(params)}`, { token }),
  getKnowledgeArticle: (token, id) => request(`/knowledge/articles/${id}`, { token }),
  createKnowledgeArticle: (token, body) =>
    request("/knowledge/articles", { method: "POST", token, body }),
  updateKnowledgeArticle: (token, id, body) =>
    request(`/knowledge/articles/${id}`, { method: "PATCH", token, body }),
  restoreKnowledgeArticle: (token, id) =>
    request(`/knowledge/articles/${id}/restore`, { method: "POST", token }),
};
