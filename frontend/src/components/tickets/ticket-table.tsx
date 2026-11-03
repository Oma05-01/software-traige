
"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Search, SlidersHorizontal, Ticket as TicketIcon } from "lucide-react";

import type {
  Ticket,
  TicketCategory,
  TicketPriority,
  TicketStatus,
} from "@/lib/types/ticket";

import { TicketStatusBadge } from "./ticket-status-badge";
import { TicketPriorityBadge } from "./ticket-priority-badge";

type StatusFilter = TicketStatus | "all";
type CategoryFilter = TicketCategory | "all";
type PriorityFilter = TicketPriority | "all";

interface TicketTableProps {
  tickets: Ticket[];
}

function formatDate(date: string) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(date));
}

function formatCategory(category: TicketCategory) {
  return category.charAt(0).toUpperCase() + category.slice(1);
}

const selectStyles =
  "h-10 rounded-lg border border-[#e6eaf0] bg-white px-3 text-xs text-slate-600 outline-none transition-colors focus:border-[#829cbe]";

export function TicketTable({ tickets }: TicketTableProps) {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [category, setCategory] = useState<CategoryFilter>("all");
  const [priority, setPriority] = useState<PriorityFilter>("all");

  const filteredTickets = useMemo(() => {
    const query = search.trim().toLowerCase();

    return tickets.filter((ticket) => {
      const matchesSearch =
        !query ||
        ticket.title.toLowerCase().includes(query) ||
        ticket.id.toLowerCase().includes(query) ||
        ticket.reporter_name.toLowerCase().includes(query);

      const matchesStatus =
        status === "all" || ticket.status === status;

      const matchesCategory =
        category === "all" || ticket.category === category;

      const matchesPriority =
        priority === "all" || ticket.priority === priority;

      return (
        matchesSearch &&
        matchesStatus &&
        matchesCategory &&
        matchesPriority
      );
    });
  }, [tickets, search, status, category, priority]);

  const hasActiveFilters =
    search.trim() !== "" ||
    status !== "all" ||
    category !== "all" ||
    priority !== "all";

  function clearFilters() {
    setSearch("");
    setStatus("all");
    setCategory("all");
    setPriority("all");
  }

  return (
    <section className="overflow-hidden rounded-2xl border border-[#e9edf3] bg-white shadow-[0_2px_8px_rgba(30,50,80,0.025)]">
      {/* Table heading */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#edf0f5] px-5 py-5 sm:px-6">
        <div>
          <h2 className="text-sm font-semibold text-[#293b54]">
            Ticket inbox
          </h2>

          <p className="mt-1 text-xs text-slate-400">
            {filteredTickets.length} of {tickets.length} tickets
          </p>
        </div>

        <div className="flex items-center gap-2 text-[11px] text-slate-400">
          <SlidersHorizontal size={14} />
          <span>Filter and search</span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 border-b border-[#edf0f5] p-4 sm:px-5 lg:flex-row lg:items-center">
        <div className="relative min-w-0 flex-1">
          <Search
            size={16}
            className="absolute top-1/2 left-3 -translate-y-1/2 text-slate-400"
          />

          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search by ticket title, ID or reporter..."
            className="h-10 w-full rounded-lg border border-[#e6eaf0] bg-white pr-3 pl-9 text-xs text-slate-700 outline-none placeholder:text-slate-400 focus:border-[#829cbe]"
          />
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:flex">
          <select
            aria-label="Filter by status"
            value={status}
            onChange={(event) =>
              setStatus(event.target.value as StatusFilter)
            }
            className={selectStyles}
          >
            <option value="all">All statuses</option>
            <option value="submitted">Submitted</option>
            <option value="in_progress">In progress</option>
            <option value="awaiting_review">Awaiting review</option>
            <option value="completed">Completed</option>
            <option value="closed">Closed</option>
          </select>

          <select
            aria-label="Filter by category"
            value={category}
            onChange={(event) =>
              setCategory(event.target.value as CategoryFilter)
            }
            className={selectStyles}
          >
            <option value="all">All categories</option>
            <option value="bug">Bug</option>
            <option value="feature">Feature</option>
            <option value="spam">Spam</option>
            <option value="other">Other</option>
            <option value="unclassified">Unclassified</option>
          </select>

          <select
            aria-label="Filter by priority"
            value={priority}
            onChange={(event) =>
              setPriority(event.target.value as PriorityFilter)
            }
            className={selectStyles}
          >
            <option value="all">All priorities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
            <option value="unassessed">Unassessed</option>
          </select>

          <button
            type="button"
            onClick={clearFilters}
            disabled={!hasActiveFilters}
            className="h-10 rounded-lg px-3 text-xs font-medium text-[#56769e] transition-colors hover:bg-[#f1f5fa] disabled:cursor-not-allowed disabled:opacity-40"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[850px] text-left">
          <thead>
            <tr className="border-b border-[#edf0f5] bg-[#fafbfd]">
              {[
                "Ticket",
                "Reporter",
                "Category",
                "Priority",
                "Status",
                "Submitted",
                "",
              ].map((heading) => (
                <th
                  key={heading}
                  className="px-5 py-3 text-[10px] font-semibold tracking-wider text-slate-400 uppercase"
                >
                  {heading}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {filteredTickets.map((ticket) => (
              <tr
                key={ticket.id}
                className="border-b border-[#f0f2f5] transition-colors last:border-0 hover:bg-[#fafbfd]"
              >
                <td className="max-w-[260px] px-5 py-4">
                  <Link
                    href={`/tickets/${encodeURIComponent(ticket.id)}`}
                    className="block truncate text-xs font-semibold text-[#2c405c] hover:text-[#6687b5]"
                  >
                    {ticket.title}
                  </Link>

                  <p className="mt-1 text-[10px] text-slate-400">
                    {ticket.id}
                  </p>
                </td>

                <td className="px-5 py-4">
                  <p className="text-xs font-medium text-slate-600">
                    {ticket.reporter_name}
                  </p>

                  <p className="mt-1 text-[10px] text-slate-400">
                    {ticket.reporter_email}
                  </p>
                </td>

                <td className="px-5 py-4 text-xs text-slate-500">
                  {formatCategory(ticket.category)}
                </td>

                <td className="px-5 py-4">
                  <TicketPriorityBadge priority={ticket.priority} />
                </td>

                <td className="px-5 py-4">
                  <TicketStatusBadge status={ticket.status} />
                </td>

                <td className="whitespace-nowrap px-5 py-4 text-[11px] text-slate-500">
                  {formatDate(ticket.created_at)}
                </td>

                <td className="px-5 py-4">
                  <Link
                    href={`/tickets/${encodeURIComponent(ticket.id)}`}
                    className="text-[11px] font-semibold text-[#6687b5] hover:text-[#294b76]"
                  >
                    View
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {filteredTickets.length === 0 && (
          <div className="flex flex-col items-center px-5 py-16 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#f1f4f8]">
              <TicketIcon size={21} className="text-slate-400" />
            </div>

            <h3 className="mt-4 text-sm font-medium text-[#394a62]">
              No tickets found
            </h3>

            <p className="mt-2 text-xs text-slate-400">
              Try changing your search or filter criteria.
            </p>
          </div>
        )}
      </div>

      <div className="border-t border-[#edf0f5] px-5 py-3">
        <p className="text-[10px] text-slate-400">
          Displaying preview records. Live ticket data is not connected yet.
        </p>
      </div>
    </section>
  );
}
