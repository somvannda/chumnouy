import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Inbox as InboxIcon, Search } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../context/auth";
import { Badge, Card, EmptyState, Input, Spinner } from "../components/ui";
import {
  SAVED_VIEWS,
  formatRelativeTime,
  priorityTone,
  statusTone,
  truncate,
  viewParams,
} from "../lib/format";

export default function Inbox() {
  const { token } = useAuth();
  const [params, setParams] = useSearchParams();
  const view = params.get("view") || "all";
  const query = params.get("q") || "";
  const [search, setSearch] = useState(query);
  const [tickets, setTickets] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setTickets(null);
    setError(null);
    api
      .listTickets(token, { ...viewParams(view), q: query || undefined, limit: 50 })
      .then((data) => {
        if (!cancelled) setTickets(data.data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [token, view, query]);

  function selectView(id) {
    const next = new URLSearchParams(params);
    next.set("view", id);
    setParams(next);
  }

  function submitSearch(event) {
    event.preventDefault();
    const next = new URLSearchParams(params);
    if (search) next.set("q", search);
    else next.delete("q");
    setParams(next);
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
      <aside className="space-y-1">
        <p className="px-3 text-[11px] font-bold uppercase tracking-[.14em] text-muted">Views</p>
        {SAVED_VIEWS.map((saved) => (
          <button
            key={saved.id}
            onClick={() => selectView(saved.id)}
            className={`w-full rounded-xl px-3 py-2 text-left text-sm font-bold transition ${
              saved.id === view ? "bg-brand-soft text-brand" : "text-ink-soft hover:bg-surface-muted"
            }`}
          >
            {saved.label}
          </button>
        ))}
      </aside>

      <section className="min-w-0">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-lg font-black text-ink">Inbox</h1>
          <form onSubmit={submitSearch} className="relative w-full max-w-xs">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <Input
              className="pl-9"
              placeholder="Search subject…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </form>
        </div>

        <div className="mt-4 space-y-2">
          {error && <p className="text-sm font-semibold text-danger">{error}</p>}
          {!tickets && !error && (
            <div className="flex justify-center py-16">
              <Spinner />
            </div>
          )}
          {tickets && tickets.length === 0 && (
            <EmptyState icon={InboxIcon} title="No tickets here">
              Nothing matches this view yet.
            </EmptyState>
          )}
          {tickets?.map((ticket) => (
            <Link key={ticket.id} to={`/tickets/${ticket.id}`} className="block">
              <Card className="transition hover:border-brand/40 hover:shadow-panel">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-extrabold text-ink">{ticket.subject}</p>
                    <p className="mt-0.5 text-xs text-muted">
                      {ticket.reference} · {ticket.requester?.name || ticket.requester?.external_id || "Unknown"}
                      {ticket.requester?.email ? ` · ${ticket.requester.email}` : ""}
                    </p>
                  </div>
                  <span className="shrink-0 text-xs text-muted">
                    {formatRelativeTime(ticket.created_at)}
                  </span>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <Badge tone={statusTone(ticket.status)}>{ticket.status}</Badge>
                  <Badge tone={priorityTone(ticket.priority)}>{ticket.priority}</Badge>
                  {ticket.tags?.map((tag) => (
                    <Badge key={tag} tone="neutral">
                      {tag}
                    </Badge>
                  ))}
                </div>
              </Card>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
