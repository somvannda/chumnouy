import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2, Zap } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../context/auth";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  Select,
  Spinner,
} from "../components/ui";

const EVENTS = ["ticket.created", "ticket.replied", "ticket.updated"];
const FIELDS = ["tag", "priority", "status", "subject"];
const ACTIONS = [
  "set_priority",
  "set_status",
  "add_tag",
  "remove_tag",
  "set_team",
  "notify",
  "webhook",
];

const EMPTY = {
  name: "",
  event: "ticket.created",
  field: "tag",
  op: "is",
  value: "",
  actionType: "set_priority",
  actionValue: "high",
};

export default function Triggers() {
  const { token } = useAuth();
  const [items, setItems] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [webhooks, setWebhooks] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    () => api.listTriggers(token).then(setItems).catch((err) => setError(err.message)),
    [token],
  );

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    api.listWebhooks(token).then(setWebhooks).catch(() => setWebhooks([]));
  }, [token]);

  async function run(action) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function create(event) {
    event.preventDefault();
    run(async () => {
      await api.createTrigger(token, {
        name: form.name.trim(),
        event: form.event,
        conditions: form.value ? [{ field: form.field, op: form.op, value: form.value }] : [],
        actions: [{ type: form.actionType, value: form.actionValue }],
      });
      setForm({ ...EMPTY, event: form.event });
    });
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-lg font-black text-ink">Triggers</h1>
      <p className="mt-1 text-sm text-ink-soft">
        When an event fires and the condition matches, run the action.
      </p>

      <Alert className="mt-4">{error}</Alert>

      <Card className="mt-4">
        <form onSubmit={create} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Name">
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Escalate hardware"
              />
            </Field>
            <Field label="Event">
              <Select value={form.event} onChange={(e) => setForm({ ...form, event: e.target.value })}>
                {EVENTS.map((event) => (
                  <option key={event} value={event}>
                    {event}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="When field">
              <Select value={form.field} onChange={(e) => setForm({ ...form, field: e.target.value })}>
                {FIELDS.map((field) => (
                  <option key={field} value={field}>
                    {field}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Op">
              <Select value={form.op} onChange={(e) => setForm({ ...form, op: e.target.value })}>
                <option value="is">is</option>
                <option value="contains">contains</option>
              </Select>
            </Field>
            <Field label="Value">
              <Input value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} />
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Then action">
              <Select
                value={form.actionType}
                onChange={(e) => setForm({ ...form, actionType: e.target.value })}
              >
                {ACTIONS.map((action) => (
                  <option key={action} value={action}>
                    {action}
                  </option>
                ))}
              </Select>
            </Field>
            <Field
              label="Action value"
              hint={
                form.actionType === "notify"
                  ? "requester, agents, or an email"
                  : form.actionType === "webhook"
                    ? "the webhook to call"
                    : undefined
              }
            >
              {form.actionType === "webhook" ? (
                <Select
                  value={form.actionValue}
                  onChange={(e) => setForm({ ...form, actionValue: e.target.value })}
                >
                  <option value="">{webhooks.length ? "Pick a webhook…" : "No webhooks yet"}</option>
                  {webhooks.map((hook) => (
                    <option key={hook.id} value={hook.id}>
                      {hook.description || hook.url}
                    </option>
                  ))}
                </Select>
              ) : (
                <Input
                  value={form.actionValue}
                  onChange={(e) => setForm({ ...form, actionValue: e.target.value })}
                />
              )}
            </Field>
          </div>
          <Button type="submit" disabled={busy || !form.name.trim()}>
            <Plus size={16} /> Add trigger
          </Button>
        </form>
      </Card>

      <div className="mt-6 space-y-2">
        {!items && (
          <div className="flex justify-center py-10">
            <Spinner />
          </div>
        )}
        {items?.length === 0 && <EmptyState icon={Zap} title="No triggers yet" />}
        {items?.map((trigger) => (
          <Card key={trigger.id} className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-extrabold text-ink">{trigger.name}</p>
              <p className="mt-0.5 text-xs text-muted">on {trigger.event}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {trigger.conditions.map((condition, index) => (
                  <Badge key={`c${index}`} tone="neutral">
                    {condition.field} {condition.op} {condition.value}
                  </Badge>
                ))}
                {trigger.actions.map((action, index) => (
                  <Badge key={`a${index}`} tone="brand">
                    {action.type} {action.value}
                  </Badge>
                ))}
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() =>
                  run(() => api.updateTrigger(token, trigger.id, { is_active: !trigger.is_active }))
                }
              >
                {trigger.is_active ? "Disable" : "Enable"}
              </Button>
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => run(() => api.deleteTrigger(token, trigger.id))}
                aria-label="Delete"
              >
                <Trash2 size={16} />
              </Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
