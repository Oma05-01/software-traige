
"use client";

import { Suspense, useState, type ReactNode } from "react";

import { AppSidebar } from "./app-sidebar";
import { AppHeader } from "./app-header";

interface DashboardShellProps {
  children: ReactNode;
}

export function DashboardShell({
  children,
}: DashboardShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  function closeNavigation() {
    setMobileNavOpen(false);
  }

  return (
    <div className="min-h-screen bg-[#f6f8fb] text-[#25344b]">

      <Suspense
        fallback={
          <aside
            aria-hidden="true"
            className={`fixed inset-y-0 left-0 z-50 bg-[#17243a] transition-[width,transform] duration-300 ${
              sidebarCollapsed
                ? "w-[260px] lg:w-[76px]"
                : "w-[260px] lg:w-[260px]"
            } ${
              mobileNavOpen
                ? "translate-x-0"
                : "-translate-x-full"
            } lg:translate-x-0`}
          >
            <div className="flex h-[76px] items-center border-b border-white/10 px-6">
              <div className="h-9 w-36 animate-pulse rounded-lg bg-white/10" />
            </div>
          </aside>
        }
      >
        <AppSidebar
          open={mobileNavOpen}
          onClose={closeNavigation}
          collapsed={sidebarCollapsed}
        />
      </Suspense>

      {/* Mobile overlay */}
      {mobileNavOpen && (
        <button
          type="button"
          aria-label="Close navigation overlay"
          onClick={closeNavigation}
          className="fixed inset-0 z-40 bg-slate-950/40 lg:hidden"
        />
      )}

      {/* Main content */}
      <div
        className={`min-h-screen transition-[padding] duration-300 ${
          sidebarCollapsed
            ? "lg:pl-[76px]"
            : "lg:pl-[260px]"
        }`}
      >
        <AppHeader
          onMenuClick={() => setMobileNavOpen(true)}
          onSidebarToggle={() =>
            setSidebarCollapsed((previous) => !previous)
          }
          sidebarCollapsed={sidebarCollapsed}
        />

        <main className="mx-auto w-full max-w-[1600px] px-4 py-7 sm:px-6 lg:px-8 lg:py-9">
          {children}
        </main>
      </div>
    </div>
  );
}
