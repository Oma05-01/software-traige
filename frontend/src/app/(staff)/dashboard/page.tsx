
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import {
  ArrowUpRight,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  Ticket,
} from "lucide-react";

import { getDashboardOverview } from "@/lib/api/dashboard";
import type { DashboardOverview } from "@/lib/types/dashboard";

import { StatCard } from "@/components/dashboard/stat-card";
import { AgentPipeline } from "@/components/dashboard/agent-pipeline";
import { ActivityFeed } from "@/components/dashboard/activity-feed";

const statistics = [
  {
    title: "Total tickets",
    description: "Submitted reports",
    icon: Ticket,
    accent: "bg-[#edf3fc] text-[#587eaf]",
    valueKey: "total_tickets",
  },
  {
    title: "In progress",
    description: "Currently being processed",
    icon: Clock3,
    accent: "bg-[#fff5e9] text-[#ca9051]",
    valueKey: "in_progress_tickets",
  },
  {
    title: "Pending reviews",
    description: "Agent proposals awaiting staff decisions",
    icon: ClipboardCheck,
    accent: "bg-[#f3efff] text-[#8b78bb]",
    valueKey: "pending_review_requests",
  },
  {
    title: "Completed",
    description: "Successfully processed or closed",
    icon: CheckCircle2,
    accent: "bg-[#eaf7f1] text-[#529b7a]",
    valueKey: "completed_tickets",
  },
] as const;

export default function DashboardPage() {
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadDashboard() {
      try {
        const data = await getDashboardOverview();

        if (active) {
          setOverview(data);
          setError(null);
        }
      } catch (err: unknown) {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load dashboard information."
          );
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadDashboard();

    const interval = window.setInterval(() => {
      void loadDashboard();
    }, 15000);

    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  const values = overview?.statistics;

  return (
    <div className="space-y-8">
      {/* Page heading */}
      <section className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <div className="mb-3 flex items-center gap-2 text-[10px] font-semibold tracking-[0.17em] text-slate-400 uppercase">
            <span>Workspace</span>
            <span>/</span>
            <span className="text-[#587eaf]">Overview</span>
          </div>

          <h1 className="text-2xl font-semibold tracking-tight text-[#263750] sm:text-3xl">
            Dashboard overview
          </h1>

          <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">
            Monitor ticket processing, agent activity and decisions
            requiring human attention.
          </p>
        </div>

        <Link
          href="/tickets"
          className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#294b76] px-4 text-xs font-medium text-white transition-colors hover:bg-[#203d62]"
        >
          Explore tickets
          <ArrowUpRight size={15} />
        </Link>
      </section>

      {/* API connection state */}
      {error ? (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-red-100 bg-red-50 px-4 py-3">
          <span className="h-2 w-2 rounded-full bg-red-500" />

          <p className="text-xs text-red-700">
            Dashboard data could not be refreshed: {error}
          </p>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-[#e6ebf1] bg-white px-4 py-3">
          <span
            className={`h-2 w-2 rounded-full ${
              loading ? "bg-amber-400" : "bg-emerald-500"
            }`}
          />

          <p className="text-xs text-slate-600">
            <span className="font-medium text-[#34465f]">
              {loading ? "Loading dashboard data..." : "Dashboard connected."}
            </span>{" "}
            {loading
              ? "Retrieving ticket and workflow statistics."
              : "Statistics and activity are refreshed every 15 seconds."}
          </p>

          <span className="ml-auto rounded-full bg-[#f4f5f7] px-2.5 py-1 text-[10px] font-medium text-slate-500">
            Live data
          </span>
        </div>
      )}

      {/* Statistics */}
      <section>
        <div className="mb-4">
          <h2 className="text-sm font-semibold text-[#293b54]">
            Ticket overview
          </h2>

          <p className="mt-1 text-xs text-slate-400">
            Your workspace at a glance
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {statistics.map((stat) => (
            <StatCard
              key={stat.title}
              title={stat.title}
              description={stat.description}
              icon={stat.icon}
              accent={stat.accent}
              value={values ? values[stat.valueKey] : "—"}
            />
          ))}
        </div>

        <div className="mt-4 flex flex-wrap gap-3">
          <span className="rounded-lg border border-[#e9edf3] bg-white px-3 py-2 text-xs text-slate-500">
            Active workflows:{" "}
            <strong className="text-[#34465f]">
              {values?.active_workflows ?? "—"}
            </strong>
          </span>

          <span className="rounded-lg border border-[#e9edf3] bg-white px-3 py-2 text-xs text-slate-500">
            Failed workflows:{" "}
            <strong className="text-[#34465f]">
              {values?.failed_workflows ?? "—"}
            </strong>
          </span>
        </div>
      </section>

      {/* Agent pipeline and review shortcut */}
      <section className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
        <AgentPipeline />

        <aside className="rounded-2xl border border-[#e9edf3] bg-white p-5 shadow-[0_2px_8px_rgba(30,50,80,0.025)] sm:p-6">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#f2effb]">
            <ClipboardCheck size={20} className="text-[#8574b4]" />
          </div>

          <h2 className="mt-5 text-sm font-semibold text-[#2c3c54]">
            Human review
          </h2>

          <p className="mt-2 text-xs leading-5 text-slate-500">
            Inspect agent proposals, request corrections, and authorize actions.
          </p>

          <div className="mt-6 rounded-xl bg-[#f8f9fb] p-4">
            <p className="text-[11px] font-medium text-slate-500">
              Review queue
            </p>

            <p className="mt-2 text-2xl font-semibold text-[#30445f]">
              {values?.pending_review_requests ?? "—"}
            </p>

            <p className="mt-1 text-[10px] text-slate-400">
              Pending review requests
            </p>
          </div>

          <Link
            href="/reviews"
            className="mt-5 flex h-10 w-full items-center justify-center gap-2 rounded-xl border border-[#dfe6ef] text-xs font-semibold text-[#43648d] transition-colors hover:bg-[#f4f7fb]"
          >
            Open review queue
            <ArrowUpRight size={14} />
          </Link>
        </aside>
      </section>

      {/* Recent workflow activity */}
      <ActivityFeed
        events={overview?.recent_activity ?? []}
        loading={loading}
        error={error}
      />
    </div>
  );
}
