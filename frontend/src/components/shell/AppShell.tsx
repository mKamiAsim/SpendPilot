import {
  CalendarClock,
  ChartColumn,
  CreditCard,
  FileText,
  LayoutDashboard,
  Menu,
  Moon,
  Search,
  Settings,
  Shield,
  SlidersHorizontal,
  Sparkles,
  Sun,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { NavLink, Outlet } from "react-router";

import { Button } from "../ui/button";
import { useSession } from "../../app/session";
import { useTheme } from "../../app/theme";
import { cn } from "../../lib/cn";

const destinations = [
  { label: "Overview", to: "/overview", icon: LayoutDashboard },
  { label: "Cards & accounts", to: "/money/cards", icon: CreditCard, group: "Money" },
  { label: "Transactions", to: "/money/transactions", icon: FileText, group: "Money" },
  { label: "Statements", to: "/money/statements", icon: FileText, group: "Money" },
  { label: "Analytics", to: "/money/analytics", icon: ChartColumn, group: "Money" },
  { label: "Obligations", to: "/money/obligations", icon: CalendarClock, group: "Money" },
  { label: "Advisor", to: "/intelligence/advisor", icon: Sparkles, group: "Intelligence" },
  { label: "Scenarios", to: "/intelligence/scenarios", icon: SlidersHorizontal, group: "Intelligence" },
  { label: "Settings", to: "/settings", icon: Settings },
];

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useSession();
  const items = user?.role === "admin" ? [...destinations, { label: "Administration", to: "/admin", icon: Shield }] : destinations;
  let lastGroup = "";
  return (
    <div className="flex flex-col gap-1">
      {items.map((item) => {
        const group = "group" in item ? item.group : undefined;
        const showGroup = group && group !== lastGroup;
        if (group) lastGroup = group;
        const Icon = item.icon;
        return (
          <div key={item.to}>
            {showGroup ? (
              <p className="px-3 pb-1 pt-4 text-xs font-medium uppercase tracking-[0.14em] text-ink-secondary">
                {group}
              </p>
            ) : null}
            <NavLink
              to={item.to}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  "flex h-11 items-center gap-3 rounded-lg px-3 text-sm",
                  isActive ? "bg-surface-secondary font-medium text-ink" : "text-ink-secondary",
                )
              }
            >
              <Icon aria-hidden="true" size={18} />
              {item.label}
            </NavLink>
          </div>
        );
      })}
    </div>
  );
}

export function AppShell() {
  const { user } = useSession();
  const { theme, toggle } = useTheme();
  const [menuOpen, setMenuOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [query, setQuery] = useState("");
  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return destinations.filter((item) => item.label.toLowerCase().includes(needle));
  }, [query]);

  useEffect(() => {
    const source = new EventSource("/api/v1/events");
    return () => source.close();
  }, []);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen(true);
      }
      if (event.key === "Escape") {
        setPaletteOpen(false);
        setMenuOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="min-h-screen bg-canvas text-ink" data-testid="shell">
      <div className="mx-auto flex min-h-screen max-w-[1440px]">
        <aside
          className="hidden w-[232px] shrink-0 border-r border-line bg-surface md:flex md:flex-col"
          data-testid="sidebar"
        >
          <div className="flex h-16 items-center px-4">
            <Wordmark />
          </div>
          <nav aria-label="Primary" className="flex-1 overflow-y-auto px-3 pb-6">
            <NavItems />
          </nav>
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-16 items-center gap-3 border-b border-line bg-surface px-4 md:px-8">
            <Button
              variant="secondary"
              size="sm"
              className="md:hidden"
              aria-expanded={menuOpen}
              aria-controls="mobile-navigation"
              data-testid="open-menu"
              onClick={() => setMenuOpen(true)}
            >
              <Menu aria-hidden="true" size={18} />
              Menu
            </Button>
            <Wordmark className="md:hidden" />
            <Button variant="secondary" size="sm" className="ml-auto" onClick={() => setPaletteOpen(true)}>
              <Search aria-hidden="true" size={16} />
              <span className="hidden sm:inline">Search navigation</span>
              <kbd className="hidden rounded border border-line px-1.5 text-xs text-ink-secondary lg:inline">Ctrl K</kbd>
            </Button>
            <Button
              variant="secondary"
              size="sm"
              aria-pressed={theme === "dark"}
              data-testid="theme-toggle"
              onClick={toggle}
            >
              {theme === "dark" ? <Sun aria-hidden="true" size={16} /> : <Moon aria-hidden="true" size={16} />}
              <span className="sr-only">{theme === "dark" ? "Use light theme" : "Use dark theme"}</span>
              <span className="hidden sm:inline">{theme === "dark" ? "Light" : "Dark"}</span>
            </Button>
          </header>
          {user && !user.email_verified ? (
            <p className="border-b border-line bg-surface-secondary px-4 py-3 text-sm md:px-8">
              This email address is not verified yet. Statement import stays closed until it is.
            </p>
          ) : null}
          <main className="flex-1 px-4 py-6 md:px-8 md:py-8">
            <Outlet />
          </main>
        </div>
      </div>
      {menuOpen ? (
        <div className="fixed inset-0 z-40 md:hidden" id="mobile-navigation">
          <button className="absolute inset-0 bg-[#17212f]/40" aria-label="Close menu" onClick={() => setMenuOpen(false)} />
          <nav aria-label="Primary" className="absolute inset-y-0 left-0 flex w-[min(100%,280px)] flex-col bg-surface p-4">
            <div className="mb-4 flex items-center justify-between">
              <Wordmark />
              <Button variant="ghost" size="sm" onClick={() => setMenuOpen(false)} aria-label="Close menu">
                <X aria-hidden="true" size={18} />
              </Button>
            </div>
            <NavItems onNavigate={() => setMenuOpen(false)} />
          </nav>
        </div>
      ) : null}
      {paletteOpen ? (
        <div className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-24">
          <button className="absolute inset-0 bg-[#17212f]/40" aria-label="Close search" onClick={() => setPaletteOpen(false)} />
          <div role="dialog" aria-label="Search navigation" className="relative w-full max-w-lg rounded-xl border border-line bg-surface p-3 shadow-sm">
            <input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Jump to a section"
              className="h-11 w-full rounded-lg border border-line bg-canvas px-3"
            />
            <ul className="mt-2">
              {results.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    className="flex h-11 items-center rounded-lg px-3 text-sm"
                    onClick={() => {
                      setPaletteOpen(false);
                      setQuery("");
                    }}
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("flex items-center gap-2 text-sm font-semibold", className)}>
      <span aria-hidden="true" className="h-2.5 w-2.5 rounded-sm bg-action" />
      SpendPilot
    </span>
  );
}
