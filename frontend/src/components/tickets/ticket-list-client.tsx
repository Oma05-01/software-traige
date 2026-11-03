"use client";

import { useEffect, useState } from "react";

import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  Inbox,
} from "lucide-react";

import { getTickets } from "@/lib/api/tickets";
import type { Ticket } from "@/lib/types/ticket";
import { TicketTable } from "@/components/tickets/ticket-table";

export function TicketListClient() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let active = true;

    getTickets()
      .then((data) => {
        if (active) {
          setTickets(data);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load tickets."
          );
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [reload]);

  function handleRetry() {
    setLoading(true);
    setError(null);
    setReload((current) => current + 1);
  }

  if (loading) {
    return (
      <div className="flex min-h-48 items-center justify-center">
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-[#365a88]" />
          Loading tickets...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6">
        <p className="text-sm font-semibold text-red-700">
          Unable to load tickets
        </p>

        <p className="mt-2 text-sm text-red-600">{error}</p>

        <button
          type="button"
          onClick={handleRetry}
          className="mt-4 rounded-lg bg-[#294b76] px-4 py-2 text-sm font-medium text-white hover:bg-[#203d61]"
        >
          Try again
        </button>
      </div>
    );
  }

  const summaryCards = [
    {
      title: "Total tickets",
      value: tickets.length,
      icon: Inbox,
      accent: "bg-[#edf3fc] text-[#587eaf]",
    },
    {
      title: "In progress",
      value: tickets.filter(
        (ticket) => ticket.status === "in_progress"
      ).length,
      icon: Clock3,
      accent: "bg-[#fff5e9] text-[#ca9051]",
    },
    {
      title: "Awaiting review",
      value: tickets.filter(
        (ticket) => ticket.status === "awaiting_review"
      ).length,
      icon: AlertCircle,
      accent: "bg-[#f3efff] text-[#8b78bb]",
    },
    {
      title: "Completed",
      value: tickets.filter(
        (ticket) =>
          ticket.status === "completed" ||
          ticket.status === "closed"
      ).length,
      icon: CheckCircle2,
      accent: "bg-[#eaf7f1] text-[#529b7a]",
    },
  ];

  return (
    <div className="space-y-8">
      {/* Summary cards */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {summaryCards.map((card) => {
          const Icon = card.icon;

          return (
            <article
              key={card.title}
              className="rounded-2xl border border-[#e9edf3] bg-white p-5 shadow-[0_2px_8px_rgba(30,50,80,0.025)]"
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs font-medium text-slate-500">
                    {card.title}
                  </p>

                  <p className="mt-4 text-3xl font-semibold text-[#263750]">
                    {card.value}
                  </p>
                </div>

                <div
                  className={`flex h-11 w-11 items-center justify-center rounded-xl ${card.accent}`}
                >
                  <Icon size={20} strokeWidth={1.8} />
                </div>
              </div>
            </article>
          );
        })}
      </section>

      {/* Ticket table */}
      <TicketTable tickets={tickets} />
    </div>
  );
}