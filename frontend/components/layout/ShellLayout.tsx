"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  AlertTriangle,
  GitBranch,
  Shield,
  Bot,
  Radio,
  PanelLeftClose,
  PanelLeftOpen,
  Menu,
  X,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/incidents", label: "Incidents", icon: AlertTriangle },
  { href: "/plans", label: "Rescue Plans", icon: GitBranch },
  { href: "/resources", label: "Resources", icon: Shield },
  { href: "/agent", label: "AI Agent", icon: Bot },
];

const SIDEBAR_EXPANDED_W = 240; // px
const SIDEBAR_COLLAPSED_W = 56; // px (icon-only)
const TRANSITION_MS = 250;

export function ShellLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();
  const sidebarRef = useRef<HTMLElement>(null);

  // Close mobile drawer on navigation
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  // After sidebar width transition finishes, tell Leaflet to recalculate
  const handleTransitionEnd = useCallback(() => {
    window.dispatchEvent(new Event("resize"));
  }, []);

  const sidebarW = collapsed ? SIDEBAR_COLLAPSED_W : SIDEBAR_EXPANDED_W;
  const isCollapsed = collapsed;

  // Public citizen dashboard has its own clean, focused layout without admin chrome
  if (pathname?.startsWith("/help")) {
    return <div className="min-h-screen bg-background text-foreground flex flex-col">{children}</div>;
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── Desktop sidebar ── */}
      <aside
        ref={sidebarRef}
        onTransitionEnd={handleTransitionEnd}
        className="hidden md:flex flex-col border-r border-card-border bg-surface overflow-hidden shrink-0"
        style={{ width: sidebarW, transition: `width ${TRANSITION_MS}ms ease` }}
      >
        {/* Logo row */}
        <div className="flex items-center gap-2 px-3 py-3 border-b border-card-border min-h-[48px]">
          <Radio className="h-4.5 w-4.5 text-accent shrink-0" />
          {!isCollapsed && (
            <div className="overflow-hidden whitespace-nowrap leading-tight">
              <div className="text-[13px] font-bold tracking-widest text-foreground">
                RESCUNET
              </div>
              <div className="text-[9px] tracking-wider text-muted">
                EMERGENCY COORDINATION
              </div>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-2 space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                title={isCollapsed ? item.label : undefined}
                className={`flex items-center gap-3 px-3 py-1.5 text-[13px] rounded-md transition-colors ${
                  active
                    ? "bg-accent/10 text-accent font-semibold"
                    : "text-muted hover:text-foreground hover:bg-card"
                } ${isCollapsed ? "justify-center" : ""}`}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                {!isCollapsed && <span className="whitespace-nowrap">{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Footer + toggle */}
        <div className="border-t border-card-border">
          <button
            onClick={() => setCollapsed((c) => !c)}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 text-muted hover:text-foreground hover:bg-card transition-colors"
            title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {isCollapsed ? (
              <PanelLeftOpen className="h-4 w-4 shrink-0" />
            ) : (
              <>
                <PanelLeftClose className="h-4 w-4 shrink-0" />
                <span className="text-xs whitespace-nowrap">Collapse</span>
              </>
            )}
          </button>
        </div>
      </aside>

      {/* ── Mobile sidebar overlay ── */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}
      <aside
        className={`fixed z-50 top-0 left-0 h-full w-60 flex flex-col border-r border-card-border bg-surface md:hidden transition-transform duration-250 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Logo row */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-card-border">
          <div className="flex items-center gap-2">
            <Radio className="h-4.5 w-4.5 text-accent" />
            <div className="leading-tight">
              <div className="text-[13px] font-bold tracking-widest text-foreground">
                RESCUNET
              </div>
              <div className="text-[9px] tracking-wider text-muted">
                EMERGENCY COORDINATION
              </div>
            </div>
          </div>
          <button
            onClick={() => setMobileOpen(false)}
            className="text-muted hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-2 space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-1.5 text-[13px] rounded-md transition-colors ${
                  active
                    ? "bg-accent/10 text-accent font-semibold"
                    : "text-muted hover:text-foreground hover:bg-card"
                }`}
              >
                <item.icon className="h-4 w-4" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* ── Main content ── */}
      <main className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Mobile header */}
        <header className="md:hidden flex items-center justify-between px-4 py-2.5 border-b border-card-border bg-surface">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setMobileOpen(true)}
              className="p-1.5 text-muted hover:text-foreground transition-colors"
              aria-label="Open navigation"
            >
              <Menu className="h-4 w-4" />
            </button>
            <Radio className="h-4 w-4 text-accent" />
            <span className="text-[13px] font-bold tracking-widest">RESCUNET</span>
          </div>
          <nav className="flex items-center gap-3">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="p-1.5 text-muted hover:text-foreground transition-colors"
              >
                <item.icon className="h-4 w-4" />
              </Link>
            ))}
          </nav>
        </header>

        {/* Page content */}
        <div className="flex-1 overflow-hidden">{children}</div>
      </main>
    </div>
  );
}
