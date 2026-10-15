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

export async function request(path, { method = "GET", token, body, headers = {}, base = "/api/v1" } = {}) {
  const res = await fetch(`${BASE}${base}${path}`, {
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

  // Platform admin (separate prefix + credential)
  adminUsage: (token) => request("/usage", { token, base: "/api/admin" }),
  adminAccounts: (token) => request("/accounts", { token, base: "/api/admin" }),
  adminWorkspaces: (token, params = {}) =>
    request(`/workspaces${buildQuery(params)}`, { token, base: "/api/admin" }),
  adminWorkspace: (token, id) => request(`/workspaces/${id}`, { token, base: "/api/admin" }),
  updateAdminWorkspace: (token, id, body) =>
    request(`/workspaces/${id}`, { method: "PATCH", token, base: "/api/admin", body }),

  // Requesters
  listRequesters: (token, params = {}) => request(`/requesters${buildQuery(params)}`, { token }),
  getRequester: (token, id) => request(`/requesters/${id}`, { token }),
  updateRequester: (token, id, body) =>
    request(`/requesters/${id}`, { method: "PATCH", token, body }),
  issuePortalToken: (token, id) =>
    request(`/requesters/${id}/portal-token`, { method: "POST", token }),

  // Assistant
  listConversations: (token) => request("/assistant/conversations", { token }),
  getConversation: (token, id) => request(`/assistant/conversations/${id}`, { token }),
  assistantFeedback: (token, body) =>
    request("/assistant/feedback", { method: "POST", token, body }),

  // Webhooks
  listWebhooks: (token) => request("/webhooks", { token }),
  createWebhook: (token, body) => request("/webhooks", { method: "POST", token, body }),
  updateWebhook: (token, id, body) =>
    request(`/webhooks/${id}`, { method: "PATCH", token, body }),
  deleteWebhook: (token, id) => request(`/webhooks/${id}`, { method: "DELETE", token }),
  webhookDeliveries: (token, id, params = {}) =>
    request(`/webhooks/${id}/deliveries${buildQuery(params)}`, { token }),
  replayWebhookDelivery: (token, deliveryId) =>
    request(`/webhooks/deliveries/${deliveryId}/replay`, { method: "POST", token }),

  // Public help centre (no auth; addressed by workspace slug)
  helpIndex: (slug, params = {}) => request(`/public/help/${slug}${buildQuery(params)}`),
  helpArticle: (slug, articleSlug, params = {}) =>
    request(`/public/help/${slug}/articles/${articleSlug}${buildQuery(params)}`),
};

function parseSse(chunk) {
  let event = "message";
  let data = "";
  for (const line of chunk.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return null;
  try {
    return { event, data: JSON.parse(data) };
  } catch {
    return null;
  }
}

// Streams POST /assistant/chat (SSE). Calls `onEvent({ event, data })` per event
// and returns when the stream ends. Throws ApiError on a non-2xx response.
export async function chatStream(token, body, { onEvent, signal } = {}) {
  const res = await fetch(`${BASE}/api/v1/assistant/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    const text = await res.text();
    let detail = res.statusText;
    try {
      detail = JSON.parse(text)?.detail || detail;
    } catch {
      /* keep statusText */
    }
    throw new ApiError(detail, res.status);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let index = buffer.indexOf("\n\n");
    while (index !== -1) {
      const event = parseSse(buffer.slice(0, index));
      buffer = buffer.slice(index + 2);
      if (event && onEvent) onEvent(event);
      index = buffer.indexOf("\n\n");
    }
  }
}
