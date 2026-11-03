
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  ClipboardCheck,
  LayoutDashboard,
  MessageSquare,
  PanelsTopLeft,
  Ticket,
  Workflow,
  X,
} from "lucide-react";

interface AppSidebarProps {
  open: boolean;
  onClose: () => void;
  collapsed: boolean;
}

const navigation = [
  {
    label: "Overview",
    href: "/dashboard",
    icon: LayoutDashboard,
  },
  {
    label: "Tickets",
    href: "/tickets",
    icon: Ticket,
  },
  {
    label: "Human Reviews",
    href: "/reviews",
    icon: ClipboardCheck,
  },
  {
    label: "Virtual Office",
    href: "/office",
    icon: PanelsTopLeft,
  },
];

export function AppSidebar({
  open,
  onClose,
  collapsed,
}: AppSidebarProps) {
  const pathname = usePathname();

  return (
    <aside
      className={`fixed inset-y-0 left-0 z-50 flex w-[260px] flex-col border-r border-white/10 bg-[#17243a] text-white transition-[width,transform] duration-300 ${
        collapsed ? "lg:w-[76px]" : "lg:w-[260px]"
      } ${open ? "translate-x-0" : "-translate-x-full"} lg:translate-x-0`}
    >
      {/* Brand */}
      <div
        className={`flex h-[76px] shrink-0 items-center border-b border-white/10 ${
          collapsed
            ? "justify-center px-3"
            : "justify-between px-6"
        }`}
      >
        <Link
          href="/dashboard"
          onClick={onClose}
          title={collapsed ? "Software Triage Team" : undefined}
          className="flex min-w-0 items-center gap-3"
        >
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#527cbd]">
            <Workflow size={22} strokeWidth={1.8} />
          </div>

          <div className={collapsed ? "lg:hidden" : ""}>
            <p className="whitespace-nowrap text-sm font-semibold tracking-wide">
              Software Triage
            </p>

            <p className="mt-0.5 whitespace-nowrap text-[10px] tracking-[0.18em] text-slate-400 uppercase">
              Team workspace
            </p>
          </div>
        </Link>

        <button
          type="button"
          aria-label="Close navigation"
          onClick={onClose}
          className="rounded-lg p-2 text-slate-400 hover:bg-white/10 lg:hidden"
        >
          <X size={19} />
        </button>
      </div>

      {/* Navigation */}
      <div className={`px-4 pt-7 ${collapsed ? "lg:px-2" : ""}`}>
        <p
          className={`mb-3 px-3 text-[10px] font-semibold tracking-[0.16em] text-slate-500 uppercase ${
            collapsed ? "lg:hidden" : ""
          }`}
        >
          Workspace
        </p>

        <nav className="space-y-1">
          {navigation.map((item) => {
            const Icon = item.icon;

            const active =
              pathname === item.href ||
              (item.href !== "/dashboard" &&
                pathname.startsWith(`${item.href}/`));

            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onClose}
                title={collapsed ? item.label : undefined}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-3 rounded-xl px-3 py-3 text-[13px] transition-colors ${
                  collapsed ? "lg:justify-center lg:px-2" : ""
                } ${
                  active
                    ? "bg-[#29466e] font-medium text-white"
                    : "text-slate-400 hover:bg-white/5 hover:text-white"
                }`}
              >
                <Icon
                  size={19}
                  strokeWidth={1.8}
                  className="shrink-0"
                />

                <span
                  className={`whitespace-nowrap ${
                    collapsed ? "lg:hidden" : ""
                  }`}
                >
                  {item.label}
                </span>

                {active && (
                  <span
                    className={`ml-auto h-1.5 w-1.5 shrink-0 rounded-full bg-[#80b7df] ${
                      collapsed ? "lg:hidden" : ""
                    }`}
                  />
                )}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Workspace information */}
      <div
        className={`mt-auto p-4 ${
          collapsed ? "lg:px-2" : ""
        }`}
      >
        <div
          className={`rounded-xl border border-white/10 bg-white/[0.04] p-4 ${
            collapsed ? "lg:hidden" : ""
          }`}
        >
          <div className="mb-3 flex items-center gap-2">
            <Activity size={16} className="text-[#80b7df]" />

            <span className="text-xs font-medium text-slate-200">
              Workspace activity
            </span>
          </div>

          <p className="text-xs leading-5 text-slate-400">
            Agent activity and workflow information will appear
            here when the backend is connected.
          </p>

          <Link
            href="/reviews"
            onClick={onClose}
            className="mt-4 flex items-center gap-2 text-xs font-medium text-[#91bce5] hover:text-white"
          >
            <MessageSquare size={14} />
            Review workspace
          </Link>
        </div>

        {collapsed && (
          <div className="hidden items-center justify-center py-3 text-[10px] font-semibold tracking-wider text-slate-500 lg:flex">
            STT
          </div>
        )}

        {!collapsed && (
          <p className="px-2 pt-5 text-[10px] text-slate-500">
            Software Triage Team · Development
          </p>
        )}
      </div>
    </aside>
  );
}
