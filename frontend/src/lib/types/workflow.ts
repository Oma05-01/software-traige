export type WorkflowStatus =
  | "queued"
  | "running"
  | "awaiting_review"
  | "completed"
  | "failed";

export type WorkflowStage =
  | "receptionist"
  | "debugger"
  | "product_manager"
  | "support_rep"
  | "human_review";

export type AgentType =
  | "receptionist"
  | "debugger"
  | "product_manager"
  | "support_rep";

export type AgentExecutionStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "skipped";

export type WorkflowEventSource =
  | "system"
  | "agent"
  | "human"
  | "integration";

export interface AgentExecution {
  id: string;
  agent_type: AgentType;
  status: AgentExecutionStatus;
  attempt: number;
  output_payload: Record<string, unknown>;
  started_at: string | null;
  finished_at: string | null;
  error_code: string;
  error_message: string;
  created_at: string;
  updated_at: string;
}

export interface WorkflowEvent {
  id: string;
  event_type: string;
  source: WorkflowEventSource;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface WorkflowRun {
  id: string;
  ticket: string;
  status: WorkflowStatus;
  current_stage: WorkflowStage;
  workflow_version: string;
  started_at: string | null;
  finished_at: string | null;
  error_code: string;
  error_message: string;
  created_at: string;
  updated_at: string;
  agent_executions: AgentExecution[];
  events: WorkflowEvent[];
}