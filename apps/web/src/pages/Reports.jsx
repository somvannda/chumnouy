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
  const [daily, setDaily] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(
    () => api.reportSummary(token).then(setSummary).catch((err) => setError(err.message)),
    [token],
  );

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    api.reportDaily(token, { days: 14 }).then(setDaily).catch(() => setDaily(null));
  }, [token]);

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
        <>
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
          {[
            ["by_team", "By team"],
            ["by_assignee", "By assignee"],
            ["by_sentiment", "By sentiment"],
          ].map(([key, label]) => (
            <Card key={key} className="mt-4">
              <p className="text-xs font-bold uppercase tracking-[.08em] text-muted">{label}</p>
              <ul className="mt-2 space-y-1">
                {Object.entries(summary[key] || {}).map(([id, count]) => (
                  <li key={id} className="flex items-center justify-between text-sm">
                    <span className="truncate font-mono text-xs text-ink-soft">{id}</span>
                    <span className="font-bold text-ink">{count}</span>
                  </li>
                ))}
              </ul>
            </Card>
          ))}

          {daily && (
            <Card className="mt-4">
              <p className="text-xs font-bold uppercase tracking-[.08em] text-muted">
                Last {daily.days.length} days
              </p>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs font-bold uppercase tracking-[.08em] text-muted">
                      <th className="py-1 pr-3">Day</th>
                      <th className="py-1 pr-3">Created</th>
                      <th className="py-1 pr-3">Resolved</th>
                      <th className="py-1 pr-3">First responses</th>
                      <th className="py-1">Breached</th>
                    </tr>
                  </thead>
                  <tbody>
                    {daily.days.map((row) => (
                      <tr key={row.day} className="border-t border-line">
                        <td className="py-1.5 pr-3 font-mono text-xs text-ink-soft">{row.day}</td>
                        <td className="py-1.5 pr-3 font-bold text-ink">{row.created}</td>
                        <td className="py-1.5 pr-3 font-bold text-ink">{row.resolved}</td>
                        <td className="py-1.5 pr-3 font-bold text-ink">{row.first_responses}</td>
                        <td className="py-1.5 font-bold text-ink">{row.breached}</td>
                      </tr>
                    ))}
                  </tbody>
                  {daily.totals && (
                    <tfoot>
                      <tr className="border-t border-line text-xs font-bold uppercase tracking-[.08em] text-muted">
                        <td className="py-1.5 pr-3">Total</td>
                        <td className="py-1.5 pr-3">{daily.totals.created}</td>
                        <td className="py-1.5 pr-3">{daily.totals.resolved}</td>
                        <td className="py-1.5 pr-3">{daily.totals.first_responses}</td>
                        <td className="py-1.5">{daily.totals.breached}</td>
                      </tr>
                    </tfoot>
                  )}
                </table>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
