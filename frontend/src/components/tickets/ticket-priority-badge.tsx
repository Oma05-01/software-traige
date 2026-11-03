import type { TicketPriority } from "@/lib/types/ticket";

const priorityStyles: Record<TicketPriority, string> = {
  unassessed: "bg-slate-100 text-slate-500",
  low: "bg-sky-50 text-sky-700",
  medium: "bg-amber-50 text-amber-700",
  high: "bg-orange-50 text-orange-700",
  critical: "bg-red-50 text-red-700",
};

const priorityLabels: Record<TicketPriority, string> = {
  unassessed: "Unassessed",
  low: "Low",
  medium: "Medium",
  high: "High",
  critical: "Critical",
};

export function TicketPriorityBadge({
  priority,
}: {
  priority: TicketPriority;
}) {
  return (
    <span
      className={`inline-flex rounded-md px-2 py-1 text-[10px] font-semibold ${priorityStyles[priority]}`}
    >
      {priorityLabels[priority]}
    </span>
  );
}