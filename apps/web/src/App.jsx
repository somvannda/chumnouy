import { useEffect, useState } from "react";
import { LifeBuoy, Moon, Sun, Inbox, KeyRound, Sparkles } from "lucide-react";
import { api } from "./lib/api";
import { Badge, Button, Card, useTheme } from "./components/ui";

const SECTIONS = [
  { icon: Inbox, title: "Tickets", body: "One inbox for every product and channel." },
  { icon: KeyRound, title: "Integrations", body: "API keys, scopes and signed webhooks." },
  { icon: Sparkles, title: "Assistant", body: "AI answers grounded in your help corpus." },
];

export default function App() {
  const { theme, toggle } = useTheme();
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.health().then(setHealth).catch((err) => setError(err.message));
  }, []);

  return (
    <div className="min-h-screen bg-page text-ink-soft">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-6">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand text-white">
              <LifeBuoy size={18} />
            </span>
            <span className="text-base font-extrabold text-ink">Chumnouy</span>
            <Badge tone="neutral" className="ml-1">preview</Badge>
          </div>
          <Button variant="ghost" onClick={toggle} aria-label="Toggle theme">
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-14">
        <p className="text-[11px] font-bold uppercase tracking-[.16em] text-brand">
          Tickets &amp; support as a service
        </p>
        <h1 className="mt-3 max-w-2xl text-3xl font-black leading-tight text-ink sm:text-4xl">
          Build support once, integrate it everywhere.
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-relaxed">
          Chumnouy is the API-first support platform behind every Chmaba product. Sign up,
          take an API key, and reuse conversations, attachments and an AI assistant without
          rebuilding them.
        </p>

        <div className="mt-10 grid gap-4 sm:grid-cols-3">
          {SECTIONS.map(({ icon: Icon, title, body }) => (
            <Card key={title}>
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-soft text-brand">
                <Icon size={20} />
              </span>
              <h2 className="mt-4 text-sm font-extrabold text-ink">{title}</h2>
              <p className="mt-1 text-sm leading-relaxed">{body}</p>
            </Card>
          ))}
        </div>

        <Card className="mt-8 flex items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-extrabold text-ink">API status</h2>
            <p className="mt-1 text-sm">
              {error
                ? `Backend unreachable: ${error}`
                : health
                  ? `${health.service} · ${health.status} · ${health.environment}`
                  : "Checking…"}
            </p>
          </div>
          {health && <Badge tone="success">online</Badge>}
        </Card>
      </main>
    </div>
  );
}
