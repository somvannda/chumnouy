// Typed, dependency-free client for the Chumnouy API.
//
//   import { createClient } from "@chumnouy/api-client";
//   const api = createClient({ baseUrl: "https://api.chumnouy.chmaba.com", token });
//   const ticket = await api.getTicket(id);
//
// Types come from ./schema.ts, which is generated from the committed OpenAPI
// spec (npm run generate).
import type {
  ApiKeyCreate,
  ApiKeyCreated,
  ApiKeyRead,
  AuthRead,
  HealthRead,
  IntegrationCreate,
  IntegrationRead,
  LoginRequest,
  MeRead,
  SignupRequest,
  TicketCreate,
  TicketDetailRead,
  TicketListRead,
  TicketMessageCreate,
  TicketMessageRead,
  TicketRead,
} from "./schema";

export interface ClientOptions {
  baseUrl?: string;
  token?: string;
  headers?: Record<string, string>;
}

export class ApiError extends Error {
  status: number;
  code?: string;
  details?: unknown;

  constructor(message: string, status: number, code?: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  token?: string;
  headers?: Record<string, string>;
  base?: string;
}

export interface WriteOptions {
  token?: string;
  idempotencyKey?: string;
}

export interface TicketQuery {
  status?: string;
  priority?: string;
  assignee?: string;
  integration?: string;
  q?: string;
  limit?: number;
  cursor?: string;
}

function query(params: Record<string, unknown> = {}): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export function createClient(options: ClientOptions = {}) {
  const base = (options.baseUrl ?? "").replace(/\/$/, "");
  const defaultToken = options.token;

  async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
    const res = await fetch(`${base}${opts.base ?? "/api/v1"}${path}`, {
      method: opts.method ?? "GET",
      headers: {
        ...(opts.body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(opts.token ? { Authorization: `Bearer ${opts.token}` } : {}),
        ...options.headers,
        ...opts.headers,
      },
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
    const text = await res.text();
    const data = text ? JSON.parse(text) : null;
    if (!res.ok) {
      const error = data?.error;
      throw new ApiError(error?.message ?? res.statusText, res.status, error?.code, error?.details);
    }
    return data as T;
  }

  function writeHeaders(opts: WriteOptions): Record<string, string> {
    return opts.idempotencyKey ? { "Idempotency-Key": opts.idempotencyKey } : {};
  }

  return {
    // System
    health: () => request<HealthRead>("/health"),

    // Console auth
    signup: (body: SignupRequest) => request<AuthRead>("/auth/signup", { method: "POST", body }),
    login: (body: LoginRequest) => request<AuthRead>("/auth/login", { method: "POST", body }),
    me: (token = defaultToken) => request<MeRead>("/auth/me", { token }),

    // Tickets
    listTickets: (params: TicketQuery = {}, token = defaultToken) =>
      request<TicketListRead>(`/tickets${query(params)}`, { token }),
    getTicket: (id: string, token = defaultToken) =>
      request<TicketDetailRead>(`/tickets/${id}`, { token }),
    createTicket: (body: TicketCreate, opts: WriteOptions = {}) =>
      request<TicketDetailRead>("/tickets", {
        method: "POST",
        body,
        token: opts.token ?? defaultToken,
        headers: writeHeaders(opts),
      }),
    updateTicket: (id: string, body: Partial<TicketCreate>, token = defaultToken) =>
      request<TicketRead>(`/tickets/${id}`, { method: "PATCH", body, token }),
    replyTicket: (id: string, body: TicketMessageCreate, opts: WriteOptions = {}) =>
      request<TicketMessageRead>(`/tickets/${id}/messages`, {
        method: "POST",
        body,
        token: opts.token ?? defaultToken,
        headers: writeHeaders(opts),
      }),
    resolveTicket: (id: string, token = defaultToken) =>
      request<TicketRead>(`/tickets/${id}/resolve`, { method: "POST", token }),
    reopenTicket: (id: string, token = defaultToken) =>
      request<TicketRead>(`/tickets/${id}/reopen`, { method: "POST", token }),

    // Integrations & keys
    listIntegrations: (token = defaultToken) =>
      request<IntegrationRead[]>("/integrations", { token }),
    createIntegration: (body: IntegrationCreate, token = defaultToken) =>
      request<IntegrationRead>("/integrations", { method: "POST", body, token }),
    listKeys: (integrationId: string, token = defaultToken) =>
      request<ApiKeyRead[]>(`/integrations/${integrationId}/keys`, { token }),
    createKey: (integrationId: string, body: ApiKeyCreate, token = defaultToken) =>
      request<ApiKeyCreated>(`/integrations/${integrationId}/keys`, { method: "POST", body, token }),
    revokeKey: (keyId: string, token = defaultToken) =>
      request<ApiKeyRead>(`/integrations/keys/${keyId}/revoke`, { method: "POST", token }),

    // Platform admin (separate prefix + credential)
    adminUsage: (token = defaultToken) =>
      request<Record<string, number>>("/usage", { token, base: "/api/admin" }),
  };
}

export type ChumnouyClient = ReturnType<typeof createClient>;
