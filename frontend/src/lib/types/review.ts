export type ReviewStatus =
  | "pending"
  | "changes_requested"
  | "approved"
  | "rejected";

export type ReviewActionType =
  | "send_support_response"
  | "create_github_issue";

export type ReviewRelation =
  | string
  | number
  | {
      id?: string | number;
      username?: string;
    }
  | null;

export interface ReviewRequest {
  id: string;
  workflow_run?: ReviewRelation;
  workflow_run_id?: string | null;
  agent_execution?: ReviewRelation;
  agent_execution_id?: string | null;

  action_type: ReviewActionType;
  status: ReviewStatus;
  proposed_payload: Record<string, unknown>;

  revision_number: number;
  reviewed_by?: ReviewRelation;
  reviewed_at: string | null;
  decision_note: string | null;

  created_at: string;
  updated_at?: string;
}

export interface PaginatedReviewResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: ReviewRequest[];
}