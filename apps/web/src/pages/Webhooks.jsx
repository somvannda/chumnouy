import { useCallback, useEffect, useState } from "react";
import { RotateCcw, Trash2, Webhook } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../context/auth";
import { Alert, Badge, Button, Card, EmptyState, Field, Input, Spinner } from "../components/ui";
import { formatRelativeTime, statusTone } from "../lib/format";

const EVENTS = [
  "ticket.created",
  "ticket.replied",
  "ticket.status_changed",
  "ticket.assigned",
  "ticket.resolved",
  "ticket.reopened",
];

function WebhookCard({ webhook, onChange }) {
  const { token } = useAuth();
  const [deliveries, setDeliveries] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function run(action) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const loadDeliveries = () =>
    run(async () => setDeliveries(await api.webhookDeliveries(token, webhook.id, { limit: 20 })));

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-extrabold text-ink">{webhook.url}</p>
          {webhook.description && <p className="text-xs text-muted">{webhook.description}</p>}
        </div>
        <Badge tone={webhook.is_active ? "success" : "neutral"}>
          {webhook.is_active ? "active" : "disabled"}
        </Badge>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {webhook.events.map((event) => (
          <Badge key={event} tone="neutral">
            {event}
          </Badge>
        ))}
      </div>

      <Alert className="mt-3">{error}</Alert>

      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="secondary" disabled={busy} onClick={loadDeliveries}>
          Deliveries
        </Button>
        <Button
          variant="secondary"
          disabled={busy}
          onClick={() =>
            run(async () => {
              await api.updateWebhook(token, webhook.id, { is_active: !webhook.is_active });
              await onChange();
            })
          }
        >
          {webhook.is_active ? "Disable" : "Enable"}
        </Button>
        <Button
          variant="ghost"
          disabled={busy}
          onClick={() =>
            run(async () => {
              await api.deleteWebhook(token, webhook.id);
              await onChange();
            })
          }
          aria-label="Delete webhook"
        >
          <Trash2 size={16} />
        </Button>
      </div>

      {deliveries && (
        <ul className="mt-3 divide-y divide-line">
          {deliveries.length === 0 && <li className="py-2 text-sm text-muted">No deliveries yet.</li>}
          {deliveries.map((delivery) => (
            <li key={delivery.id} className="flex items-center justify-between gap-3 py-2">
              <div className="min-w-0">
                <p className="truncate text-xs font-bold text-ink">{delivery.event}</p>
                <p className="text-xs text-muted">
                  {delivery.status} · {delivery.attempts} attempt(s) ·{" "}
                  {formatRelativeTime(delivery.created_at)}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={statusTone(delivery.status === "delivered" ? "resolved" : "pending")}>
                  {delivery.status}
                </Badge>
                <button
                  title="Replay"
                  onClick={() =>
                    run(async () => {
                      await api.replayWebhookDelivery(token, delivery.id);
                      await loadDeliveries();
                    })
                  }
                  className="text-muted hover:text-brand"
                >
                  <RotateCcw size={15} />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export default function Webhooks() {
  const { token } = useAuth();
  const [webhooks, setWebhooks] = useState(null);
  const [error, setError] = useState(null);
  const [created, setCreated] = useState(null);
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [events, setEvents] = useState(["ticket.created", "ticket.replied"]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    () => api.listWebhooks(token).then(setWebhooks).catch((err) => setError(err.message)),
    [token],
  );

  useEffect(() => {
    load();
  }, [load]);

  function toggleEvent(event) {
    setEvents((prev) => (prev.includes(event) ? prev.filter((e) => e !== event) : [...prev, event]));
  }

  async function create(event) {
    event.preventDefault();
    if (!url.trim() || events.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const data = await api.createWebhook(token, {
        url: url.trim(),
        description: description.trim() || null,
        events,
      });
      setCreated(data);
      setUrl("");
      setDescription("");
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-lg font-black text-ink">Webhooks</h1>
      <p className="mt-1 text-sm text-ink-soft">
        Signed ticket events delivered to your endpoints. Secrets are shown once.
      </p>

      <Alert className="mt-4">{error}</Alert>
      {created && (
        <Alert tone="success" className="mt-4">
          <span className="block">Signing secret — copy it now, it won’t be shown again:</span>
          <code className="mt-1 block break-all font-mono text-xs">{created.secret}</code>
        </Alert>
      )}

      <Card className="mt-4">
        <form onSubmit={create} className="space-y-4">
          <Field label="Endpoint URL">
            <Input required value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/hook" />
          </Field>
          <Field label="Description" hint="Optional.">
            <Input value={description} onChange={(e) => setDescription(e.target.value)} />
          </Field>
          <div>
            <p className="mb-1.5 text-xs font-bold uppercase tracking-[.08em] text-ink-soft">Events</p>
            <div className="flex flex-wrap gap-1.5">
              {EVENTS.map((event) => (
                <button
                  key={event}
                  type="button"
                  onClick={() => toggleEvent(event)}
                  className={`rounded-full px-2.5 py-0.5 text-xs font-bold transition ${
                    events.includes(event)
                      ? "bg-brand-soft text-brand"
                      : "bg-surface-sunken text-muted hover:text-ink-soft"
                  }`}
                >
                  {event}
                </button>
              ))}
            </div>
          </div>
          <Button type="submit" disabled={busy || !url.trim() || events.length === 0}>
            Create webhook
          </Button>
        </form>
      </Card>

      <div className="mt-6 space-y-4">
        {!webhooks && (
          <div className="flex justify-center py-10">
            <Spinner />
          </div>
        )}
        {webhooks?.length === 0 && (
          <EmptyState icon={Webhook} title="No webhooks yet">
            Create one above to receive ticket events.
          </EmptyState>
        )}
        {webhooks?.map((webhook) => (
          <WebhookCard key={webhook.id} webhook={webhook} onChange={load} />
        ))}
      </div>
    </div>
  );
}
