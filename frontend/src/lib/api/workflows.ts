import { apiRequest } from "./client";
import type { WorkflowRun } from "@/lib/types/workflow";

export async function getTicketWorkflow(
  ticketId: string
): Promise<WorkflowRun> {
  return apiRequest<WorkflowRun>(
    `/workflows/tickets/${encodeURIComponent(ticketId)}/`
  );
}