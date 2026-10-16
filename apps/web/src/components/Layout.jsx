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
  Users,
  Wand2,
  Webhook,
  Zap,
} from "lucide-react";
import { useAuth } from "../context/auth";
import { initials, isPlatformAdmin } from "../lib/format";
import CommandBar from "./CommandBar";
import { Avatar, Button, useTheme } from "./ui";

const NAV = [
  { to: "/inbox", label: "Inbox", icon: Inbox },
  { to: "/chat", label: "Live chat", icon: MessagesSquare },
  { to: "/reports", label: "Reports", icon: BarChart3 },
  { to: "/assistant", label: "Assistant", icon: Bot },
  { to: "/knowledge", label: "Knowledge", icon: BookOpen },
  { to: "/requesters", label: "Requesters", icon: Users },
  { to: "/webhooks", label: "Webhooks", icon: Webhook },
  { to: "/triggers", label: "Triggers", icon: Zap },
  { to: "/automations", label: "Automations", icon: Clock },
  { to: "/canned-responses", label: "Canned", icon: MessageSquareText },
  { to: "/macros", label: "Macros", icon: Wand2 },
  { to: "/audit", label: "Audit", icon: ScrollText },
  { to: "/integrations", label: "Integrations", icon: KeyRound },
  { to: "/settings", label: "Settings", icon: Settings },
];

export default function Layout() {
  const { workspace, user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();
  const nav = isPlatformAdmin(user)
    ? [...NAV, { to: "/admin", label: "Admin", icon: ShieldCheck }]
    : NAV;

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
              {workspace?.name || "Workspace"}
            </p>
            <p className="truncate text-xs text-muted">{workspace?.slug}</p>
          </div>
          <div className="flex items-center gap-2">
            <Avatar label={initials(user?.name || user?.email)} />
            <div className="hidden text-right sm:block">
              <p className="text-sm font-bold text-ink">{user?.name}</p>
              <p className="text-xs text-muted capitalize">{workspace?.role}</p>
            </div>
            <Button variant="ghost" onClick={toggle} aria-label="Toggle theme">
              {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
            </Button>
            <Button variant="ghost" onClick={signOut} aria-label="Sign out">
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
