import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  BarChart3,
  BookOpen,
  Bot,
  Clock,
  Inbox,
  KeyRound,
  LifeBuoy,
  LogOut,
  MessagesSquare,
  MessageSquareText,
  Moon,
  ScrollText,
  Settings,
  ShieldCheck,
  Sun,
  UserPlus,
  Users,
  UsersRound,
  Wand2,
  Webhook,
  Zap,
} from "lucide-react";
import { useAuth } from "../context/auth";
import { useI18n } from "../context/i18n";
import { LOCALES } from "../lib/i18n";
import { initials, isPlatformAdmin } from "../lib/format";
import CommandBar from "./CommandBar";
import { Avatar, Button, useTheme } from "./ui";

const NAV = [
  { to: "/inbox", key: "nav.inbox", icon: Inbox },
  { to: "/chat", key: "nav.chat", icon: MessagesSquare },
  { to: "/reports", key: "nav.reports", icon: BarChart3 },
  { to: "/assistant", key: "nav.assistant", icon: Bot },
  { to: "/knowledge", key: "nav.knowledge", icon: BookOpen },
  { to: "/requesters", key: "nav.requesters", icon: Users },
  { to: "/members", key: "nav.members", icon: UserPlus },
  { to: "/teams", key: "nav.teams", icon: UsersRound },
  { to: "/webhooks", key: "nav.webhooks", icon: Webhook },
  { to: "/triggers", key: "nav.triggers", icon: Zap },
  { to: "/automations", key: "nav.automations", icon: Clock },
  { to: "/canned-responses", key: "nav.canned", icon: MessageSquareText },
  { to: "/macros", key: "nav.macros", icon: Wand2 },
  { to: "/audit", key: "nav.audit", icon: ScrollText },
  { to: "/integrations", key: "nav.integrations", icon: KeyRound },
  { to: "/settings", key: "nav.settings", icon: Settings },
];

export default function Layout() {
  const { workspace, user, logout } = useAuth();
  const { t, locale, setLocale } = useI18n();
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();
  const nav = (isPlatformAdmin(user)
    ? [...NAV, { to: "/admin", key: "nav.admin", icon: ShieldCheck }]
    : NAV
  ).map(({ to, key, icon }) => ({ to, label: t(key), icon }));

  function signOut() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen bg-page text-ink-soft lg:flex">
      <aside className="border-b border-line bg-surface lg:min-h-screen lg:w-64 lg:shrink-0 lg:border-b-0 lg:border-r">
        <div className="flex h-16 items-center gap-2.5 px-6">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand text-white">
            <LifeBuoy size={18} />
          </span>
          <span className="text-base font-extrabold text-ink">Chumnouy</span>
        </div>
        <nav className="flex gap-1 px-3 pb-3 lg:flex-col">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-bold transition ${
                  isActive ? "bg-brand-soft text-brand" : "text-ink-soft hover:bg-surface-muted"
                }`
              }
            >
              <Icon size={17} />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-h-screen flex-1 flex-col">
        <header className="flex h-16 items-center justify-between gap-4 border-b border-line bg-surface px-6">
          <div className="min-w-0">
            <p className="truncate text-sm font-extrabold text-ink">
              {workspace?.name || t("shell.workspace")}
            </p>
            <p className="truncate text-xs text-muted">{workspace?.slug}</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="hidden items-center gap-1 rounded-xl bg-surface-sunken p-1 sm:flex">
              {LOCALES.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => setLocale(option.id)}
                  aria-label={`${t("shell.language")}: ${option.label}`}
                  className={`rounded-lg px-2 py-1 text-xs font-bold transition ${
                    locale === option.id ? "bg-brand text-white" : "text-muted hover:text-ink-soft"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <Avatar label={initials(user?.name || user?.email)} />
            <div className="hidden text-right sm:block">
              <p className="text-sm font-bold text-ink">{user?.name}</p>
              <p className="text-xs text-muted capitalize">{workspace?.role}</p>
            </div>
            <Button variant="ghost" onClick={toggle} aria-label={t("shell.toggleTheme")}>
              {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
            </Button>
            <Button variant="ghost" onClick={signOut} aria-label={t("shell.signOut")}>
              <LogOut size={18} />
            </Button>
          </div>
        </header>

        <main className="flex-1 px-6 py-6">
          <Outlet />
        </main>
      </div>

      <CommandBar items={nav} />
    </div>
  );
}
