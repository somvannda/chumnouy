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
    neutral: "bg-surface-sunken text-ink-soft",
  }[tone];
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-bold ${tones} ${className}`}
      {...props}
    />
  );
}
