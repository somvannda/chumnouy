# Reuse from Chmaba POS

What to lift from `E:\Development\Chmaba` and how to generalize it. This is the
"don't build it again" inventory: the POS already has every hard part of a support
system; Chumnouy re-homes it behind a public API.

## 1. Direct ports (adapt, don't rewrite)

| Chumnouy module | Chmaba POS source | Change |
|---|---|---|
| `services/tickets.py` | `app/services/support_tickets.py` | `company_id`→`workspace_id`; add `requester`; add assignment/tags/SLA; keep `bind_attachments`, `ticket_detail_read` logic |
| `models.py::Ticket*` | `app/models.py` `SupportTicket*` (≈1498–1570) | same shape, tenancy renamed, add `requester_id`, `priority`, `tags`, `assignee_user_id`, `source_integration_id` |
| `services/knowledge.py` | `app/services/help_repo.py` + `app/support_content.py` | corpus becomes per-workspace; port the seeded default articles as templates |
| `services/assistant.py` | `app/services/support.py` | provider plumbing stays; grounding by workspace corpus |
| `services/assistant_tools.py` | `app/services/support_tools.py` | read-only tools become an integrator-supplied contract |
| `services/ai.py` | `app/services/ai.py` | unchanged concept: `load_ai_settings`, `resolve_provider`, `complete_chat`, streaming, error types |
| console `SupportChat` | `apps/web/src/components/SupportChat.jsx` | reuse the streaming UI component |
| console `HelpContent` | `apps/admin` help editor | becomes workspace-scoped knowledge editor |

## 2. Reusable without change

- **Attachment staging/claim** — `bind_attachments` (security-critical: only the
  caller's own unowned rows can be claimed). Port as-is.
- **Thread rendering** — `ticket_detail_read`, including `include_system` hiding
  the assistant's system note from the requester.
- **AI reply rewrite / suggest** — `rewrite_reply`, `suggest_reply` (agent tools).
- **Branded email shell** — `app/services/email_layout.py` (`transactional_email`,
  `data_table`) is the *template* Notifyr will use; Chumnouy calls Notifyr, not
  this file.
- **Design system** — `packages/ui` (`tokens.css`, `tailwind-preset.js`) already
  vendored into this repo; the console must use it.

## 3. Redesign (the parts coupled to the POS)

- **Escalation ("talk to a human")** in Chmaba is tied to the AI support flow.
  In Chumnouy, a ticket is a first-class resource any integration can create —
  the AI assistant becomes an optional path *into* a ticket, not the entry point.
- **Notifications** — Chmaba has `store_notifications.py` (30 KB) and email
  senders. Chumnouy does **not** port these; it calls **Notifyr**.
- **Admin insights** — Chmaba's `AdminSupportInsights` reads platform activity.
  Chumnouy gets a workspace-scoped analytics view in the console.
- **`notify_ticket_merchants`** — replace with a Chumnouy→Notifyr call.

## 4. Deliberately NOT carried over

- POS models (`Company`, `Store`, `Membership`, orders, inventory) — not relevant.
- Billing/subscription logic — platform-owned, out of Chumnouy scope.
- Telegram digest — Notifyr's channel concern.
- Anything that writes to the merchant's POS data from a ticket.

## 5. Reuse of the AI provider layer

Chmaba resolves AI config from `platform_settings` with env fallbacks
(`AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL`, `AI_BASE_URL`) and exposes
`AINotConfiguredError` / `AIError`. Chumnouy keeps the same shape but the config
is **per workspace** (a workspace brings its own key), with an optional
platform-provided default so a trial workspace works out of the box.

## 6. Field mapping (one table)

| Chmaba | Chumnouy |
|---|---|
| `SupportTicket.company_id` | `tickets.workspace_id` |
| `SupportTicket.user_id` | `tickets.requester_id` → `requesters` |
| `SupportTicket.store_id` | `tickets.metadata.store_id` |
| `SupportTicket.question` | `tickets` + first `ticket_messages` row (or `subject` + body) |
| `SupportTicket.status` (`open`/`resolved`) | `status` ∈ `open`,`pending`,`resolved`,`closed` |
| `SupportTicket.resolution_note` | last agent message + `ticket_events` entry |
| `SupportTicketMessage.author_type` | same (`requester`/`agent`/`system`/`ai`) |
| `SupportTicketAttachment.company_id` | `ticket_attachments.workspace_id` |

## 7. Sequencing

Port in the order of `docs/architecture.md` §10. Ports happen **after** tenancy +
tickets core exist, so the ported code lands into the generalized model rather
than a POS-shaped one.
