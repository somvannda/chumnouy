// Pure formatting/label helpers shared by the console. Kept dependency-free so
// they can be unit-tested with `node --test`.

const STATUS_TONES = {
  open: "brand",
  pending: "warning",
  resolved: "success",
  closed: "neutral",
};

const PRIORITY_TONES = {
  low: "neutral",
  normal: "neutral",
  high: "warning",
  urgent: "danger",
};

export const STATUSES = ["open", "pending", "resolved", "closed"];
export const PRIORITIES = ["low", "normal", "high", "urgent"];

export function statusTone(status) {
  return STATUS_TONES[status] || "neutral";
}

export function priorityTone(priority) {
  return PRIORITY_TONES[priority] || "neutral";
}

export function initials(name) {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function truncate(text, max = 120) {
  const value = String(text || "").trim();
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

const RELATIVE_UNITS = [
  [60, "m"],
  [60, "h"],
  [24, "d"],
  [7, "w"],
  [4.34, "mo"],
  [12, "y"],
];

export function formatRelativeTime(iso, now = Date.now()) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  let seconds = Math.max(0, Math.round((now - then) / 1000));
  if (seconds < 45) return "just now";
  let value = seconds;
  let unit = "s";
  for (const [step, nextUnit] of RELATIVE_UNITS) {
    if (value < step) break;
    value = value / step;
    unit = nextUnit;
  }
  const rounded = Math.max(1, Math.round(value));
  return `${rounded}${unit} ago`;
}

export function buildQuery(params = {}) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, value);
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

// Saved views map to filters the /tickets endpoint understands.
export const SAVED_VIEWS = [
  { id: "all", label: "All tickets", params: {} },
  { id: "open", label: "Open", params: { status: "open" } },
  { id: "pending", label: "Pending", params: { status: "pending" } },
  { id: "unassigned", label: "Unassigned", params: { assignee: "none" } },
  { id: "resolved", label: "Resolved", params: { status: "resolved" } },
];

export function viewParams(viewId) {
  return (SAVED_VIEWS.find((view) => view.id === viewId) || SAVED_VIEWS[0]).params;
}
