export interface DashboardStatistics {
  total_tickets: number;
  in_progress_tickets: number;
  awaiting_review_tickets: number;
  completed_tickets: number;
  active_workflows: number;
  failed_workflows: number;
  pending_review_requests: number;
}

export interface DashboardActivityEvent {
  id: string;
  event_type: string;
  source: "system" | "agent" | "human" | "integration";
  created_at: string;
  workflow_id: string;
  ticket_id: string;
  ticket_title: string;
}

export interface DashboardOverview {
  statistics: DashboardStatistics;
  recent_activity: DashboardActivityEvent[];
}