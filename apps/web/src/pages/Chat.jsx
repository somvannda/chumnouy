import { useCallback, useEffect, useRef, useState } from "react";
import { MessagesSquare, Send } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../context/auth";
import { Alert, Badge, Button, Card, EmptyState, Spinner, Textarea } from "../components/ui";
import { formatRelativeTime } from "../lib/format";

// The session list is polled; the open thread is streamed (SSE) so agent replies
// and requester messages appear without a refresh.
const LIST_POLL_MS = 10000;

export default function Chat() {
  const { token } = useAuth();
  const [sessions, setSessions] = useState(null);
  const [activeId, setActiveId] = useState(null);
  const [active, setActive] = useState(null);
  const [body, setBody] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const bottom = useRef(null);

  const loadSessions = useCallback(
    () =>
      api
        .chatSessions(token, { status: "open" })
        .then(setSessions)
        .catch((err) => setError(err.message)),
    [token],
  );

  const loadActive = useCallback(
    (id) =>
      api
        .chatSession(token, id)
        .then(setActive)
        .catch((err) => setError(err.message)),
    [token],
  );

  useEffect(() => {
    loadSessions();
    const timer = setInterval(loadSessions, LIST_POLL_MS);
    return () => clearInterval(timer);
  }, [loadSessions]);

  useEffect(() => {
    if (!activeId) return undefined;
    loadActive(activeId);

    // Stream the thread; reconnect when the bounded window closes.
    const controller = new AbortController();
    let cancelled = false;

    function append(message) {
      setActive((current) => {
        if (!current || current.id !== activeId) return current;
        const messages = current.messages || [];
        if (messages.some((existing) => existing.id === message.id)) return current;
        return { ...current, messages: [...messages, message] };
      });
    }

    async function run() {
      while (!cancelled) {
        try {
          await api.streamChat(token, activeId, {
            signal: controller.signal,
            onEvent: (event) => {
              if (event.event === "message" && event.data) append(event.data);
            },
          });
        } catch (err) {
          if (cancelled || err.name === "AbortError") return;
          // A dropped stream is not fatal — fall back to the next reconnect.
          await new Promise((resolve) => setTimeout(resolve, 2000));
        }
      }
    }
    run();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [activeId, token, loadActive]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [active]);

  async function reply(event) {
    event.preventDefault();
    if (!body.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.chatReply(token, activeId, { body: body.trim() });
      setBody("");
      setActive((current) =>
        current && current.id === activeId
          ? { ...current, messages: [...(current.messages || []), created] }
          : current,
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function close() {
    setBusy(true);
    try {
      await api.chatClose(token, activeId);
      setActiveId(null);
      setActive(null);
      await loadSessions();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
      <aside className="space-y-2">
        <h1 className="text-lg font-black text-ink">Live chat</h1>
        {!sessions && (
          <div className="flex justify-center py-10">
            <Spinner />
          </div>
        )}
        {sessions?.length === 0 && <EmptyState icon={MessagesSquare} title="No open chats" />}
        {sessions?.map((session) => (
          <button
            key={session.id}
            onClick={() => setActiveId(session.id)}
            className={`w-full rounded-xl px-3 py-2 text-left text-sm font-bold transition ${
              session.id === activeId ? "bg-brand-soft text-brand" : "text-ink-soft hover:bg-surface-muted"
            }`}
          >
            <span className="block truncate">{session.id.slice(0, 8)}</span>
            <span className="block text-xs font-normal text-muted">
              {formatRelativeTime(session.updated_at || session.created_at)}
            </span>
          </button>
        ))}
      </aside>

      <section className="flex min-h-[60vh] flex-col">
        <Alert>{error}</Alert>
        {!active ? (
          <EmptyState title="Select a chat" className="mt-4" />
        ) : (
          <>
            <div className="mt-4 flex items-center justify-between">
              <Badge tone={active.status === "open" ? "brand" : "neutral"}>{active.status}</Badge>
              {active.status === "open" && (
                <Button variant="secondary" disabled={busy} onClick={close}>
                  Close chat
                </Button>
              )}
            </div>
            <div className="mt-4 flex-1 space-y-3">
              {(active.messages || []).map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.author_type === "agent" ? "justify-end" : ""}`}
                >
                  <div
                    className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm ${
                      message.author_type === "agent"
                        ? "bg-brand text-white"
                        : "border border-line bg-surface text-ink"
                    }`}
                  >
                    {message.body}
                  </div>
                </div>
              ))}
              <div ref={bottom} />
            </div>
            <Card className="mt-4">
              <form onSubmit={reply} className="space-y-3">
                <Textarea
                  rows={2}
                  placeholder="Reply…"
                  value={body}
                  onChange={(event) => setBody(event.target.value)}
                  disabled={active.status !== "open"}
                />
                <div className="flex justify-end">
                  <Button type="submit" disabled={busy || active.status !== "open" || !body.trim()}>
                    <Send size={16} /> Send
                  </Button>
                </div>
              </form>
            </Card>
          </>
        )}
      </section>
    </div>
  );
}
