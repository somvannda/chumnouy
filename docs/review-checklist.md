# Review checklist

The v1 platform was merged on green CI **without** a human review pass, so this is
a **retrospective** checklist. Work top-down; tick items as they are cleared.
File paths are relative to the repo root.

## 1. Security-sensitive code (highest priority)

| Area | Files | Verify |
|---|---|---|
| Attachment claim | `chumnouy_api/app/services/attachments.py`, `chumnouy_api/app/media.py` | Only the caller's own, still-unowned rows are claimed (tenant isolation); a row cannot be claimed twice; upload suffix/size validation; stored path cannot escape `MEDIA_ROOT`. |
| Webhook signing | `chumnouy_api/app/services/webhooks.py`, `chumnouy_api/app/models.py` (`Webhook.secret`) | HMAC is `sha256(secret, "<timestamp>.<body>")`; retry/backoff and terminal failure; replay resets correctly; **the signing secret is stored in plaintext** — accept or change. |
| Requester portal tokens | `chumnouy_api/app/deps.py` (`get_requester_context`), `app/services/requesters.py`, `app/services/public.py` | Token stored only as SHA-256; a token reaches only its own workspace/tickets; **only public messages are returned** (internal notes hidden); unauthenticated requests are 401. |
| Platform admin credential | `chumnouy_api/app/deps.py` (`get_platform_admin`), `app/api/admin.py` | Cross-tenant access requires `platform_role ∈ {admin, super_admin}`; a tenant API key can never reach `/api/admin`. |
| Idempotency store | `chumnouy_api/app/services/idempotency.py`, `app/api/tickets.py` | Keys are per workspace; a repeat returns the stored response; no cross-tenant replay; the check-then-store race window is acceptable. |
| Error envelope | `chumnouy_api/app/errors.py` | No internal detail leaks via `message`; validation `details` do not expose secrets. |
| Notifyr hand-off | `chumnouy_api/app/services/notifyr.py`, `app/services/workspace_settings.py` | Per-workspace URL/key override; secrets write-only; outbox retry/backoff; unconfigured workspace enqueues nothing. |
| AI assistant | `chumnouy_api/app/api/assistant.py`, `app/services/ai.py`, `app/services/assistant.py` | SSE plus post-stream session lifetime (`persist_message_standalone`); per-workspace provider key; rate limiting. |
| Widget token handling | `packages/widget/chumnouy-widget.js` | Token is passed in, sent as `X-Requester-Token`, never logged; only public endpoints are called. |
| Console session | `apps/web/src/context/auth.jsx`, `apps/web/src/lib/session.js` | JWT is stored in `localStorage` (XSS exposure) — accept or change; sign-out clears it. |

## 2. Decisions needing sign-off

- **Error envelope is breaking** — every error is now
  `{ "error": { "code", "message", "details" } }` (was `{ "detail": … }`). Fine
  pre-launch; confirm.
- **Notifyr is queued, not inline** — hand-offs go through an outbox with retry;
  confirm the delivery-semantics change.
- **Worker**: `WEBHOOK_WORKER_ENABLED` (default **off**) vs a dedicated external
  drainer; one drainer per database.
- **Public rate limit**: in-process, per client IP, `PUBLIC_RATE_LIMIT_PER_MINUTE`
  (default 120); confirm the value and that per-worker (not global) is acceptable.
- **Widget** ships alongside the customer portal — confirm the call.
- **`@chmaba/ui`** is still a vendored copy — publish a package or keep vendored.
- **Deployment topology** (`deploy/README.md`): persistent `MEDIA_ROOT` volume;
  who serves `/media` (API `StaticFiles` vs reverse proxy/CDN).

## 3. Process / after-the-fact review

- **Merged PRs**: #1 (attachments), #23 (consolidated platform — the large one),
  #24 (API client), #25 (CI client drift check). Stacked PRs #2–#22 were closed
  as superseded.
- **`packages/api-client/src/client.ts`** — the hand-written wrapper (the
  generated `schema.ts` is mechanical).
- **Migrations `0001`–`0009`** — `alembic heads` is a single head; up/down paths
  are as intended.

## Suggested order

1. Section 1, items 1–4 (auth / tenancy / crypto) — the real risk surface.
2. Section 2 (breaking and behavioural decisions).
3. Section 3 (skim #23 and the API client).
