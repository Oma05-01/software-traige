"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  ChevronDown,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
} from "lucide-react";

import { useAuth } from "@/hooks/use-auth";

interface AppHeaderProps {
  onMenuClick: () => void;
  onSidebarToggle: () => void;
  sidebarCollapsed: boolean;
}

export function AppHeader({
  onMenuClick,
  onSidebarToggle,
  sidebarCollapsed,
}: AppHeaderProps) {
  const router = useRouter();
  const { user, logout } = useAuth();

  const [loggingOut, setLoggingOut] = useState(false);

  const displayName =
    [user?.first_name, user?.last_name].filter(Boolean).join(" ") ||
    user?.username ||
    "Staff";

  const initials = displayName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();

  async function handleLogout() {
  if (loggingOut) return;

  setLoggingOut(true);

  try {
    await logout();

    router.replace("/login");
    router.refresh();
  } catch (error) {
    console.error("Logout request failed:", error);
  } finally {
    setLoggingOut(false);
  }
}

  return (
    <header className="sticky top-0 z-30 flex h-[76px] items-center justify-between border-b border-[#e9edf3] bg-white/90 px-4 backdrop-blur-md sm:px-6 lg:px-8">
      {/* Left section */}
      <div className="flex min-w-0 items-center gap-3 sm:gap-4">
        {/* Mobile navigation */}
        <button
          type="button"
          aria-label="Open navigation"
          onClick={onMenuClick}
          className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
        >
          <Menu size={21} />
        </button>

        {/* Desktop sidebar toggle */}
        <button
          type="button"
          aria-label={
            sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"
          }
          title={
            sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"
          }
          onClick={onSidebarToggle}
          className="hidden rounded-lg p-2 text-slate-500 transition-colors hover:bg-slate-100 hover:text-[#294b76] lg:block"
        >
          {sidebarCollapsed ? (
            <PanelLeftOpen size={19} />
          ) : (
            <PanelLeftClose size={19} />
          )}
        </button>

        {/* Workspace identification */}
        <div className="hidden min-w-0 xl:block">
          <p className="text-[11px] font-medium tracking-wider text-slate-400 uppercase">
            Workspace
          </p>

          <p className="mt-1 text-sm font-medium text-[#24344d]">
            Software Triage Team
          </p>
        </div>

        {/* Search */}
        <div className="relative hidden min-w-0 md:block md:w-48 xl:w-72">
          <Search
            size={16}
            className="absolute top-1/2 left-3 -translate-y-1/2 text-slate-400"
          />

          <input
            type="search"
            placeholder="Search workspace..."
            disabled
            aria-label="Workspace search (coming soon)"
            className="h-10 w-full rounded-lg border border-[#e9edf3] bg-[#f8f9fb] pr-3 pl-9 text-xs text-slate-600 outline-none placeholder:text-slate-400 disabled:cursor-not-allowed"
          />
        </div>
      </div>

      {/* Right section */}
      <div className="flex shrink-0 items-center gap-3 sm:gap-5">
        {/* Environment indicator */}
        <span className="hidden text-[11px] text-slate-400 2xl:inline">
          Development environment
        </span>

        {/* Staff profile */}
        <div className="flex items-center gap-2 border-l border-[#e9edf3] pl-3 sm:gap-3 sm:pl-5">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#e8eff8] text-xs font-semibold text-[#365a88]">
            {initials}
          </div>

          <div className="hidden sm:block">
            <p className="text-xs font-semibold text-[#27364d]">
              {displayName}
            </p>

            <p className="mt-0.5 text-[10px] text-slate-400">
              Staff workspace
            </p>
          </div>

          <ChevronDown
            size={15}
            className="hidden text-slate-400 sm:block"
          />

          {/* Logout */}
          <button
            type="button"
            onClick={handleLogout}
            disabled={loggingOut}
            aria-label="Log out"
            title="Log out"
            className="ml-1 rounded-lg p-2 text-slate-500 transition-colors hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <LogOut size={17} />
          </button>
        </div>
      </div>
    </header>
  );
}