import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../context/auth";
import { Alert, Card, Spinner } from "../components/ui";

const CARDS = [
  ["total", "Tickets"],
  ["by_status.open", "Open"],
  ["by_status.pending", "Pending"],
  ["by_status.resolved", "Resolved"],
  ["breached", "SLA breached"],
  ["sla_compliance", "SLA compliance %"],
  ["avg_first_response_minutes", "Avg first response (min)"],
  ["avg_resolution_minutes", "Avg resolution (min)"],
  ["csat_responses", "CSAT responses"],
  ["csat_positive_pct", "CSAT positive %"],
];

function pick(obj, path) {
  return path.split(".").reduce((value, key) => (value == null ? value : value[key]), obj);
}

export default function Reports() {
  const { token } = useAuth();
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(
    () => api.reportSummary(token).then(setSummary).catch((err) => setError(err.message)),
    [token],
  );

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-lg font-black text-ink">Reports</h1>
      <p className="mt-1 text-sm text-ink-soft">Volume, response times, SLA and CSAT.</p>

      <Alert className="mt-4">{error}</Alert>
      {!summary && !error && (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      )}
      {summary && (
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {CARDS.map(([path, label]) => (
            <Card key={path}>
              <p className="text-2xl font-black text-ink">
                {pick(summary, path) ?? "—"}
              </p>
              <p className="mt-1 text-xs font-bold uppercase tracking-[.08em] text-muted">{label}</p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
