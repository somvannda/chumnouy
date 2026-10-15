import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, Input } from "./ui";

export default function CommandBar({ items }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    function onKey(event) {
      const tag = document.activeElement?.tagName;
      const typing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
      if ((event.key === "k" && (event.metaKey || event.ctrlKey)) || (event.key === "/" && !typing)) {
        event.preventDefault();
        setQuery("");
        setOpen(true);
      } else if (event.key === "Escape") {
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const matches = useMemo(
    () => items.filter((item) => item.label.toLowerCase().includes(query.trim().toLowerCase())),
    [items, query],
  );

  if (!open) return null;

  function go(to) {
    navigate(to);
    setOpen(false);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/30 p-6 pt-24"
      onClick={() => setOpen(false)}
    >
      <Card className="w-full max-w-md p-3" onClick={(event) => event.stopPropagation()}>
        <Input
          autoFocus
          placeholder="Go to…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && matches[0]) go(matches[0].to);
          }}
        />
        <ul className="mt-2 max-h-72 overflow-auto">
          {matches.map((item) => (
            <li key={item.to}>
              <button
                type="button"
                className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm font-bold text-ink-soft hover:bg-surface-muted"
                onClick={() => go(item.to)}
              >
                {item.icon && <item.icon size={16} />}
                {item.label}
              </button>
            </li>
          ))}
          {!matches.length && <li className="px-3 py-2 text-sm text-muted">No match</li>}
        </ul>
        <p className="mt-2 px-3 text-xs text-muted">Ctrl/⌘+K or / to open · Esc to close</p>
      </Card>
    </div>
  );
}
