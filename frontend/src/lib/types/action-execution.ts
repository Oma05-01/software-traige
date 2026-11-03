export type ActionExecutionStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed";

export interface ActionExecution {
  id: string;
  status: ActionExecutionStatus;

  action_type?: string;
  provider?: string;
  attempt_count?: number;

  provider_response?: Record<string, unknown> | null;

  created_at?: string;
  started_at?: string | null;
  completed_at?: string | null;
}