import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Send } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../context/auth";
import {
  Avatar,
  Badge,
  Button,
  Card,
  EmptyState,
  Select,
  Spinner,
  Textarea,
} from "../components/ui";
import { PRIORITIES, formatRelativeTime, initials, priorityTone, statusTone } from "../lib/format";

const VISIBILITIES = ["public", "internal"];

export default function TicketView() {
  const { id } = useParams();
  const { token, user } = useAuth();
  const [ticket, setTicket] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [body, setBody] = useState("");
  const [visibility, setVisibility] = useState("public");

  const load = useCallback(
    () =>
      api
        .getTicket(token, id)
        .then(setTicket)
        .catch((err) => setError(err.message)),
    [token, id],
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

  function reply(event) {
    event.preventDefault();
    if (!body.trim()) return;
    run(async () => {
      await api.replyTicket(token, id, { body: body.trim(), visibility });
      setBody("");
    });
  }

  if (!ticket) {
    return (
      <div className="flex justify-center py-20">
        {error ? <p className="text-sm font-semibold text-danger">{error}</p> : <Spinner />}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/inbox" className="inline-flex items-center gap-1.5 text-sm font-bold text-brand">
        <ArrowLeft size={16} /> Inbox
      </Link>

      <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl font-black text-ink">{ticket.subject}</h1>
          <p className="mt-1 text-sm text-muted">
            {ticket.reference} · from{" "}
            {ticket.requester?.name || ticket.requester?.external_id || "Unknown"}
            {ticket.requester?.email ? ` (${ticket.requester.email})` : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={statusTone(ticket.status)}>{ticket.status}</Badge>
          <Badge tone={priorityTone(ticket.priority)}>{ticket.priority}</Badge>
        </div>
      </div>

      <Card className="mt-4 flex flex-wrap items-center gap-3">
        <label className="text-xs font-bold uppercase tracking-[.08em] text-muted">Status</label>
        <Select
          value={ticket.status}
          disabled={busy}
          onChange={(event) => run(() => api.updateTicket(token, id, { status: event.target.value }))}
        >
          {["open", "pending", "resolved", "closed"].map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </Select>
        <label className="text-xs font-bold uppercase tracking-[.08em] text-muted">Priority</label>
        <Select
          value={ticket.priority}
          disabled={busy}
          onChange={(event) => run(() => api.updateTicket(token, id, { priority: event.target.value }))}
        >
          {PRIORITIES.map((priority) => (
            <option key={priority} value={priority}>
              {priority}
            </option>
          ))}
        </Select>
        <div className="ml-auto flex gap-2">
          {ticket.status === "resolved" || ticket.status === "closed" ? (
            <Button variant="secondary" disabled={busy} onClick={() => run(() => api.reopenTicket(token, id))}>
              Reopen
            </Button>
          ) : (
            <Button disabled={busy} onClick={() => run(() => api.resolveTicket(token, id))}>
              Resolve
            </Button>
          )}
        </div>
      </Card>

      <section className="mt-6 space-y-4">
        {ticket.messages.map((message) => (
          <div key={message.id} className="flex gap-3">
            <Avatar label={initials(message.author_type === "agent" ? user?.name : ticket.requester?.name) || "?"} />
            <div className="min-w-0 flex-1">
              <p className="text-xs text-muted">
                <span className="font-bold capitalize text-ink-soft">{message.author_type}</span> ·{" "}
                {formatRelativeTime(message.created_at)}
                {message.visibility === "internal" && (
                  <Badge tone="warning" className="ml-2">
                    internal
                  </Badge>
                )}
              </p>
              <div className="mt-1 whitespace-pre-wrap rounded-2xl border border-line bg-surface px-4 py-3 text-sm leading-relaxed text-ink">
                {message.body}
              </div>
            </div>
          </div>
        ))}
        {!ticket.messages.length && <EmptyState title="No messages yet" />}
      </section>

      <Card className="mt-6">
        <form onSubmit={reply} className="space-y-3">
          <Textarea
            rows={4}
            placeholder="Write a reply…"
            value={body}
            onChange={(event) => setBody(event.target.value)}
          />
          <div className="flex items-center justify-between gap-3">
            <Select
              className="w-40"
              value={visibility}
              onChange={(event) => setVisibility(event.target.value)}
            >
              {VISIBILITIES.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </Select>
            <Button type="submit" disabled={busy || !body.trim()}>
              <Send size={16} /> Send
            </Button>
          </div>
        </form>
      </Card>

      {error && <p className="mt-3 text-sm font-semibold text-danger">{error}</p>}
    </div>
  );
}
