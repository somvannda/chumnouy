import { useCallback, useEffect, useState } from "react";
import { Building2 } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../context/auth";
import { Alert, Badge, Button, Card, EmptyState, Input, Spinner } from "../components/ui";
import { formatRelativeTime } from "../lib/format";

const USAGE_FIELDS = [
  ["accounts", "Accounts"],
  ["workspaces", "Workspaces"],
  ["active_workspaces", "Active"],
  ["tickets", "Tickets"],
  ["open_tickets", "Open"],
  ["requesters", "Requesters"],
  ["integrations", "Integrations"],
  ["knowledge_articles", "Articles"],
  ["webhook_deliveries", "Deliveries"],
];

function WorkspaceRow({ workspace, onToggle, onQuota, busy }) {
  const [quota, setQuota] = useState(workspace.quota?.tickets_per_month ?? "");

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-extrabold text-ink">{workspace.name}</p>
          <p className="mt-0.5 text-xs text-muted">
            {workspace.slug} · {workspace.ticket_count} tickets · created{" "}
            {formatRelativeTime(workspace.created_at)}
          </p>
        </div>
        <Badge tone={workspace.is_active ? "success" : "danger"}>
          {workspace.is_active ? "active" : "disabled"}
        </Badge>
      </div>
      <div className="mt-3 flex flex-wrap items-end gap-3">
        <label className="text-xs font-bold uppercase tracking-[.08em] text-muted">
          Quota / month
          <Input
            className="mt-1 w-32"
            inputMode="numeric"
            value={quota}
            placeholder="unlimited"
            onChange={(event) => setQuota(event.target.value)}
          />
        </label>
        <Button variant="secondary" disabled={busy} onClick={() => onQuota(workspace, quota)}>
          Save quota
        </Button>
        <Button variant="secondary" disabled={busy} onClick={() => onToggle(workspace)}>
          {workspace.is_active ? "Disable" : "Enable"}
        </Button>
      </div>
    </Card>
  );
}

export default function Admin() {
  const { token } = useAuth();
  const [usage, setUsage] = useState(null);
  const [accounts, setAccounts] = useState(null);
  const [workspaces, setWorkspaces] = useState(null);
  const [q, setQ] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    const params = q ? { q } : {};
    return Promise.all([
      api.adminUsage(token),
      api.adminAccounts(token),
      api.adminWorkspaces(token, params),
    ])
      .then(([usageData, accountData, workspaceData]) => {
        setUsage(usageData);
        setAccounts(accountData);
        setWorkspaces(workspaceData);
      })
      .catch((err) => setError(err.message));
  }, [token, q]);

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

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-lg font-black text-ink">Platform admin</h1>
      <p className="mt-1 text-sm text-ink-soft">Cross-tenant accounts, workspaces and usage.</p>

      <Alert className="mt-4">{error}</Alert>

      {!usage && !error && (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      )}

      {usage && (
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {USAGE_FIELDS.map(([key, label]) => (
            <Card key={key}>
              <p className="text-2xl font-black text-ink">{usage[key]}</p>
              <p className="mt-1 text-xs font-bold uppercase tracking-[.08em] text-muted">{label}</p>
            </Card>
          ))}
        </div>
      )}

      <h2 className="mt-8 text-sm font-extrabold text-ink">Accounts</h2>
      <div className="mt-3 space-y-2">
        {accounts?.length === 0 && <EmptyState title="No accounts" />}
        {accounts?.map((account) => (
          <Card key={account.id} className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-bold text-ink">{account.name}</p>
              <p className="text-xs text-muted">{account.slug}</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge tone="neutral">{account.workspace_count} ws</Badge>
              <Badge tone={account.status === "active" ? "success" : "neutral"}>
                {account.status}
              </Badge>
            </div>
          </Card>
        ))}
      </div>

      <div className="mt-8 flex items-center justify-between gap-3">
        <h2 className="text-sm font-extrabold text-ink">Workspaces</h2>
        <Input
          className="max-w-xs"
          placeholder="Search workspaces…"
          value={q}
          onChange={(event) => setQ(event.target.value)}
        />
      </div>
      <div className="mt-3 space-y-2">
        {workspaces?.length === 0 && (
          <EmptyState icon={Building2} title="No workspaces match" />
        )}
        {workspaces?.map((workspace) => (
          <WorkspaceRow
            key={workspace.id}
            workspace={workspace}
            busy={busy}
            onToggle={(ws) => run(() => api.updateAdminWorkspace(token, ws.id, { is_active: !ws.is_active }))}
            onQuota={(ws, value) =>
              run(() =>
                api.updateAdminWorkspace(token, ws.id, {
                  quota: value === "" ? {} : { tickets_per_month: Number(value) },
                }),
              )
            }
          />
        ))}
      </div>
    </div>
  );
}
