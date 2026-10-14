import { useCallback, useEffect, useState } from "react";
import { KeyRound, Plus, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../context/auth";
import { Alert, Badge, Button, Card, EmptyState, Field, Input, Spinner } from "../components/ui";
import { formatRelativeTime } from "../lib/format";

const ALL_SCOPES = [
  "tickets:read",
  "tickets:write",
  "requesters:read",
  "requesters:write",
  "knowledge:read",
  "knowledge:write",
  "assistant:use",
  "webhooks:manage",
];

const DEFAULT_SCOPES = ["tickets:read", "tickets:write"];

function IntegrationCard({ integration, onKeyIssued }) {
  const { token } = useAuth();
  const [keys, setKeys] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const loadKeys = useCallback(
    () => api.listKeys(token, integration.id).then(setKeys).catch((err) => setError(err.message)),
    [token, integration.id],
  );

  useEffect(() => {
    loadKeys();
  }, [loadKeys]);

  async function issueKey() {
    setBusy(true);
    setError(null);
    try {
      const data = await api.createKey(token, integration.id, { name: "console", environment: "live" });
      onKeyIssued(data);
      await loadKeys();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function revokeKey(keyId) {
    setBusy(true);
    try {
      await api.revokeKey(token, keyId);
      await loadKeys();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-extrabold text-ink">{integration.name}</p>
          <p className="mt-0.5 text-xs text-muted">
            {integration.slug} · created {formatRelativeTime(integration.created_at)}
          </p>
        </div>
        <Badge tone={integration.is_active ? "success" : "neutral"}>
          {integration.is_active ? "active" : "disabled"}
        </Badge>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {integration.scopes.map((scope) => (
          <Badge key={scope} tone="neutral">
            {scope}
          </Badge>
        ))}
      </div>

      <div className="mt-4 flex items-center justify-between">
        <p className="text-xs font-bold uppercase tracking-[.08em] text-muted">API keys</p>
        <Button variant="secondary" onClick={issueKey} disabled={busy}>
          <Plus size={15} /> New key
        </Button>
      </div>
      <Alert className="mt-3">{error}</Alert>

      <ul className="mt-2 divide-y divide-line">
        {!keys && (
          <li className="py-3 text-center">
            <Spinner />
          </li>
        )}
        {keys?.length === 0 && <li className="py-3 text-sm text-muted">No keys yet.</li>}
        {keys?.map((key) => (
          <li key={key.id} className="flex items-center justify-between gap-3 py-2.5">
            <div className="min-w-0">
              <p className="truncate text-sm font-bold text-ink">{key.name}</p>
              <p className="text-xs text-muted">
                {key.key_prefix}… · {key.environment} ·{" "}
                {key.last_used_at ? `used ${formatRelativeTime(key.last_used_at)}` : "never used"}
              </p>
            </div>
            {key.is_active ? (
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => revokeKey(key.id)}
                aria-label="Revoke key"
              >
                <Trash2 size={16} />
              </Button>
            ) : (
              <Badge tone="danger">revoked</Badge>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

export default function Integrations() {
  const { token } = useAuth();
  const [integrations, setIntegrations] = useState(null);
  const [error, setError] = useState(null);
  const [createdKey, setCreatedKey] = useState(null);
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState(DEFAULT_SCOPES);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    () => api.listIntegrations(token).then(setIntegrations).catch((err) => setError(err.message)),
    [token],
  );

  useEffect(() => {
    load();
  }, [load]);

  function toggleScope(scope) {
    setScopes((prev) => (prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]));
  }

  async function createIntegration(event) {
    event.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.createIntegration(token, { name: name.trim(), scopes });
      setName("");
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-lg font-black text-ink">Integrations</h1>
      <p className="mt-1 text-sm text-ink-soft">
        Register a client app, then take a scoped API key. Keys are shown once.
      </p>

      <Alert className="mt-4">{error}</Alert>
      {createdKey && (
        <Alert tone="success" className="mt-4">
          <span className="block">New key for “{createdKey.api_key.name}” — copy it now, it won’t be shown again:</span>
          <code className="mt-1 block break-all font-mono text-xs">{createdKey.key}</code>
        </Alert>
      )}

      <Card className="mt-4">
        <form onSubmit={createIntegration} className="space-y-4">
          <Field label="New integration">
            <Input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Chmaba POS"
            />
          </Field>
          <div>
            <p className="mb-1.5 text-xs font-bold uppercase tracking-[.08em] text-ink-soft">Scopes</p>
            <div className="flex flex-wrap gap-1.5">
              {ALL_SCOPES.map((scope) => {
                const active = scopes.includes(scope);
                return (
                  <button
                    key={scope}
                    type="button"
                    onClick={() => toggleScope(scope)}
                    className={`rounded-full px-2.5 py-0.5 text-xs font-bold transition ${
                      active ? "bg-brand-soft text-brand" : "bg-surface-sunken text-muted hover:text-ink-soft"
                    }`}
                  >
                    {scope}
                  </button>
                );
              })}
            </div>
          </div>
          <Button type="submit" disabled={busy || !name.trim()}>
            Create integration
          </Button>
        </form>
      </Card>

      <div className="mt-6 space-y-4">
        {!integrations && (
          <div className="flex justify-center py-10">
            <Spinner />
          </div>
        )}
        {integrations?.length === 0 && (
          <EmptyState icon={KeyRound} title="No integrations yet">
            Create one above to issue your first API key.
          </EmptyState>
        )}
        {integrations?.map((integration) => (
          <IntegrationCard key={integration.id} integration={integration} onKeyIssued={setCreatedKey} />
        ))}
      </div>
    </div>
  );
}
