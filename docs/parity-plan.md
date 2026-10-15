# Parity plan — closing the gap with Chatwoot / Zendesk / Freshdesk

A plan to grow Chumnouy from a strong **API-first, multi-tenant ticket core** into
something **feature-comparable** to an established support platform.

- **Primary target: Chatwoot** — the closest in *shape* (open-source,
  self-hostable, omni-channel) and the most realistic parity bar.
- **Secondary target: Zendesk / Freshdesk "table stakes"** — the features a buyer
  assumes exist (SLA, automation, reporting, CSAT, SSO).

We do **not** aim to out-Zendesk Zendesk. We keep our differentiator — *build
support once, embed it everywhere* (self-serve workspace + scoped API keys +
per-workspace BYO AI + delivery decoupled to Notifyr) — and fill the functional
gaps around it.

> Baseline comparison and reasoning: see the scorecard in the session that
> produced this plan; statuses below reflect the repo at `main` when written.

## 1. Guiding principles

1. **API-first, console second.** Every capability lands as an API with tests;
   the console is a client of it.
2. **Stay multi-tenant.** No per-account assumptions; everything is
   workspace-scoped and keyed.
3. **Don't build delivery.** Outbound email/SMS/chat/push stay in **Notifyr**;
   Chumnouy emits events. Channels we "add" are mostly *inbound* + config, with
   transport delegated.
4. **Reuse the ledger pattern.** Anything with retries (webhooks, Notifyr,
   SLA sweeps, automations) uses the outbox/worker pattern already in place.
5. **Measurable parity.** Every phase moves a scored matrix (§3); we track the
   percentage of the matrix at "have".

## 2. Current status (baseline)

| Area | Status |
|---|---|
| Ticketing core, attachments (images), knowledge API, AI chat/draft, public surface + widget, agent console, admin, Notifyr outbox, idempotency, rate limits, error envelope, self-host compose | **have** |
| Attachments breadth, AI depth, console depth, collaboration (@mentions/teams), search, security/compliance, help-centre portal | **partial** |
| Channels, SLA, automation, macros, reporting, CSAT | **missing** |

## 3. Parity matrix (the scoreboard)

Track each row as **have / partial / missing**; the goal is Chatwoot rows at
`have`, and Zendesk/Freshdesk table stakes at `have` or an explicit
`not planned`.

Rows (initial):

`ticketing-core · attachments · search · knowledge · help-centre-portal ·
widget · live-chat · inbound-email · social-channels · sla · business-hours ·
escalations · triggers · automations · macros · routing · teams · mentions ·
collision · reporting · csat · contacts/segmentation · campaigns · ai-agent ·
ai-copilot · ai-triage · audit-log · rbac · sso-saml · gdpr · i18n ·
mobile-apps · integrations`

## 4. Phases

Sizing: **S** ≈ half a session, **M** ≈ one session, **L** ≈ two–three sessions,
**XL** ≈ a mini-project. Each phase ends with green CI + regenerated
`openapi.json` + docs.

### P0 — Foundations (enablers) · L

Everything else depends on these; do first.

- **Rich messages**: allow HTML/markdown in `ticket_messages.body` with
  sanitisation (port Chmaba's `sanitize_html`), a `body_format` column
  (`text|html`). Migration `0010`. ✅ **done** (`body_format`/`message_format`,
  sanitised via `services/sanitize.py`).
- **Attachments breadth**: allow any content type with a per-workspace allowlist
  + max size; keep content-addressed storage; add `kind` (image/file). ✅ **done**
  (configurable `UPLOAD_SUFFIXES` + `MAX_UPLOAD_BYTES`; `kind` column, migration
  `0012_attachment_kind`).
- **Full-text search**: Postgres `tsvector` on tickets/messages/articles +
  `GET /v1/search`. Migration `0011`. ✅ **done** (`GET /v1/search` over
  tickets/messages/articles; Postgres GIN expression indexes in `0011_search`,
  portable `ILIKE` query).
- **Teams/groups + RBAC**: `teams`, `team_members`; roles
  `owner|admin|team_lead|agent|viewer`; permission checks in `deps`.
- **Audit log surface**: expose `ticket_events` (and account/workspace events)
  via `GET /v1/audit`. ✅ **done** (`GET /v1/audit`, filterable ticket-event
  trail; account/workspace-level events still to add).
- **i18n**: content locales exist; add a UI locale switch (en/km) and
  translatable notification templates (rendered by Notifyr). ✅ **backend done**
  (workspace locale via `/v1/console/settings/locale`, included in every Notifyr
  event's variables); the console UI switch and per-string translation remain.
- **Quotas**: per-workspace limits (tickets/mo, seats, storage) enforced in
  middleware, surfaced in admin. ✅ **done for tickets/month**
  (`workspace.settings.quota.tickets_per_month`, enforced on the tenant and
  public create paths with a `429`; seats/storage still to add).

### P1 — Channels · XL

The biggest gap. Split so the boundary stays clean:

- **Inbound email → ticket (M)**: `POST /v1/inbound/email` (signed webhook from
  Notifyr's inbound parse) creating a ticket or appending a threaded reply;
  `email_message_id`/`in_reply_to` on messages for threading. ✅ **done**
  (`POST /v1/inbound/email`, scope `tickets:write`; threads by `in_reply_to` or
  the sender's latest open ticket; migration `0014_inbound_email`).
- **Live chat (L)**: a real-time widget session (`/v1/chat/sessions`, WS/SSE
  stream), agents reply from the console; delivery/notification via Notifyr.
- **Social/SMS/WhatsApp (delegated, M)**: define the channel adapter contract —
  Notifyr owns transport and posts inbound to `/v1/inbound/{channel}`; Chumnouy
  owns identity mapping and threading. Ship one adapter end-to-end (WhatsApp).
- **Voice**: **not planned** (contact-centre scope) — document as such.

### P2 — SLA & business hours · L
✅ **v1 done**: per-priority first-response/resolution targets
(`workspace.settings.sla`, editable via `/v1/console/settings/sla`), due
timestamps stamped on ticket creation, a worker sweep that marks breaches
(`sla.breached` event + webhook), and `first_response_due_at` /
`resolution_due_at` / `sla_breached_at` on the ticket. Still to add: **business
hours** calendars and per-team policies.

- `business_hours` (per workspace, calendars), `sla_policies` (per priority/
  team), `sla_events` (first-response/resolution targets + breaches).
- Compute `first_response_due_at` / `resolution_due_at` on ticket events; a
  worker sweep marks breaches and emits `sla.breached` webhooks + Notifyr events.
- Console: SLA badges on tickets, policy editor; admin: breach stats.

### P3 — Automation · XL

- **Triggers** (event-based) and **automations** (time-based) with a
  condition/action DSL: conditions on ticket fields; actions = assign, set
  status/priority/tag/team, send notification, call webhook. ✅ **triggers done**
  (`/v1/triggers`, event `ticket.created|replied|updated`, conditions →
  set_status/priority/tag/team, `trigger.applied` audit); time-based automations
  and notify/webhook actions remain.
- **Macros / canned responses**: workspace-scoped saved replies + macros
  (a trigger bundle applied on demand). ✅ **canned responses done**
  (`/v1/canned-responses` CRUD); macros (trigger bundles) remain.
- **Routing**: round-robin, load-balanced (agent capacity), skill-based
  (teams/skills), on the ticket-assign path.
- Reuse the worker for time-based sweeps.

### P4 — Reporting & CSAT · L

- **Metrics**: materialise `ticket_metrics` (first response, resolution, reopen,
  volume by channel/team/agent) with a daily rollup worker. ✅ **summary done**
  (`GET /v1/reports/summary`: counts, response/resolution averages, SLA
  compliance, computed on the fly); the daily rollup + per-agent/team breakdowns
  remain.
- **API + console**: `GET /v1/reports/*` and a Reports screen (volume, FRT,
  resolution, SLA compliance, agent/team breakdowns, CSV export).
- **CSAT**: `csat_surveys` + `csat_responses`; send via Notifyr on resolve; a
  public rating endpoint; reports + per-agent rollups. ✅ **responses done**
  (`POST /v1/public/tickets/{id}/csat` + CSAT in the summary report, migration
  `0018_csat`); sending the survey via Notifyr and per-agent rollups remain.

### P5 — Collaboration · M

- **@mentions** in internal notes → notify the mentioned agent (Notifyr).
- **Collision detection**: `GET /v1/tickets/{id}/presence` (who is viewing).
- **Bulk actions** on a ticket id list (assign/status/tag/team).
- Console: keyboard shortcuts + command bar; saved views already exist.

### P6 — Self-service · L

- **Rendered help centre**: a public, SEO-friendly site over the knowledge API
  (sections, article pages, search, article feedback) — new `apps/help` or an
  SSR route in `apps/web`.
- **Widget v2**: pre-chat form, live-chat handoff, article suggestions from the
  assistant, branding config per workspace.

### P7 — Enterprise & security · XL

- **SSO/SAML** (+ optional SCIM), **granular RBAC** wired to every endpoint.
- **Audit log UI**; **GDPR**: requester data export/erasure endpoints.
- **Retention/data residency** settings; **IP allowlists** for admin.
- Compliance groundwork (SOC 2 controls, logging, backups) — process + docs.

### P8 — AI depth · L

- **Triage**: auto-priority/team/label suggestions on create.
- **Copilot**: summarise thread, suggest macro, sentiment, reply QA.
- **Agentic tools**: the integrator-supplied read-only tool contract (the
  long-open decision) so the assistant can answer data questions safely.
- **AI agent**: auto-answer from the corpus with escalation to a human ticket
  (the Chmaba "talk to a human" flow, generalised).

## 5. Explicitly out of scope / delegated

| Item | Decision |
|---|---|
| Outbound email/SMS/chat/push delivery | **Notifyr** (never in Chumnouy) |
| Voice / contact centre | **not planned** |
| Mobile apps (iOS/Android) | **not planned** for v1; responsive console instead |
| Marketplace of 1000+ integrations | **not planned**; ship a curated few (Slack, Shopify, Linear) |
| Chmaba POS migration | owned by the **Chmaba POS** project |

## 6. Sequencing

```
P0 foundations
  └─ P1 channels ─┬─ P2 SLA ─ P4 reporting/CSAT
                  └─ P3 automation ─ P5 collaboration
P0 ─ P6 self-service (help centre, widget v2)
P0 ─ P7 enterprise/security
P0 ─ P8 AI depth (after P4 metrics for triage data)
```

Rationale: **P0 first** (search, teams, rich text unblock everything).
**P1 inbound email** is the highest single-value item. **P2/P3** are what buyers
call "a real helpdesk". **P4** makes it measurable. P5–P8 round it out.

## 7. Definition of done (every phase)

- API + migration (`alembic heads` single), regenerated `openapi.json`.
- Tests (happy path + tenancy isolation + a failure path), green CI (3 jobs).
- Console/API surface documented in `docs/api.md`; roadmap updated.
- No regressions: full `scripts/check.ps1` passes locally.

## 8. Metrics

- **Parity score** = share of the §3 matrix at `have` (target: Chatwoot rows
  ≥ 85% before calling it "comparable").
- **Table stakes** = Zendesk/Freshdesk rows marked `not planned` or `have`
  (no `missing` left in SLA/automation/reporting/CSAT/SSO).
- **Quality**: tests per area, CI green rate, first-response p95 from a load test.

## 9. Risks

- **Scope**: this is ~8 phases; each is its own unit of work (see the handoff
  convention). Don't bundle.
- **Channels pull us into delivery**: keep transport in Notifyr; only inbound +
  config live here.
- **Search/scale**: `tsvector` is fine to start; revisit if volume grows.
- **Compliance** is process, not code — flag early, it gates enterprise deals.
