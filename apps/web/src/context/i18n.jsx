import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { DEFAULT_LOCALE, isLocale, translate } from "../lib/i18n";

const STORAGE_KEY = "chumnouy.locale";

const I18nContext = createContext(null);

function loadLocale() {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return isLocale(stored) ? stored : DEFAULT_LOCALE;
  } catch {
    return DEFAULT_LOCALE;
  }
}

export function I18nProvider({ children }) {
  const [locale, setLocaleState] = useState(loadLocale);

  const setLocale = useCallback((next) => {
    if (!isLocale(next)) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // A blocked localStorage must not break the console.
    }
    setLocaleState(next);
  }, []);

  const value = useMemo(
    () => ({
      locale,
      setLocale,
      t: (key, fallback) => translate(locale, key, fallback),
    }),
    [locale, setLocale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}
