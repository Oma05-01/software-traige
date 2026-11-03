export type TicketCategory =
  | "unclassified"
  | "bug"
  | "feature"
  | "spam"
  | "other";

export type TicketPriority =
  | "unassessed"
  | "low"
  | "medium"
  | "high"
  | "critical";

export type TicketStatus =
  | "submitted"
  | "in_progress"
  | "awaiting_review"
  | "completed"
  | "closed";

export interface Ticket {
  id: string;
  title: string;
  description: string;
  reporter_name: string;
  reporter_email: string;
  environment: string;
  steps_to_reproduce: string;
  expected_behavior: string;
  actual_behavior: string;

  category: TicketCategory;
  priority: TicketPriority;
  status: TicketStatus;

  created_at: string;
  updated_at: string;
  workflow_id?: string | null;
}