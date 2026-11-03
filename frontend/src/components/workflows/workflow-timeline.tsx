import {
  AlertCircle,
  CheckCircle2,
  Circle,
  Clock3,
  LoaderCircle,
} from "lucide-react";

import type {
  AgentExecution,
  AgentType,
  WorkflowRun,
} from "@/lib/types/workflow";

import type { TicketCategory } from "@/lib/types/ticket";

interface WorkflowTimelineProps {
  workflow: WorkflowRun | null;
  category: TicketCategory;
  error?: string | null;
}

const AGENT_LABELS: Record<AgentType, string> = {
  receptionist: "Receptionist",
  debugger: "Debugger",
  product_manager: "Product Manager",
  support_rep: "Support Representative",
};

function formatLabel(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (char) =>
    char.toUpperCase()
  );
}

function formatDate(value: string | null) {
  if (!value) return "Not available";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Not available";
  }

  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function statusClasses(status: string) {
  switch (status) {
    case "succeeded":
    case "completed":
      return "bg-emerald-50 text-emerald-700";

    case "running":
      return "bg-blue-50 text-blue-700";

    case "queued":
      return "bg-amber-50 text-amber-700";

    case "awaiting_review":
      return "bg-violet-50 text-violet-700";

    case "failed":
      return "bg-red-50 text-red-700";

    default:
      return "bg-slate-100 text-slate-600";
  }
}

function executionIcon(status: string) {
  switch (status) {
    case "succeeded":
      return <CheckCircle2 size={17} className="text-emerald-600" />;

    case "running":
      return (
        <LoaderCircle
          size={17}
          className="animate-spin text-blue-600"
        />
      );

    case "queued":
      return <Clock3 size={17} className="text-amber-600" />;

    case "failed":
      return <AlertCircle size={17} className="text-red-600" />;

    default:
      return <Circle size={17} className="text-slate-300" />;
  }
}

function getAgentSequence(
  category: TicketCategory
): AgentType[] {
  if (category === "bug") {
    return ["receptionist", "debugger", "support_rep"];
  }

  if (category === "feature") {
    return ["receptionist", "product_manager", "support_rep"];
  }

  return ["receptionist"];
}

function latestExecution(
  executions: AgentExecution[],
  agentType: AgentType
) {
  return executions
    .filter((execution) => execution.agent_type === agentType)
    .sort((a, b) => {
      if (a.attempt !== b.attempt) {
        return b.attempt - a.attempt;
      }

      return (
        new Date(b.created_at).getTime() -
        new Date(a.created_at).getTime()
      );
    })[0] ?? null;
}

function getString(
  payload: Record<string, unknown>,
  key: string
): string | null {
  const value = payload[key];

  return typeof value === "string" && value.trim()
    ? value
    : null;
}

function getStringArray(
  payload: Record<string, unknown>,
  key: string
): string[] {
  const value = payload[key];

  if (!Array.isArray(value)) return [];

  return value.filter(
    (item): item is string =>
      typeof item === "string" && item.trim().length > 0
  );
}

function ExecutionFindings({
  execution,
}: {
  execution: AgentExecution;
}) {
  const payload = execution.output_payload;

  const summary =
    getString(payload, "summary") ??
    getString(payload, "investigation_summary") ??
    getString(payload, "problem_statement") ??
    getString(payload, "draft_response");

  const questions =
    getStringArray(payload, "unresolved_questions").length > 0
      ? getStringArray(payload, "unresolved_questions")
      : getStringArray(payload, "follow_up_questions");

  const evidence = Array.isArray(payload.documented_evidence)
    ? payload.documented_evidence
    : [];

  const category = getString(payload, "category");
  const priority = getString(payload, "priority");

  const rootCause = payload.root_cause;
  const rootCauseStatus =
    rootCause && typeof rootCause === "object"
      ? getString(
          rootCause as Record<string, unknown>,
          "status"
        )
      : null;

  const assessment = getString(
    payload,
    "requested_capability"
  );

  return (
    <div className="mt-4 space-y-3 border-t border-[#edf0f5] pt-4">
      {category && (
        <p className="text-xs text-slate-600">
          <span className="font-semibold">Classification:</span>{" "}
          {formatLabel(category)}
          {priority && ` · ${formatLabel(priority)} priority`}
        </p>
      )}

      {summary && (
        <div>
          <p className="text-[10px] font-semibold tracking-wide text-slate-400 uppercase">
            Agent findings
          </p>

          <p className="mt-1 whitespace-pre-wrap text-xs leading-6 text-slate-600">
            {summary}
          </p>
        </div>
      )}

      {assessment && (
        <div>
          <p className="text-[10px] font-semibold tracking-wide text-slate-400 uppercase">
            Requested capability
          </p>
          <p className="mt-1 text-xs text-slate-600">
            {assessment}
          </p>
        </div>
      )}

      {execution.agent_type === "debugger" && (
        <div className="flex flex-wrap gap-2">
          <span className="rounded-lg bg-slate-100 px-2.5 py-1.5 text-[10px] text-slate-600">
            {evidence.length} evidence sections
          </span>

          {rootCauseStatus && (
            <span className="rounded-lg bg-amber-50 px-2.5 py-1.5 text-[10px] text-amber-700">
              Root cause: {formatLabel(rootCauseStatus)}
            </span>
          )}
        </div>
      )}

      {questions.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold tracking-wide text-slate-400 uppercase">
            Outstanding questions
          </p>

          <ul className="mt-2 space-y-1.5">
            {questions.map((question, index) => (
              <li
                key={`${index}-${question}`}
                className="text-xs leading-5 text-slate-600"
              >
                • {question}
              </li>
            ))}
          </ul>
        </div>
      )}

      <details className="group">
        <summary className="cursor-pointer text-xs font-medium text-[#58749b] hover:text-[#294b76]">
          View structured findings
        </summary>

        <pre className="mt-3 max-h-96 overflow-auto rounded-xl bg-[#f7f9fc] p-3 text-[10px] leading-5 text-slate-600">
          {JSON.stringify(payload, null, 2)}
        </pre>
      </details>
    </div>
  );
}

export function WorkflowTimeline({
  workflow,
  category,
  error,
}: WorkflowTimelineProps) {
  if (!workflow) {
    return (
      <section className="rounded-2xl border border-[#e9edf3] bg-white p-5 sm:p-6">
        <h2 className="text-sm font-semibold text-[#263750]">
          Agent workflow
        </h2>

        <p className="mt-3 text-xs leading-6 text-slate-500">
          {error
            ? "Workflow information is currently unavailable."
            : "No workflow has been created for this ticket yet."}
        </p>
      </section>
    );
  }

  const sequence = getAgentSequence(category);

  return (
    <section className="rounded-2xl border border-[#e9edf3] bg-white p-5 shadow-[0_2px_8px_rgba(30,50,80,0.025)] sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-[#263750]">
            Agent workflow
          </h2>

          <p className="mt-1 text-xs text-slate-400">
            Processing history and agent findings
          </p>
        </div>

        <span
          className={`rounded-full px-3 py-1.5 text-[10px] font-semibold ${statusClasses(workflow.status)}`}
        >
          {formatLabel(workflow.status)}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="rounded-xl bg-[#f8f9fb] p-3">
          <p className="text-[10px] font-medium uppercase text-slate-400">
            Current stage
          </p>
          <p className="mt-1 text-sm font-semibold text-[#34465f]">
            {formatLabel(workflow.current_stage)}
          </p>
        </div>

        <div className="rounded-xl bg-[#f8f9fb] p-3">
          <p className="text-[10px] font-medium uppercase text-slate-400">
            Started
          </p>
          <p className="mt-1 text-sm font-semibold text-[#34465f]">
            {formatDate(workflow.started_at)}
          </p>
        </div>
      </div>

      {workflow.status === "failed" && (
        <div className="mt-4 rounded-xl border border-red-100 bg-red-50 p-3">
          <p className="text-xs font-semibold text-red-700">
            Workflow failed
          </p>
          <p className="mt-1 text-xs leading-5 text-red-600">
            {workflow.error_message || workflow.error_code || "An unexpected workflow error occurred."}
          </p>
        </div>
      )}

      <div className="mt-6 space-y-4">
        {sequence.map((agentType, index) => {
          const execution = latestExecution(
            workflow.agent_executions,
            agentType
          );

          const isCurrentStage =
            workflow.current_stage === agentType;

          const status = execution?.status ??
            (isCurrentStage && workflow.status === "running"
              ? "queued"
              : "not_started");

          return (
            <article
              key={agentType}
              className="rounded-xl border border-[#edf0f5] p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  <div className="mt-0.5">
                    {executionIcon(status)}
                  </div>

                  <div>
                    <p className="text-sm font-semibold text-[#34465f]">
                      {String(index + 1).padStart(2, "0")} ·{" "}
                      {AGENT_LABELS[agentType]}
                    </p>

                    <p className="mt-1 text-[10px] text-slate-400">
                      {execution
                        ? `Attempt ${execution.attempt}`
                        : "Awaiting execution"}
                    </p>
                  </div>
                </div>

                <span
                  className={`rounded-full px-2.5 py-1 text-[10px] font-medium ${statusClasses(status)}`}
                >
                  {formatLabel(status)}
                </span>
              </div>

              {execution && (
                <>
                  <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[10px] text-slate-400">
                    <span>
                      Started: {formatDate(execution.started_at)}
                    </span>

                    <span>
                      Finished: {formatDate(execution.finished_at)}
                    </span>
                  </div>

                  {execution.error_message && (
                    <p className="mt-3 rounded-lg bg-red-50 p-3 text-xs text-red-600">
                      {execution.error_message}
                    </p>
                  )}

                  {execution.status === "succeeded" && (
                    <ExecutionFindings execution={execution} />
                  )}
                </>
              )}
            </article>
          );
        })}
      </div>

      {workflow.current_stage === "human_review" && (
        <div className="mt-5 rounded-xl border border-violet-100 bg-violet-50 p-4">
          <p className="text-sm font-semibold text-violet-800">
            Awaiting human review
          </p>
          <p className="mt-1 text-xs leading-5 text-violet-700">
            The automated agents have handed their proposal to the review process.
          </p>
        </div>
      )}

      <div className="mt-7 border-t border-[#edf0f5] pt-5">
        <h3 className="text-xs font-semibold text-[#34465f]">
          Workflow events
        </h3>

        {workflow.events.length === 0 ? (
          <p className="mt-3 text-xs text-slate-400">
            No workflow events have been recorded.
          </p>
        ) : (
          <div className="mt-4 space-y-4">
            {[...workflow.events].reverse().map((event) => (
              <div
                key={event.id}
                className="flex gap-3"
              >
                <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-[#7894b8]" />

                <div className="min-w-0">
                  <p className="break-words text-xs font-medium text-[#34465f]">
                    {formatLabel(event.event_type)}
                  </p>

                  <p className="mt-1 text-[10px] text-slate-400">
                    {formatLabel(event.source)} · {formatDate(event.created_at)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}