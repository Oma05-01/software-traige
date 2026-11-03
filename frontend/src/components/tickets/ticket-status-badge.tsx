import type { TicketStatus } from "@/lib/types/ticket";

const statusStyles: Record<TicketStatus, string> = {
  submitted: "bg-slate-100 text-slate-600",
  in_progress: "bg-blue-50 text-blue-700",
  awaiting_review: "bg-amber-50 text-amber-700",
  completed: "bg-emerald-50 text-emerald-700",
  closed: "bg-gray-100 text-gray-600",
};

const statusLabels: Record<TicketStatus, string> = {
  submitted: "Submitted",
  in_progress: "In progress",
  awaiting_review: "Awaiting review",
  completed: "Completed",
  closed: "Closed",
};

export function TicketStatusBadge({
  status,
}: {
  status: TicketStatus;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-[10px] font-semibold ${statusStyles[status]}`}
    >
      <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-current" />
      {statusLabels[status]}
    </span>
  );
}