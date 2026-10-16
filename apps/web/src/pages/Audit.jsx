import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ScrollText } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../context/auth";
import { Alert, Badge, Card, EmptyState, Spinner } from "../components/ui";
import { formatRelativeTime } from "../lib/format";

const TYPES = [
  "ticket.created",
  "ticket.replied",
  "ticket.updated",
  "ticket.resolved",
  "ticket.reopened",
  "trigger.applied",
  "sla.breached",
];

const WORKSPACE_TYPES = [
  "settings.branding",
  "settings.locale",
  "settings.sla",
  "settings.sso",
  "settings.ai",
  "settings.notifications",
  "settings.business-hours",
  "member.invited",
  "member.updated",
  "member.removed",
  "invite.revoked",
];

export default function Audit() {
  const { token } = useAuth();
  const [scope, setScope] = useState("ticket");
  const [events, setEvents] = useState(null);
  const [type, setType] = useState("");
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    const params = { limit: 100 };
    if (type) params.type = type;
    const request = scope === "workspace" ? api.auditWorkspaceEvents : api.auditEvents;
    return request(token, params)
      .then((data) => setEvents(data.data))
      .catch((e) => setError(e.message));
  }, [token, scope, type]);

  useEffect(() => {
    load();
  }, [load]);

  const options = scope === "workspace" ? WORKSPACE_TYPES : TYPES;

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-lg font-black text-ink">Audit log</h1>
      <p className="mt-1 text-sm text-ink-soft">
        {scope === "workspace"
          ? "Account and workspace changes, newest first."
          : "Every ticket event, newest first."}
      </p>

      <Alert className="mt-4">{error}</Alert>

      <div className="mt-4 flex flex-wrap gap-1.5">
        {[
          ["ticket", "Tickets"],
          ["workspace", "Workspace"],
        ].map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => {
              setScope(value);
              setType("");
              setEvents(null);
            }}
            className={`rounded-full px-3 py-1 text-xs font-bold transition ${
              scope === value ? "bg-brand text-white" : "bg-surface-sunken text-muted hover:text-ink-soft"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <button
          type="button"
          onClick={() => setType("")}
          className={`rounded-full px-2.5 py-1 text-xs font-bold transition ${
            type === "" ? "bg-brand-soft text-brand" : "bg-surface-sunken text-muted hover:text-ink-soft"
          }`}
        >
          All
        </button>
        {options.map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => setType(option)}
            className={`rounded-full px-2.5 py-1 text-xs font-bold transition ${
              type === option ? "bg-brand-soft text-brand" : "bg-surface-sunken text-muted hover:text-ink-soft"
            }`}
          >
            {option}
          </button>
        ))}
      </div>

      <div className="mt-4 space-y-2">
        {!events && !error && (
          <div className="flex justify-center py-16">
            <Spinner />
          </div>
        )}
        {events?.length === 0 && <EmptyState icon={ScrollText} title="No events" />}
        {events?.map((event) => (
          <Card key={event.id} className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-bold text-ink">{event.type}</p>
              <p className="text-xs text-muted">
                {event.actor_type} · {formatRelativeTime(event.created_at)}
              </p>
            </div>
            {event.ticket_id ? (
              <Link
                to={`/tickets/${event.ticket_id}`}
                className="shrink-0 text-xs font-bold text-brand hover:underline"
              >
                View ticket
              </Link>
            ) : (
              <Badge tone="neutral">workspace</Badge>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
