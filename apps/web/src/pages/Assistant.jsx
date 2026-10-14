import { useCallback, useEffect, useRef, useState } from "react";
import { Bot, Plus, Send, ThumbsDown, ThumbsUp } from "lucide-react";
import { api, chatStream } from "../lib/api";
import { useAuth } from "../context/auth";
import { Alert, Badge, Button, Card, EmptyState, Spinner, Textarea } from "../components/ui";
import { formatRelativeTime } from "../lib/format";

export default function Assistant() {
  const { token } = useAuth();
  const [conversations, setConversations] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [citations, setCitations] = useState([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState(null);
  const bottom = useRef(null);

  const loadConversations = useCallback(
    () => api.listConversations(token).then(setConversations).catch((e) => setError(e.message)),
    [token],
  );

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function openConversation(id) {
    setError(null);
    setActiveId(id);
    setMessages([]);
    try {
      const detail = await api.getConversation(token, id);
      setMessages(
        detail.messages.map((message) => ({
          id: message.id,
          role: message.role,
          content: message.content,
          citations: message.citations || [],
        })),
      );
    } catch (err) {
      setError(err.message);
    }
  }

  function newChat() {
    setActiveId(null);
    setMessages([]);
    setCitations([]);
    setError(null);
  }

  async function send(event) {
    event.preventDefault();
    const question = input.trim();
    if (!question || streaming) return;
    setInput("");
    setError(null);
    setCitations([]);
    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, role: "user", content: question, citations: [] },
      { id: `a-${Date.now()}`, role: "assistant", content: "", citations: [], pending: true },
    ]);
    setStreaming(true);
    try {
      await chatStream(
        token,
        { question, conversation_id: activeId || undefined },
        {
          onEvent: ({ event: name, data }) => {
            if (name === "citation") {
              setCitations(data.citations || []);
            } else if (name === "token") {
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                next[next.length - 1] = { ...last, content: last.content + data.text };
                return next;
              });
            } else if (name === "done") {
              setActiveId(data.conversation_id);
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                next[next.length - 1] = { ...last, id: data.message_id, pending: false };
                return next;
              });
            } else if (name === "error") {
              setError(data.message);
              setMessages((prev) => prev.slice(0, -1));
            }
          },
        },
      );
      await loadConversations();
    } catch (err) {
      setError(err.message);
      setMessages((prev) => prev.filter((m) => !m.pending));
    } finally {
      setStreaming(false);
    }
  }

  async function rate(message, rating) {
    try {
      await api.assistantFeedback(token, { message_id: message.id, rating });
      setMessages((prev) =>
        prev.map((m) => (m.id === message.id ? { ...m, rating } : m)),
      );
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
      <aside className="space-y-2">
        <Button variant="secondary" className="w-full" onClick={newChat}>
          <Plus size={16} /> New chat
        </Button>
        {conversations.map((conversation) => (
          <button
            key={conversation.id}
            onClick={() => openConversation(conversation.id)}
            className={`w-full rounded-xl px-3 py-2 text-left text-sm font-bold transition ${
              conversation.id === activeId
                ? "bg-brand-soft text-brand"
                : "text-ink-soft hover:bg-surface-muted"
            }`}
          >
            <span className="block truncate">{conversation.title}</span>
            <span className="block text-xs font-normal text-muted">
              {formatRelativeTime(conversation.updated_at)}
            </span>
          </button>
        ))}
      </aside>

      <section className="flex min-h-[70vh] flex-col">
        <h1 className="text-lg font-black text-ink">Assistant</h1>
        <Alert className="mt-3">{error}</Alert>

        <div className="mt-4 flex-1 space-y-4">
          {messages.length === 0 && (
            <EmptyState icon={Bot} title="Ask about your product">
              Answers are grounded in your knowledge base.
            </EmptyState>
          )}
          {messages.map((message) => (
            <div key={message.id} className={`flex ${message.role === "user" ? "justify-end" : ""}`}>
              <div className="max-w-[85%]">
                <div
                  className={`whitespace-pre-wrap rounded-2xl border px-4 py-3 text-sm leading-relaxed ${
                    message.role === "user"
                      ? "border-transparent bg-brand text-white"
                      : "border-line bg-surface text-ink"
                  }`}
                >
                  {message.content || (message.pending ? "…" : "")}
                </div>
                {message.role === "assistant" && message.citations?.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {message.citations.map((citation) => (
                      <Badge key={citation.id} tone="neutral">
                        {citation.title}
                      </Badge>
                    ))}
                  </div>
                )}
                {message.role === "assistant" && !message.pending && message.id && (
                  <div className="mt-2 flex items-center gap-2 text-muted">
                    <button onClick={() => rate(message, "up")} aria-label="Good answer">
                      <ThumbsUp size={15} className={message.rating === "up" ? "text-success" : ""} />
                    </button>
                    <button onClick={() => rate(message, "down")} aria-label="Bad answer">
                      <ThumbsDown size={15} className={message.rating === "down" ? "text-danger" : ""} />
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={bottom} />
        </div>

        <Card className="mt-4">
          <form onSubmit={send} className="space-y-3">
            <Textarea
              rows={2}
              placeholder="Ask a question…"
              value={input}
              onChange={(event) => setInput(event.target.value)}
            />
            <div className="flex items-center justify-between">
              <p className="text-xs text-muted">
                {streaming ? "Answering…" : citations.length ? `${citations.length} sources` : ""}
              </p>
              <Button type="submit" disabled={streaming || !input.trim()}>
                <Send size={16} /> Send
              </Button>
            </div>
          </form>
        </Card>
      </section>
    </div>
  );
}
