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

export type ClassificationReviewStatus = "pending" | "resolved";

export type ClassificationDecision = "confirmed" | "corrected" | "";

export type ClassificationCategory =
  | "unclassified"
  | "bug"
  | "feature"
  | "spam"
  | "other";

export type ClassificationPriority =
  | "unassessed"
  | "low"
  | "medium"
  | "high"
  | "critical";

export interface ClassificationReview {
  id: string;

  workflow_run_id: string;
  agent_execution_id: string;

  ticket_id: string;
  ticket_title: string;
  ticket_description: string;
  ticket_environment: string;
  ticket_steps_to_reproduce: string;
  ticket_expected_behavior: string;
  ticket_actual_behavior: string;

  proposed_category: Exclude<
    ClassificationCategory,
    "unclassified"
  >;

  proposed_priority: ClassificationPriority;
  classification_confidence: string;

  status: ClassificationReviewStatus;
  decision: ClassificationDecision;

  resolved_category:
    | Exclude<ClassificationCategory, "unclassified">
    | "";

  resolved_priority:
    | Exclude<ClassificationPriority, "unassessed">
    | "";

  reviewed_by: string | number | null;
  reviewed_by_username: string | null;
  reviewed_at: string | null;

  decision_note: string;

  created_at: string;
  updated_at: string;
}

export interface PaginatedClassificationReviewResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: ClassificationReview[];
}

export interface ResolveClassificationPayload {
  resolved_category: "bug" | "feature";
  resolved_priority: "low" | "medium" | "high" | "critical";
  decision_note?: string;
}
