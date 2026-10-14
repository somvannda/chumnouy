# Tenancy Model

How Chumnouy isolates one customer's support data from another's, and how a
credential turns into a scoped workspace context.

See `docs/architecture.md` ADR-003 / ADR-004 / ADR-009 for the decisions.

## The three levels

```
Account                     who owns / pays
  └─ Workspace              hard isolation boundary  (all rows carry workspace_id)
       ├─ Integration       a client app (Chmaba POS, website, mobile)
       │    ├─ ApiKey       test / live, scoped
       │    └─ Webhook      events -> external URL
       ├─ Agent             a human (membership + role)
       ├─ Requester         an external end user (integrator's customer)
       └─ Ticket / Knowledge / Assistant data
```

### Account

The signup entity. An account can own one workspace (small teams) or many (an
agency, a multi-brand operator). Billing and platform-level quota attach here in
a later phase.

### Workspace

The isolation boundary. **Every tenant table has a non-null `workspace_id`**, and
every read/write is scoped by the workspace resolved from the caller's credential.
There is no "select all tickets" anywhere in the service layer — the workspace
filter is mandatory.

### Integration

A registered client inside a workspace. This is what makes Chumnouy reusable: the
same workspace can host "Chmaba POS", "Storefront" and "Mobile" as distinct
integrations, each with its own keys, webhooks and scopes, and each tagged on the
tickets it creates (`source_integration_id`).

## Credential → context resolution

`deps.py` resolves exactly one of these per request:

| Credential | Header | Resolves to |
|---|---|---|
| API key | `Authorization: Bearer chm_live_…` / `X-Api-Key` | integration → workspace, scopes, environment |
| User JWT | `Authorization: Bearer <jwt>` | membership → workspace, role |
| Requester token | `Authorization: Bearer chm_req_…` | single requester → their tickets only |

The resolved context object is passed to the service layer. Services take a
`workspace_id` argument; they never read it from the request body or the model's
arguments, so a caller cannot address another workspace.

## Rules

1. **Scope on every query.** Repository helpers require `workspace_id`. A missing
   scope is a code error, not a runtime default.
2. **No ids from the model / no ids from untrusted input for tenancy.** Ticket
   ids come from the URL; workspace comes from the credential. The two are
   checked together before any row is returned.
3. **Integrations cannot exceed their scopes.** A `tickets:read` key cannot post
   a reply, manage webhooks, or use the assistant.
4. **Requesters are workspace-scoped.** The same external id in two workspaces is
   two different `requesters` rows.
5. **Cross-workspace references are not allowed.** Attachments, messages,
   knowledge and assistant data all belong to the ticket's workspace; claiming a
   foreign attachment id is rejected (ported from Chmaba's `bind_attachments`).
6. **Audit per workspace.** `ticket_events` records who did what, scoped to the
   workspace, and is surfaced in the console timeline.

## Hardening (later, not v1)

- Postgres row-level security policies as defense-in-depth.
- Per-integration rate limits and anomaly detection.
- Encryption of ticket bodies at rest if a customer requires it.

## What this replaces in Chmaba POS

| Chmaba POS | Chumnouy |
|---|---|
| `company_id` | `workspace_id` |
| `store_id` (on tickets) | `source_integration_id` + `ticket.metadata.store_id` |
| `user_id` (merchant who opened) | `requester` (external) or `agent` (staff) |
| platform admin sees all companies | platform operator sees all workspaces (admin API) |
