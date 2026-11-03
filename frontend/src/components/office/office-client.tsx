
"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import {
  Activity,
  Clock3,
  RefreshCw,
  Users,
} from "lucide-react";

import { getOfficeActivity } from "@/lib/api/office";

import type {
  OfficeActivity,
  OfficeExecution,
} from "@/lib/types/office";

import type { AgentType } from "@/lib/types/workflow";

import { OfficeScene } from "./OfficeScene";


const AGENT_NAMES: Record<AgentType, string> = {
  receptionist: "Receptionist",
  debugger: "Debugger",
  product_manager: "Product Manager",
  support_rep: "Support Rep",
};


function formatDate(value: string | null) {
  if (!value) return "Not started";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unavailable";
  }

  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}


function executionStatus(status: OfficeExecution["status"]) {
  switch (status) {
    case "succeeded":
      return {
        label: "Completed",
        classes: "bg-emerald-50 text-emerald-700",
      };

    case "running":
      return {
        label: "Working",
        classes: "bg-blue-50 text-blue-700",
      };

    case "queued":
      return {
        label: "Queued",
        classes: "bg-amber-50 text-amber-700",
      };

    case "failed":
      return {
        label: "Failed",
        classes: "bg-red-50 text-red-700",
      };

    default:
      return {
        label: "Skipped",
        classes: "bg-slate-100 text-slate-500",
      };
  }
}


export function OfficeClient() {
  const [activity, setActivity] =
    useState<OfficeActivity | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadOffice = useCallback(async () => {
    try {
      const data = await getOfficeActivity();

      setActivity(data);
      setError(null);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load office activity."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;

    async function refresh() {
      try {
        const data = await getOfficeActivity();

        if (active) {
          setActivity(data);
          setError(null);
        }
      } catch (err: unknown) {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load office activity."
          );
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void refresh();

    const interval = window.setInterval(() => {
      void refresh();
    }, 5000);

    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  const agents = activity?.agents ?? [];

  const workingCount = agents.filter(
    (agent) => agent.status === "working"
  ).length;

  const activeAssignments = agents.reduce(
    (total, agent) => total + agent.active_count,
    0
  );

  const recentExecutions = activity?.recent_executions ?? [];

  return (
    <div className="space-y-6">

      {/* Header */}
      <section className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <div className="mb-3 flex items-center gap-2 text-[10px] font-semibold tracking-[0.17em] text-slate-400 uppercase">
            <span>Workspace</span>
            <span>/</span>
            <span className="text-[#587eaf]">Virtual Office</span>
          </div>

          <h1 className="text-2xl font-semibold tracking-tight text-[#263750] sm:text-3xl">
            Virtual office
          </h1>

          <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">
            Observe the four agents as they process bug reports
            and feature requests.
          </p>
        </div>

        <div className="flex items-center gap-2 rounded-xl border border-[#e6ebf1] bg-white px-4 py-3">
          <span
            className={`h-2 w-2 rounded-full ${
              error
                ? "bg-red-500"
                : loading
                  ? "bg-amber-400"
                  : "bg-emerald-500"
            }`}
          />

          <span className="text-xs text-slate-600">
            {error
              ? "Connection issue"
              : loading
                ? "Connecting..."
                : "Live office"}
          </span>

          <RefreshCw
            size={13}
            className={`ml-1 text-slate-400 ${
              loading ? "animate-spin" : ""
            }`}
          />
        </div>
      </section>

      {error && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-100 bg-red-50 p-4">
          <p className="text-xs text-red-700">{error}</p>

          <button
            type="button"
            onClick={() => {
              setLoading(true);
              void loadOffice();
            }}
            className="text-xs font-semibold text-red-700 hover:underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* Summary */}
      <section className="grid grid-cols-1 gap-3 sm:grid-cols-3">

        <div className="rounded-xl border border-[#e9edf3] bg-white p-4">
          <div className="flex items-center gap-2 text-slate-400">
            <Users size={16} />
            <span className="text-[10px] font-semibold uppercase">
              Team members
            </span>
          </div>

          <p className="mt-2 text-2xl font-semibold text-[#2c3c54]">
            4
          </p>

          <p className="mt-1 text-[10px] text-slate-400">
            Registered agents
          </p>
        </div>

        <div className="rounded-xl border border-[#e9edf3] bg-white p-4">
          <div className="flex items-center gap-2 text-slate-400">
            <Activity size={16} />
            <span className="text-[10px] font-semibold uppercase">
              Working now
            </span>
          </div>

          <p className="mt-2 text-2xl font-semibold text-[#2c3c54]">
            {workingCount}
          </p>

          <p className="mt-1 text-[10px] text-slate-400">
            Agents with running executions
          </p>
        </div>

        <div className="rounded-xl border border-[#e9edf3] bg-white p-4">
          <div className="flex items-center gap-2 text-slate-400">
            <Clock3 size={16} />
            <span className="text-[10px] font-semibold uppercase">
              Active assignments
            </span>
          </div>

          <p className="mt-2 text-2xl font-semibold text-[#2c3c54]">
            {activeAssignments}
          </p>

          <p className="mt-1 text-[10px] text-slate-400">
            Queued and running executions
          </p>
        </div>
      </section>

      {/* Office scene */}
      <section className="overflow-hidden rounded-2xl border border-[#e1e8ef] bg-white shadow-[0_8px_28px_rgba(30,50,80,0.05)]">

        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#dfe6ed] px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-[#2c3c54]">
              Operations floor
            </h2>

            <p className="mt-1 text-[10px] text-slate-400">
              Live agent workspace
            </p>
          </div>

          <span className="text-[10px] text-slate-400">
            {activity
              ? `Updated ${formatDate(activity.updated_at)}`
              : "Waiting for office data"}
          </span>
        </div>

        <OfficeScene agents={agents} />

        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-[#dfe6ed] bg-white px-5 py-3">
          {[
            ["Working", "bg-emerald-500"],
            ["Queued", "bg-amber-400"],
            ["Completed", "bg-blue-500"],
            ["Failed", "bg-red-500"],
            ["Idle", "bg-slate-300"],
          ].map(([label, color]) => (
            <span
              key={label}
              className="flex items-center gap-2 text-[10px] text-slate-500"
            >
              <span className={`h-2 w-2 rounded-full ${color}`} />
              {label}
            </span>
          ))}
        </div>
      </section>

      {/* Recent assignments */}
      <section className="rounded-2xl border border-[#e9edf3] bg-white p-5 sm:p-6">

        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-[#273750]">
              Recent assignments
            </h2>

            <p className="mt-1 text-xs text-slate-400">
              Latest work performed by the team
            </p>
          </div>

          <Activity size={18} className="text-[#6687b5]" />
        </div>

        {recentExecutions.length === 0 ? (
          <p className="py-10 text-center text-xs text-slate-400">
            No agent executions have been recorded yet.
          </p>
        ) : (
          <div className="mt-4 divide-y divide-[#edf0f5]">
            {recentExecutions.map((execution) => {
              const status = executionStatus(execution.status);

              return (
                <div
                  key={execution.id}
                  className="flex flex-wrap items-center justify-between gap-3 py-3"
                >
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-[#34465f]">
                      {AGENT_NAMES[execution.agent_type]}

                      <span className="ml-2 font-normal text-slate-400">
                        · Attempt {execution.attempt}
                      </span>
                    </p>

                    <Link
                      href={`/tickets/${encodeURIComponent(execution.ticket_id)}`}
                      className="mt-1 block truncate text-xs text-[#58749b] hover:text-[#294b76]"
                    >
                      {execution.ticket_title}
                    </Link>

                    <p className="mt-1 text-[10px] text-slate-400">
                      {formatDate(execution.created_at)}
                    </p>
                  </div>

                  <span
                    className={`rounded-full px-2.5 py-1 text-[10px] font-medium ${status.classes}`}
                  >
                    {status.label}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </section>

    </div>
  );
}
