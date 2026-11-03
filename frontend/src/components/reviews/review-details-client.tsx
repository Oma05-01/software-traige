"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowLeft,
  CalendarDays,
  Clock3,
  FileText,
  RefreshCw,
} from "lucide-react";

import {
  executeApprovedReview,
  getActionExecution,
} from "@/lib/api/integrations";

import type {
  ActionExecution,
} from "@/lib/types/action-execution";

import {
  getReview,
  updateReviewProposal,
  approveReview,
  rejectReview,
  requestReviewChanges,
  reviseReview,
} from "@/lib/api/reviews";

import type {
  ReviewRequest,
  ReviewRelation,
} from "@/lib/types/review";

interface ReviewDetailsClientProps {
  reviewId: string;
}

function relationId(value: ReviewRelation): string {
  if (value === null || value === undefined) return "Not available";

  if (typeof value === "object") {
    return value.id === undefined ? "Not available" : String(value.id);
  }

  return String(value);
}

function formatLabel(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatDate(value: string | null): string {
  if (!value) return "Not available";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "Not available";

  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function statusStyle(status: ReviewRequest["status"]): string {
  switch (status) {
    case "pending":
      return "bg-amber-50 text-amber-700";

    case "changes_requested":
      return "bg-violet-50 text-violet-700";

    case "approved":
      return "bg-emerald-50 text-emerald-700";

    case "rejected":
      return "bg-red-50 text-red-700";
  }
}


export function ReviewDetailsClient({
  reviewId,
}: ReviewDetailsClientProps) {
  const [review, setReview] = useState<ReviewRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [proposalText, setProposalText] = useState("");
    const [decisionNote, setDecisionNote] = useState("");
    const [actionLoading, setActionLoading] = useState(false);
    const [actionError, setActionError] = useState<string | null>(null);
    const [actionMessage, setActionMessage] = useState<string | null>(null);
const [execution, setExecution] = useState<ActionExecution | null>(null);
const [executionLoading, setExecutionLoading] = useState(false);
const [executionError, setExecutionError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    getReview(reviewId)
      .then((data) => {
        if (active) {
            setReview(data);
            setProposalText(
            JSON.stringify(data.proposed_payload, null, 2)
            );
            setError(null);
        }
        })
      .catch((err: unknown) => {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load this review."
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [reviewId, reload]);

  function handleRetry() {
    setLoading(true);
    setError(null);
    setReload((current) => current + 1);
  }

  function parseProposal(): Record<string, unknown> {
  let parsed: unknown;

  try {
    parsed = JSON.parse(proposalText);
  } catch {
    throw new Error("The proposal contains invalid JSON.");
  }

  if (
    parsed === null ||
    typeof parsed !== "object" ||
    Array.isArray(parsed)
  ) {
    throw new Error("The proposal must be a JSON object.");
  }

  return parsed as Record<string, unknown>;
}

async function handleSaveProposal() {
  if (!review || review.status !== "pending") return;

  setActionLoading(true);
  setActionError(null);
  setActionMessage(null);

  try {
    const payload = parseProposal();

    const updated = await updateReviewProposal(
      review.id,
      payload
    );

    setReview(updated);
    setProposalText(
      JSON.stringify(updated.proposed_payload, null, 2)
    );

    setActionMessage("Proposal changes saved successfully.");
  } catch (err) {
    setActionError(
      err instanceof Error
        ? err.message
        : "Unable to save the proposal."
    );
  } finally {
    setActionLoading(false);
  }
}

async function handleDecision(
  action: "approve" | "reject" | "request_changes"
) {
  if (!review || review.status !== "pending") return;

  const note = decisionNote.trim();

  if (
    action === "request_changes" &&
    !note
  ) {
    setActionError(
      "Please explain what needs to be changed."
    );
    return;
  }

  const originalProposal = JSON.stringify(
    review.proposed_payload,
    null,
    2
  );

  if (proposalText !== originalProposal) {
    setActionError(
      "You have unsaved proposal changes. Save them before making a decision."
    );
    return;
  }

  setActionLoading(true);
  setActionError(null);
  setActionMessage(null);

  try {
    let updated: ReviewRequest;

    switch (action) {
      case "approve":
        updated = await approveReview(review.id, note);
        break;

      case "reject":
        updated = await rejectReview(review.id, note);
        break;

      case "request_changes":
        updated = await requestReviewChanges(
          review.id,
          note
        );
        break;
    }

    setReview(updated);
    setProposalText(
      JSON.stringify(updated.proposed_payload, null, 2)
    );
    setDecisionNote("");

    setActionMessage(
      action === "approve"
        ? "Proposal approved. The action has not yet been executed."
        : action === "reject"
          ? "Proposal rejected."
          : "Changes requested. The proposal can now be revised."
    );
  } catch (err) {
    setActionError(
      err instanceof Error
        ? err.message
        : "Unable to process the review decision."
    );
  } finally {
    setActionLoading(false);
  }
}

async function handleSubmitRevision() {
  if (!review || review.status !== "changes_requested") return;

  setActionLoading(true);
  setActionError(null);
  setActionMessage(null);

  try {
    const payload = parseProposal();

    const updated = await reviseReview(
      review.id,
      payload
    );

    setReview(updated);
    setProposalText(
      JSON.stringify(updated.proposed_payload, null, 2)
    );
    setDecisionNote("");

    setActionMessage(
      "Revision submitted. The review is pending again."
    );
  } catch (err) {
    setActionError(
      err instanceof Error
        ? err.message
        : "Unable to submit the revision."
    );
  } finally {
    setActionLoading(false);
  }
}

async function handleExecuteApprovedAction() {
  if (!review || review.status !== "approved") {
    return;
  }

  // The current backend execution service supports support responses.
  if (review.action_type !== "send_support_response") {
    setExecutionError(
      "Execution is not currently supported for this action type."
    );
    return;
  }

  setExecutionLoading(true);
  setExecutionError(null);

  try {
    const result = await executeApprovedReview(review.id);

    setExecution(result);
  } catch (err) {
    setExecutionError(
      err instanceof Error
        ? err.message
        : "Unable to queue the approved action."
    );
  } finally {
    setExecutionLoading(false);
  }
}

async function handleRefreshExecution() {
  if (!execution) return;

  setExecutionLoading(true);
  setExecutionError(null);

  try {
    const result = await getActionExecution(execution.id);

    setExecution(result);
  } catch (err) {
    setExecutionError(
      err instanceof Error
        ? err.message
        : "Unable to retrieve execution status."
    );
  } finally {
    setExecutionLoading(false);
  }
}

  if (loading) {
    return (
      <div className="flex min-h-64 items-center justify-center">
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-[#365a88]" />
          Loading review...
        </div>
      </div>
    );
  }

  if (error || !review) {
    return (
      <div className="space-y-5">
        <Link
          href="/reviews"
          className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-[#294b76]"
        >
          <ArrowLeft size={16} />
          Back to reviews
        </Link>

        <div className="rounded-2xl border border-red-200 bg-red-50 p-6">
          <div className="flex items-center gap-2 text-red-700">
            <AlertCircle size={18} />

            <p className="text-sm font-semibold">
              Unable to load review
            </p>
          </div>

          <p className="mt-2 text-sm text-red-600">
            {error || "The requested review could not be found."}
          </p>

          <button
            type="button"
            onClick={handleRetry}
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-[#294b76] px-4 py-2 text-sm font-medium text-white hover:bg-[#203d61]"
          >
            <RefreshCw size={14} />
            Try again
          </button>
        </div>
      </div>
    );
  }

  const workflowId = relationId(
    review.workflow_run_id ?? review.workflow_run ?? null
  );

  const agentExecutionId = relationId(
    review.agent_execution_id ?? review.agent_execution ?? null
  );

  return (
    <div className="space-y-7">
      {/* Back navigation */}
      <Link
        href="/reviews"
        className="inline-flex items-center gap-2 text-sm text-slate-500 transition-colors hover:text-[#294b76]"
      >
        <ArrowLeft size={16} />
        Back to reviews
      </Link>

      {/* Review heading */}
      <section>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span
            className={`rounded-full px-3 py-1 text-[11px] font-semibold ${statusStyle(review.status)}`}
          >
            {formatLabel(review.status)}
          </span>

          <span className="text-xs text-slate-400">
            Revision {review.revision_number}
          </span>
        </div>

        <h1 className="text-2xl font-semibold tracking-tight text-[#263750] sm:text-3xl">
          {formatLabel(review.action_type)}
        </h1>

        <p className="mt-2 break-all text-xs text-slate-400">
          Review ID: {review.id}
        </p>
      </section>

      {/* Review metadata */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <article className="rounded-xl border border-[#e9edf3] bg-white p-4">
          <div className="flex items-center gap-2 text-slate-400">
            <CalendarDays size={16} />

            <span className="text-[11px] font-medium uppercase">
              Submitted
            </span>
          </div>

          <p className="mt-3 text-sm font-medium text-[#34465f]">
            {formatDate(review.created_at)}
          </p>
        </article>

        <article className="rounded-xl border border-[#e9edf3] bg-white p-4">
          <div className="flex items-center gap-2 text-slate-400">
            <Clock3 size={16} />

            <span className="text-[11px] font-medium uppercase">
              Last reviewed
            </span>
          </div>

          <p className="mt-3 text-sm font-medium text-[#34465f]">
            {formatDate(review.reviewed_at)}
          </p>
        </article>

        <article className="rounded-xl border border-[#e9edf3] bg-white p-4">
          <div className="flex items-center gap-2 text-slate-400">
            <FileText size={16} />

            <span className="text-[11px] font-medium uppercase">
              Revision
            </span>
          </div>

          <p className="mt-3 text-sm font-medium text-[#34465f]">
            Version {review.revision_number}
          </p>
        </article>
      </section>

      {/* Proposed action editor */}
        <section className="rounded-2xl border border-[#e9edf3] bg-white p-5 sm:p-6">
        <div className="mb-5">
            <h2 className="text-sm font-semibold text-[#263750]">
            Proposed action
            </h2>

            <p className="mt-1 text-xs leading-5 text-slate-500">
            Inspect the agent&apos;s proposal. You can edit the JSON before
            saving or submitting a revision.
            </p>
        </div>

        <textarea
            value={proposalText}
            onChange={(event) => setProposalText(event.target.value)}
            readOnly={
            review.status !== "pending" &&
            review.status !== "changes_requested"
            }
            spellCheck={false}
            rows={16}
            className="w-full resize-y rounded-xl border border-[#e2e8f0] bg-[#f8fafc] p-4 font-mono text-xs leading-6 text-[#34465f] outline-none focus:border-[#91a9c7] read-only:cursor-default"
            aria-label="Proposed action JSON"
        />

        <p className="mt-2 text-[11px] text-slate-400">
            {review.status === "pending"
            ? "Editing is available while this proposal is pending."
            : review.status === "changes_requested"
                ? "Update the proposal and submit your revision."
                : "This proposal is read-only because a final decision has been recorded."}
        </p>

        {review.status === "pending" && (
            <div className="mt-4 flex justify-end">
            <button
                type="button"
                onClick={handleSaveProposal}
                disabled={
                actionLoading ||
                proposalText ===
                    JSON.stringify(review.proposed_payload, null, 2)
                }
                className="rounded-lg border border-[#dce3ec] bg-white px-4 py-2.5 text-xs font-semibold text-[#34465f] transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
                {actionLoading ? "Saving..." : "Save proposal changes"}
            </button>
            </div>
        )}

        {review.status === "changes_requested" && (
            <div className="mt-4 flex justify-end">
            <button
                type="button"
                onClick={handleSubmitRevision}
                disabled={actionLoading}
                className="rounded-lg bg-[#294b76] px-5 py-2.5 text-xs font-semibold text-white transition-colors hover:bg-[#203d61] disabled:cursor-not-allowed disabled:opacity-50"
            >
                {actionLoading ? "Submitting..." : "Submit revised proposal"}
            </button>
            </div>
        )}
        </section>

      {/* Workflow references */}
      <section className="rounded-2xl border border-[#e9edf3] bg-white p-5 sm:p-6">
        <h2 className="text-sm font-semibold text-[#263750]">
          Workflow references
        </h2>

        <div className="mt-5 grid gap-5 sm:grid-cols-2">
          <div>
            <p className="text-[11px] font-medium tracking-wide text-slate-400 uppercase">
              Workflow ID
            </p>

            <p className="mt-2 break-all text-xs leading-6 text-[#34465f]">
              {workflowId}
            </p>
          </div>

          <div>
            <p className="text-[11px] font-medium tracking-wide text-slate-400 uppercase">
              Agent execution ID
            </p>

            <p className="mt-2 break-all text-xs leading-6 text-[#34465f]">
              {agentExecutionId}
            </p>
          </div>
        </div>
      </section>

      {/* Previous decision */}
      {review.decision_note && (
        <section className="rounded-2xl border border-[#e9edf3] bg-white p-5 sm:p-6">
          <h2 className="text-sm font-semibold text-[#263750]">
            Previous decision note
          </h2>

          <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-600">
            {review.decision_note}
          </p>
        </section>
      )}

      {/* Decision controls will be connected to the review API next. */}
      {/* Review decisions */}
<section className="rounded-2xl border border-[#e9edf3] bg-white p-5 sm:p-6">
  <h2 className="text-sm font-semibold text-[#263750]">
    Review decision
  </h2>

  <p className="mt-1 text-xs leading-6 text-slate-500">
    Record your decision on this specific proposed action.
  </p>

  {actionError && (
    <div className="mt-5 rounded-lg border border-red-200 bg-red-50 p-3">
      <p className="text-xs leading-5 text-red-700">
        {actionError}
      </p>
    </div>
  )}

  {actionMessage && (
    <div className="mt-5 rounded-lg border border-emerald-200 bg-emerald-50 p-3">
      <p className="text-xs leading-5 text-emerald-700">
        {actionMessage}
      </p>
    </div>
  )}

  {review.status === "pending" && (
    <div className="mt-5 space-y-5">
      <div>
        <label
          htmlFor="decision-note"
          className="text-xs font-medium text-[#34465f]"
        >
          Decision note
        </label>

        <textarea
          id="decision-note"
          value={decisionNote}
          onChange={(event) =>
            setDecisionNote(event.target.value)
          }
          rows={3}
          maxLength={2000}
          placeholder="Explain your decision or describe the changes required..."
          className="mt-2 w-full resize-y rounded-lg border border-[#e2e8f0] bg-[#f8fafc] p-3 text-sm text-[#34465f] outline-none placeholder:text-slate-400 focus:border-[#91a9c7]"
        />

        <p className="mt-1 text-[10px] text-slate-400">
          Required when requesting changes. Optional for approval
          and rejection.
        </p>
      </div>

      <div className="flex flex-wrap gap-3 border-t border-[#edf0f4] pt-5">
        <button
          type="button"
          onClick={() => handleDecision("approve")}
          disabled={actionLoading}
          className="rounded-lg bg-emerald-600 px-5 py-2.5 text-xs font-semibold text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {actionLoading ? "Processing..." : "Approve"}
        </button>

        <button
          type="button"
          onClick={() => handleDecision("request_changes")}
          disabled={actionLoading}
          className="rounded-lg border border-[#ddd5f0] bg-[#f7f4fc] px-5 py-2.5 text-xs font-semibold text-[#7963a8] transition-colors hover:bg-[#f0ebf8] disabled:cursor-not-allowed disabled:opacity-50"
        >
          Request changes
        </button>

        <button
          type="button"
          onClick={() => handleDecision("reject")}
          disabled={actionLoading}
          className="rounded-lg border border-red-200 bg-white px-5 py-2.5 text-xs font-semibold text-red-600 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Reject
        </button>
      </div>
    </div>
  )}

  {review.status === "changes_requested" && (
    <div className="mt-5 rounded-lg border border-violet-200 bg-violet-50 p-4">
      <p className="text-xs font-semibold text-violet-800">
        Changes requested
      </p>

      <p className="mt-1 text-xs leading-6 text-violet-700">
        Review the previous decision note, update the proposal
        above and submit a revised version. The revised proposal
        will return to pending review.
      </p>
    </div>
  )}

  {review.status === "approved" && (
  <div className="mt-5 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
    <p className="text-xs font-semibold text-emerald-800">
      Proposal approved
    </p>

    <p className="mt-1 text-xs leading-6 text-emerald-700">
      Human approval has been recorded. The proposed action
      still needs to be executed separately.
    </p>

    {review.action_type === "send_support_response" ? (
      <button
        type="button"
        onClick={handleExecuteApprovedAction}
        disabled={executionLoading}
        className="mt-4 rounded-lg bg-emerald-700 px-5 py-2.5 text-xs font-semibold text-white transition-colors hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {executionLoading
          ? "Queuing action..."
          : execution
            ? "Execute again / retrieve existing action"
            : "Execute approved response"}
      </button>
    ) : (
      <p className="mt-3 text-xs text-emerald-700">
        This action type does not currently have an execution provider.
      </p>
    )}
  </div>
)}

  {review.status === "rejected" && (
    <div className="mt-5 rounded-lg border border-red-200 bg-red-50 p-4">
      <p className="text-xs font-semibold text-red-800">
        Proposal rejected
      </p>

      <p className="mt-1 text-xs leading-6 text-red-700">
        This review has reached a final rejected state.
        No further decisions can be made on this review.
      </p>
    </div>
  )}
</section>

    {execution && (
  <section className="rounded-2xl border border-[#e9edf3] bg-white p-5 sm:p-6">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 className="text-sm font-semibold text-[#263750]">
          Action execution
        </h2>

        <p className="mt-1 text-xs text-slate-500">
          Execution ID: {execution.id}
        </p>
      </div>

      <span
        className={`rounded-full px-3 py-1 text-[11px] font-semibold ${
          execution.status === "succeeded"
            ? "bg-emerald-50 text-emerald-700"
            : execution.status === "failed"
              ? "bg-red-50 text-red-700"
              : execution.status === "running"
                ? "bg-blue-50 text-blue-700"
                : "bg-amber-50 text-amber-700"
        }`}
      >
        {formatLabel(execution.status)}
      </span>
    </div>

    <div className="mt-5 grid gap-4 sm:grid-cols-2">
      <div>
        <p className="text-[11px] font-medium uppercase text-slate-400">
          Provider
        </p>

        <p className="mt-1 text-sm text-[#34465f]">
          {execution.provider || "Not available"}
        </p>
      </div>

      <div>
        <p className="text-[11px] font-medium uppercase text-slate-400">
          Attempt count
        </p>

        <p className="mt-1 text-sm text-[#34465f]">
          {execution.attempt_count ?? "Not available"}
        </p>
      </div>
    </div>

    {execution.status === "succeeded" &&
      execution.provider_response?.external_delivery_performed === false && (
        <div className="mt-5 rounded-lg border border-blue-200 bg-blue-50 p-3">
          <p className="text-xs font-semibold text-blue-800">
            Mock execution successful
          </p>

          <p className="mt-1 text-xs leading-5 text-blue-700">
            The execution was successful, but no external email was sent.
          </p>
        </div>
      )}

    {executionError && (
      <p className="mt-4 text-xs text-red-600">
        {executionError}
      </p>
    )}

    <button
      type="button"
      onClick={handleRefreshExecution}
      disabled={executionLoading}
      className="mt-5 rounded-lg border border-[#dce3ec] bg-white px-4 py-2 text-xs font-semibold text-[#34465f] hover:bg-slate-50 disabled:opacity-50"
    >
      {executionLoading
        ? "Refreshing..."
        : "Refresh execution status"}
    </button>
  </section>
)}

{executionError && !execution && (
  <p className="text-xs text-red-600">
    {executionError}
  </p>
)}

    </div>
  );
}