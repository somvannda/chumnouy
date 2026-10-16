import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { api } from "../lib/api";
import { clearSession, loadSession, saveSession } from "../lib/session";

const AuthContext = createContext(null);

function toSession(data) {
  return { token: data.token, user: data.user, workspace: data.workspace };
}

export function AuthProvider({ children }) {
  const [session, setSession] = useState(loadSession);

  const persist = useCallback((data) => {
    const next = toSession(data);
    saveSession(next);
    setSession(next);
    return next;
  }, []);

  const value = useMemo(
    () => ({
      session,
      token: session?.token || null,
      user: session?.user || null,
      workspace: session?.workspace || null,
      login: (email, password) => api.login({ email, password }).then(persist),
      signup: (payload) => api.signup(payload).then(persist),
      acceptInvite: (payload) => api.acceptInvite(payload).then(persist),
      logout: () => {
        clearSession();
        setSession(null);
      },
    }),
    [session, persist],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
