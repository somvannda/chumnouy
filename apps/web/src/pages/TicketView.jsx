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
  Input,
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
  const [ai, setAi] = useState(null);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiError, setAiError] = useState(null);
  const [macros, setMacros] = useState([]);
  const [macroId, setMacroId] = useState("");
  const [teams, setTeams] = useState([]);
  const [skillsDraft, setSkillsDraft] = useState("");

  const load = useCallback(
    () =>
      api
        .getTicket(token, id)
        .then((data) => {
          setTicket(data);
          setSkillsDraft((data.required_skills || []).join(", "));
        })
        .catch((err) => setError(err.message)),
    [token, id],
  );

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    api.listMacros(token).then(setMacros).catch(() => setMacros([]));
    api.listTeams(token).then(setTeams).catch(() => setTeams([]));
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

  function reply(event) {
    event.preventDefault();
    if (!body.trim()) return;
    run(async () => {
      await api.replyTicket(token, id, { body: body.trim(), visibility });
      setBody("");
    });
  }

  async function runAi(action) {
    setAiBusy(true);
    setAiError(null);
    setAi(null);
    try {
      setAi(await action());
    } catch (err) {
      setAiError(err.message);
    } finally {
      setAiBusy(false);
    }
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
          {ticket.sentiment && (
            <Badge
              tone={
                ticket.sentiment === "negative"
                  ? "danger"
                  : ticket.sentiment === "positive"
                    ? "success"
                    : "neutral"
              }
            >
              {ticket.sentiment}
            </Badge>
          )}
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
        <label className="text-xs font-bold uppercase tracking-[.08em] text-muted">Team</label>
        <Select
          value={ticket.team_id || ""}
          disabled={busy || !teams.length}
          onChange={(event) =>
            run(() =>
              api.updateTicket(
                token,
                id,
                event.target.value ? { team_id: event.target.value } : { clear_team: true },
              ),
            )
          }
        >
          <option value="">{teams.length ? "No team" : "No teams yet"}</option>
          {teams.map((team) => (
            <option key={team.id} value={team.id}>
              {team.name}
            </option>
          ))}
        </Select>
        <label className="text-xs font-bold uppercase tracking-[.08em] text-muted">Skills</label>
        <Input
          className="w-48"
          placeholder="billing, refunds"
          value={skillsDraft}
          disabled={busy}
          onChange={(event) => setSkillsDraft(event.target.value)}
          onBlur={() => {
            const next = skillsDraft
              .split(",")
              .map((skill) => skill.trim())
              .filter(Boolean);
            if (next.join("|") !== (ticket.required_skills || []).join("|")) {
              run(() => api.updateTicket(token, id, { required_skills: next }));
            }
          }}
        />
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

      <Card className="mt-4">
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-xs font-bold uppercase tracking-[.08em] text-muted">Macro</p>
          <Select
            className="w-48"
            value={macroId}
            disabled={busy || !macros.length}
            onChange={(event) => setMacroId(event.target.value)}
          >
            <option value="">{macros.length ? "Choose…" : "No macros"}</option>
            {macros.map((macro) => (
              <option key={macro.id} value={macro.id}>
                {macro.name}
              </option>
            ))}
          </Select>
          <Button
            variant="secondary"
            disabled={busy || !macroId}
            onClick={() => run(async () => { await api.applyMacro(token, id, macroId); setMacroId(""); })}
          >
            Apply
          </Button>
        </div>
      </Card>

      <Card className="mt-4">
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-xs font-bold uppercase tracking-[.08em] text-muted">Assistant</p>
          <Button
            variant="secondary"
            disabled={aiBusy}
            onClick={() =>
              runAi(async () => ({ kind: "summary", ...(await api.summarizeTicket(token, id)) }))
            }
          >
            Summarise
          </Button>
          <Button
            variant="secondary"
            disabled={aiBusy}
            onClick={() =>
              runAi(async () => ({ kind: "triage", ...(await api.triageTicket(token, id)) }))
            }
          >
            Suggest triage
          </Button>
          {aiBusy && <Spinner />}
        </div>
        {aiError && <p className="mt-2 text-sm font-semibold text-danger">{aiError}</p>}
        {ai?.kind === "summary" && <p className="mt-3 text-sm leading-relaxed text-ink">{ai.summary}</p>}
        {ai?.kind === "triage" && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            <Badge tone={priorityTone(ai.priority)}>{ai.priority}</Badge>
            {ai.tags.map((tag) => (
              <Badge key={tag} tone="neutral">
                {tag}
              </Badge>
            ))}
          </div>
        )}
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
