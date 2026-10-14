import { useCallback, useEffect, useState } from "react";
import { KeyRound, Users } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../context/auth";
import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  Spinner,
} from "../components/ui";
import { formatRelativeTime, initials, statusTone } from "../lib/format";

export default function Requesters() {
  const { token } = useAuth();
  const [requesters, setRequesters] = useState(null);
  const [q, setQ] = useState("");
  const [detail, setDetail] = useState(null);
  const [issued, setIssued] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    const params = q ? { q } : {};
    return api
      .listRequesters(token, params)
      .then(setRequesters)
      .catch((err) => setError(err.message));
  }, [token, q]);

  useEffect(() => {
    load();
  }, [load]);

  async function open(requester) {
    setError(null);
    setIssued(null);
    try {
      setDetail(await api.getRequester(token, requester.id));
    } catch (err) {
      setError(err.message);
    }
  }

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

  function issue() {
    run(async () => setIssued(await api.issuePortalToken(token, detail.id)));
  }

  function save(event) {
    event.preventDefault();
    run(async () => {
      await api.updateRequester(token, detail.id, {
        name: detail.name || undefined,
        email: detail.email || undefined,
        phone: detail.phone || undefined,
      });
      await open(detail);
    });
  }

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-lg font-black text-ink">Requesters</h1>
      <p className="mt-1 text-sm text-ink-soft">The end users who open tickets.</p>

      <Alert className="mt-4">{error}</Alert>

      <div className="mt-4 grid gap-6 lg:grid-cols-[1fr_1fr]">
        <section>
          <Input placeholder="Search name, email, id…" value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="mt-3 space-y-2">
            {!requesters && (
              <div className="flex justify-center py-10">
                <Spinner />
              </div>
            )}
            {requesters?.length === 0 && (
              <EmptyState icon={Users} title="No requesters yet">
                They appear when a ticket is opened with a new external id.
              </EmptyState>
            )}
            {requesters?.map((requester) => (
              <Card
                key={requester.id}
                className={`flex cursor-pointer items-center gap-3 transition hover:border-brand/40 ${
                  detail?.id === requester.id ? "border-brand" : ""
                }`}
                onClick={() => open(requester)}
              >
                <Avatar label={initials(requester.name || requester.external_id)} />
                <div className="min-w-0">
                  <p className="truncate text-sm font-bold text-ink">
                    {requester.name || requester.external_id}
                  </p>
                  <p className="truncate text-xs text-muted">
                    {requester.email || requester.external_id}
                  </p>
                </div>
              </Card>
            ))}
          </div>
        </section>

        <section>
          {!detail ? (
            <EmptyState title="Select a requester" className="h-full" />
          ) : (
            <div className="space-y-4">
              <Card>
                <form onSubmit={save} className="space-y-3">
                  <Field label="Name">
                    <Input
                      value={detail.name || ""}
                      onChange={(e) => setDetail({ ...detail, name: e.target.value })}
                    />
                  </Field>
                  <Field label="Email">
                    <Input
                      value={detail.email || ""}
                      onChange={(e) => setDetail({ ...detail, email: e.target.value })}
                    />
                  </Field>
                  <Field label="Phone">
                    <Input
                      value={detail.phone || ""}
                      onChange={(e) => setDetail({ ...detail, phone: e.target.value })}
                    />
                  </Field>
                  <Button type="submit" disabled={busy}>
                    Save
                  </Button>
                </form>
              </Card>

              <Card>
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-extrabold text-ink">Portal token</h2>
                  <Button variant="secondary" onClick={issue} disabled={busy}>
                    <KeyRound size={15} /> {detail.portal_token_prefix ? "Rotate" : "Issue"}
                  </Button>
                </div>
                {issued ? (
                  <p className="mt-3 break-all rounded-xl bg-surface-sunken p-3 font-mono text-xs text-ink-soft">
                    {issued.token}
                  </p>
                ) : (
                  <p className="mt-2 text-xs text-muted">
                    Hand this to the end user for the public portal; it is shown once.
                  </p>
                )}
              </Card>

              <Card>
                <h2 className="text-sm font-extrabold text-ink">Tickets</h2>
                <div className="mt-3 space-y-2">
                  {detail.tickets?.length === 0 && <p className="text-sm text-muted">No tickets.</p>}
                  {detail.tickets?.map((ticket) => (
                    <div key={ticket.id} className="flex items-center justify-between gap-3 py-1.5">
                      <p className="min-w-0 truncate text-sm text-ink">{ticket.subject}</p>
                      <div className="flex shrink-0 items-center gap-2">
                        <Badge tone={statusTone(ticket.status)}>{ticket.status}</Badge>
                        <span className="text-xs text-muted">{ticket.reference}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
