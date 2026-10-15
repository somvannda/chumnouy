import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2, Wand2 } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../context/auth";
import { Alert, Badge, Button, Card, EmptyState, Field, Input, Select, Spinner } from "../components/ui";

const ACTIONS = ["set_priority", "set_status", "add_tag", "remove_tag", "set_team", "notify"];

const EMPTY = { name: "", actionType: "set_priority", actionValue: "high" };

export default function Macros() {
  const { token } = useAuth();
  const [items, setItems] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    () => api.listMacros(token).then(setItems).catch((err) => setError(err.message)),
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
      await api.createMacro(token, {
        name: form.name.trim(),
        actions: [{ type: form.actionType, value: form.actionValue }],
      });
      setForm(EMPTY);
    });
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-lg font-black text-ink">Macros</h1>
      <p className="mt-1 text-sm text-ink-soft">
        Named action bundles agents apply to a ticket from the ticket view.
      </p>

      <Alert className="mt-4">{error}</Alert>

      <Card className="mt-4">
        <form onSubmit={create} className="space-y-4">
          <Field label="Name">
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Escalate"
            />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Action">
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
            <Field label="Value">
              <Input
                value={form.actionValue}
                onChange={(e) => setForm({ ...form, actionValue: e.target.value })}
              />
            </Field>
          </div>
          <Button type="submit" disabled={busy || !form.name.trim()}>
            <Plus size={16} /> Add macro
          </Button>
        </form>
      </Card>

      <div className="mt-6 space-y-2">
        {!items && (
          <div className="flex justify-center py-10">
            <Spinner />
          </div>
        )}
        {items?.length === 0 && <EmptyState icon={Wand2} title="No macros yet" />}
        {items?.map((macro) => (
          <Card key={macro.id} className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-extrabold text-ink">{macro.name}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {macro.actions.map((action, index) => (
                  <Badge key={index} tone="brand">
                    {action.type} {action.value}
                  </Badge>
                ))}
              </div>
            </div>
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => run(() => api.deleteMacro(token, macro.id))}
              aria-label="Delete"
            >
              <Trash2 size={16} />
            </Button>
          </Card>
        ))}
      </div>
    </div>
  );
}
