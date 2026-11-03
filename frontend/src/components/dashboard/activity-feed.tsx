import Link from "next/link";

import {
  Activity,
  Bot,
  Clock3,
  UserRound,
  Workflow,
} from "lucide-react";

import type { DashboardActivityEvent } from "@/lib/types/dashboard";

interface ActivityFeedProps {
  events: DashboardActivityEvent[];
  loading: boolean;
  error: string | null;
}

function formatEvent(value: string) {
  return value
    .replaceAll(".", " ")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatDate(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Time unavailable";
  }

  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function SourceIcon({ source }: { source: string }) {
  if (source === "agent") {
    return <Bot size={16} className="text-[#6687b5]" />;
  }

  if (source === "human") {
    return <UserRound size={16} className="text-violet-600" />;
  }

  if (source === "integration") {
    return <Workflow size={16} className="text-emerald-600" />;
  }

  return <Activity size={16} className="text-slate-500" />;
}

export function ActivityFeed({
  events,
  loading,
  error,
}: ActivityFeedProps) {
  return (
    <section className="rounded-2xl border border-[#e9edf3] bg-white p-5 shadow-[0_2px_8px_rgba(30,50,80,0.025)] sm:p-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-[#273750]">
            Recent activity
          </h2>

          <p className="mt-1 text-xs text-slate-400">
            Events from agents and workflow operations
          </p>
        </div>

        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#f0f4f9]">
          <Activity size={18} className="text-[#6687b5]" />
        </div>
      </div>

      {loading && events.length === 0 ? (
        <div className="flex items-center justify-center gap-2 py-12 text-xs text-slate-400">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-[#365a88]" />
          Loading activity...
        </div>
      ) : error && events.length === 0 ? (
        <p className="py-10 text-center text-xs text-red-500">
          {error}
        </p>
      ) : events.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Clock3 size={21} className="text-slate-400" />

          <h3 className="mt-4 text-sm font-medium text-[#394a62]">
            No recent activity
          </h3>

          <p className="mt-2 max-w-sm text-xs leading-5 text-slate-400">
            New workflow events will appear here as tickets are processed.
          </p>
        </div>
      ) : (
        <div className="mt-5 divide-y divide-[#edf0f5]">
          {events.map((event) => (
            <article
              key={event.id}
              className="flex gap-3 py-4 first:pt-0 last:pb-0"
            >
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#f3f6fa]">
                <SourceIcon source={event.source} />
              </div>

              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold text-[#34465f]">
                  {formatEvent(event.event_type)}
                </p>

                <Link
                  href={`/tickets/${encodeURIComponent(event.ticket_id)}`}
                  className="mt-1 block truncate text-xs text-[#58749b] hover:text-[#294b76]"
                >
                  {event.ticket_title}
                </Link>

                <p className="mt-1 text-[10px] text-slate-400">
                  {formatDate(event.created_at)}
                  {" · "}
                  {formatEvent(event.source)}
                </p>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}