import { createContext, useContext, useEffect, useState } from "react";

const ThemeContext = createContext({ theme: "light", setTheme: () => {}, toggle: () => {} });

function initialTheme() {
  if (typeof window === "undefined") return "light";
  const stored = window.localStorage.getItem("chumnouy-theme");
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(initialTheme);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    window.localStorage.setItem("chumnouy-theme", theme);
  }, [theme]);

  const value = { theme, setTheme, toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")) };
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export const useTheme = () => useContext(ThemeContext);

export function Button({ variant = "primary", className = "", ...props }) {
  const styles = {
    primary: "bg-brand text-white hover:bg-brand-hover",
    secondary: "bg-surface text-ink border border-line-strong hover:bg-surface-muted",
    ghost: "text-ink-soft hover:bg-surface-muted",
  }[variant];
  return (
    <button
      className={`inline-flex h-10 items-center justify-center gap-2 rounded-xl px-4 text-sm font-bold transition disabled:opacity-50 ${styles} ${className}`}
      {...props}
    />
  );
}

export function Card({ className = "", ...props }) {
  return (
    <div
      className={`rounded-2xl border border-line bg-surface p-5 shadow-soft ${className}`}
      {...props}
    />
  );
}

export function Badge({ tone = "brand", className = "", ...props }) {
  const tones = {
    brand: "bg-brand-soft text-brand",
    success: "bg-success-soft text-success",
    danger: "bg-danger-soft text-danger",
    warning: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
    neutral: "bg-surface-sunken text-ink-soft",
  }[tone];
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-bold capitalize ${tones} ${className}`}
      {...props}
    />
  );
}

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-bold uppercase tracking-[.08em] text-ink-soft">
        {label}
      </span>
      {children}
      {hint && <span className="mt-1 block text-xs text-muted">{hint}</span>}
    </label>
  );
}

const controlClass =
  "w-full rounded-xl border border-line-strong bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/25 disabled:opacity-60";

export function Input({ className = "", ...props }) {
  return <input className={`${controlClass} h-10 ${className}`} {...props} />;
}

export function Textarea({ className = "", ...props }) {
  return <textarea className={`${controlClass} leading-relaxed ${className}`} {...props} />;
}

export function Select({ className = "", children, ...props }) {
  return (
    <select className={`${controlClass} h-10 capitalize ${className}`} {...props}>
      {children}
    </select>
  );
}

export function Spinner({ className = "" }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={`inline-block h-4 w-4 animate-spin rounded-full border-2 border-line-strong border-t-brand ${className}`}
    />
  );
}

export function EmptyState({ icon: Icon, title, children, className = "" }) {
  return (
    <div
      className={`flex flex-col items-center justify-center rounded-2xl border border-dashed border-line-strong bg-surface px-6 py-14 text-center ${className}`}
    >
      {Icon && (
        <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-surface-sunken text-ink-soft">
          <Icon size={20} />
        </span>
      )}
      <p className="mt-4 text-sm font-extrabold text-ink">{title}</p>
      {children && <p className="mt-1 max-w-sm text-sm leading-relaxed text-ink-soft">{children}</p>}
    </div>
  );
}

export function Avatar({ label, className = "" }) {
  return (
    <span
      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-soft text-xs font-extrabold text-brand ${className}`}
    >
      {label}
    </span>
  );
}

export function Alert({ tone = "danger", children, className = "" }) {
  if (!children) return null;
  const tones = {
    danger: "border-danger/30 bg-danger-soft text-danger",
    success: "border-success/30 bg-success-soft text-success",
  }[tone];
  return (
    <div className={`rounded-xl border px-3.5 py-2.5 text-sm font-semibold ${tones} ${className}`}>
      {children}
    </div>
  );
}
