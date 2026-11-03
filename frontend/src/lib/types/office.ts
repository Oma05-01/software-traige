import type { AgentType } from "@/lib/types/workflow";

export type OfficeAgentStatus =
  | "idle"
  | "queued"
  | "working"
  | "completed"
  | "failed";

export interface OfficeExecution {
  id: string;
  agent_type: AgentType;
  status:
    | "queued"
    | "running"
    | "succeeded"
    | "failed"
    | "skipped";
  attempt: number;

  ticket_id: string;
  ticket_title: string;

  workflow_id: string;
  workflow_status: string;
  workflow_stage: string;

  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;

  error_code: string;
}

export interface OfficeAgent {
  agent_type: AgentType;
  status: OfficeAgentStatus;
  active_count: number;

  current_execution: OfficeExecution | null;
  latest_execution: OfficeExecution | null;
}

export interface OfficeActivity {
  agents: OfficeAgent[];
  recent_executions: OfficeExecution[];
  updated_at: string;
}