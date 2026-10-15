"use client";

import { useEffect, useState } from "react";
import { themeStorageKey } from "@/lib/theme";

type Theme = "light" | "dark";

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme | null>(null);
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    function sync() {
      let stored: string | null = null;
      try { stored = localStorage.getItem(themeStorageKey); } catch { /* Storage may be disabled. */ }
      const selected = stored === "dark" || stored === "light" ? stored : media.matches ? "dark" : "light";
      document.documentElement.dataset.theme = selected;
      setTheme(selected);
    }
    sync();
    function syncFromPage() {
      const selected = document.documentElement.dataset.theme;
      if (selected === "light" || selected === "dark") setTheme(selected);
    }
    media.addEventListener("change", sync);
    window.addEventListener("storage", sync);
    window.addEventListener("forgewatch-theme-change", syncFromPage);
    return () => { media.removeEventListener("change", sync); window.removeEventListener("storage", sync); window.removeEventListener("forgewatch-theme-change", syncFromPage); };
  }, []);
  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    setTheme(next);
    try { localStorage.setItem(themeStorageKey, next); } catch { /* The current page still changes. */ }
    window.dispatchEvent(new Event("forgewatch-theme-change"));
  }
  return <button type="button" className="button secondary compact themeToggle" onClick={toggle} disabled={!theme} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}>
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">{theme === "dark" ? <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5" /></> : <path d="M20 15.5A8.5 8.5 0 018.5 4a8.5 8.5 0 1011.5 11.5z" />}</svg>
    <span>{theme ? theme === "dark" ? "Light mode" : "Dark mode" : "Appearance"}</span>
  </button>;
}
