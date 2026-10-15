import { useCallback, useEffect, useState } from "react";
import { Clock, Plus, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../context/auth";
import { Alert, Badge, Button, Card, EmptyState, Field, Input, Select, Spinner } from "../components/ui";

const FIELDS = ["tag", "priority", "status", "subject"];
const ACTIONS = ["set_priority", "set_status", "add_tag", "remove_tag", "set_team"];

const EMPTY = {
  name: "",
  after_minutes: 60,
  field: "status",
  op: "is",
  value: "pending",
  actionType: "add_tag",
  actionValue: "stale",
};

export default function Automations() {
  const { token } = useAuth();
  const [items, setItems] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    () => api.listAutomations(token).then(setItems).catch((err) => setError(err.message)),
    [token],
  );

  useEffect(() => {
    load();
  }, [load]);

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
      await api.createAutomation(token, {
        name: form.name.trim(),
        after_minutes: Math.max(0, Number(form.after_minutes) || 0),
        conditions: form.value ? [{ field: form.field, op: form.op, value: form.value }] : [],
        actions: [{ type: form.actionType, value: form.actionValue }],
      });
      setForm(EMPTY);
    });
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-lg font-black text-ink">Automations</h1>
      <p className="mt-1 text-sm text-ink-soft">
        After a delay, run an action on open tickets that match a condition.
      </p>

      <Alert className="mt-4">{error}</Alert>

      <Card className="mt-4">
        <form onSubmit={create} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Name">
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Nudge stale tickets"
              />
            </Field>
            <Field label="After (minutes)">
              <Input
                inputMode="numeric"
                value={form.after_minutes}
                onChange={(e) => setForm({ ...form, after_minutes: e.target.value })}
              />
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
            <Field label="Action value">
              <Input
                value={form.actionValue}
                onChange={(e) => setForm({ ...form, actionValue: e.target.value })}
              />
            </Field>
          </div>
          <Button type="submit" disabled={busy || !form.name.trim()}>
            <Plus size={16} /> Add automation
          </Button>
        </form>
      </Card>

      <div className="mt-6 space-y-2">
        {!items && (
          <div className="flex justify-center py-10">
            <Spinner />
          </div>
        )}
        {items?.length === 0 && <EmptyState icon={Clock} title="No automations yet" />}
        {items?.map((automation) => (
          <Card key={automation.id} className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-extrabold text-ink">{automation.name}</p>
              <p className="mt-0.5 text-xs text-muted">after {automation.after_minutes} min</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {automation.conditions.map((condition, index) => (
                  <Badge key={`c${index}`} tone="neutral">
                    {condition.field} {condition.op} {condition.value}
                  </Badge>
                ))}
                {automation.actions.map((action, index) => (
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
                  run(() =>
                    api.updateAutomation(token, automation.id, { is_active: !automation.is_active }),
                  )
                }
              >
                {automation.is_active ? "Disable" : "Enable"}
              </Button>
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => run(() => api.deleteAutomation(token, automation.id))}
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
