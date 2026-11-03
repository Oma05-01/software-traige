import { TicketListClient } from "@/components/tickets/ticket-list-client";

export default function TicketsPage() {
  return (
    <div className="space-y-8">
      {/* Heading */}
      <section>
        <div className="mb-3 flex items-center gap-2 text-[10px] font-semibold tracking-[0.17em] text-slate-400 uppercase">
          <span>Workspace</span>
          <span>/</span>
          <span className="text-[#587eaf]">Tickets</span>
        </div>

        <h1 className="text-2xl font-semibold tracking-tight text-[#263750] sm:text-3xl">
          Ticket management
        </h1>

        <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">
          Review incoming reports, monitor their processing status
          and inspect the work performed by your triage agents.
        </p>
      </section>

      {/* Live ticket data */}
      <TicketListClient />
    </div>
  );
}