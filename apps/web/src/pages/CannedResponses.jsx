import { useCallback, useEffect, useState } from "react";
import { MessageSquareText, Plus, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../context/auth";
import { Alert, Badge, Button, Card, EmptyState, Field, Input, Spinner, Textarea } from "../components/ui";

export default function CannedResponses() {
  const { token } = useAuth();
  const [items, setItems] = useState(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    () => api.listCannedResponses(token).then(setItems).catch((err) => setError(err.message)),
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
      await api.createCannedResponse(token, { title: title.trim(), body });
      setTitle("");
      setBody("");
    });
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-lg font-black text-ink">Canned responses</h1>
      <p className="mt-1 text-sm text-ink-soft">Saved replies agents can reuse.</p>

      <Alert className="mt-4">{error}</Alert>

      <Card className="mt-4">
        <form onSubmit={create} className="space-y-4">
          <Field label="Title">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Thanks for reaching out" />
          </Field>
          <Field label="Body">
            <Textarea rows={3} value={body} onChange={(e) => setBody(e.target.value)} />
          </Field>
          <Button type="submit" disabled={busy || !title.trim() || !body.trim()}>
            <Plus size={16} /> Add
          </Button>
        </form>
      </Card>

      <div className="mt-6 space-y-2">
        {!items && (
          <div className="flex justify-center py-10">
            <Spinner />
          </div>
        )}
        {items?.length === 0 && (
          <EmptyState icon={MessageSquareText} title="No canned responses yet" />
        )}
        {items?.map((item) => (
          <Card key={item.id} className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-extrabold text-ink">{item.title}</p>
              <p className="mt-1 whitespace-pre-wrap text-sm text-ink-soft">{item.body}</p>
              {item.body_format === "html" && (
                <Badge tone="neutral" className="mt-2">
                  html
                </Badge>
              )}
            </div>
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => run(() => api.deleteCannedResponse(token, item.id))}
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
