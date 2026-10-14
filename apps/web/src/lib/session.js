// Console session persistence. The JWT and the resolved workspace live in
// localStorage so a reload keeps the agent signed in.
const KEY = "chumnouy-session";

export function loadSession() {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    return parsed && parsed.token ? parsed : null;
  } catch {
    return null;
  }
}

export function saveSession(session) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY, JSON.stringify(session));
}

export function clearSession() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(KEY);
}
