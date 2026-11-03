import { apiRequest } from "./client";
import type { Ticket } from "@/lib/types/ticket";

interface PaginatedTicketResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Ticket[];
}

export interface TicketSubmissionPayload {
  title: string;
  description: string;
  reporter_name: string;
  reporter_email: string;
  environment?: string;
  steps_to_reproduce?: string;
  expected_behavior?: string;
  actual_behavior?: string;
}

type TicketListResponse = Ticket[] | PaginatedTicketResponse;

export async function getTickets(): Promise<Ticket[]> {
  const response = await apiRequest<TicketListResponse>("/tickets/");

  return Array.isArray(response) ? response : response.results;
}

export async function getTicket(ticketId: string): Promise<Ticket> {
  return apiRequest<Ticket>(
    `/tickets/${encodeURIComponent(ticketId)}/`
  );
}

export async function submitTicket(
  payload: TicketSubmissionPayload
): Promise<Ticket> {
  return apiRequest<Ticket>("/tickets/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}