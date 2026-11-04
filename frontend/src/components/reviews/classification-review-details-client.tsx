"use client";


import {useEffect, useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowLeft,
  CalendarDays,
  CheckCircle2,
  Clock3,
  RefreshCw,
  Workflow,
} from "lucide-react";

import {
  getClassificationReview,
  resolveClassificationReview,
} from "@/lib/api/reviews";

import type {
  ClassificationReview,
  ResolveClassificationPayload,
} from "@/lib/types/review";

interface ClassificationReviewDetailsClientProps {
  reviewId: string;
}

type ResolvedCategory = "" | "bug" | "feature";

type ResolvedPriority =
  | ""
  | "low"
  | "medium"
  | "high"
  | "critical";

function formatLabel(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (char) =>
    char.toUpperCase()
  );
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

function statusStyle(status: string): string {
  return status === "resolved"
    ? "bg-emerald-50 text-emerald-700"
    : "bg-amber-50 text-amber-700";
}

function DetailSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-[#e9edf3] bg-white p-5 sm:p-6">
      <h2 className="text-sm font-semibold text-[#263750]">
        {title}
      </h2>

      <div className="mt-4 text-sm leading-7 text-slate-600">
        {children}
      </div>
    </section>
  );
}

function DetailField({
  label,
  value,
}: {
  label: string;
  value?: string | null;
}) {
  return (
    <div>
      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
        {label}
      </p>

      <p className="mt-1 break-words text-sm text-[#34465f]">
        {value?.trim() || "Not provided"}
      </p>
    </div>
  );
}

export function ClassificationReviewDetailsClient({
  reviewId,
}: ClassificationReviewDetailsClientProps) {
  const [review, setReview] =
    useState<ClassificationReview | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  const [resolvedCategory, setResolvedCategory] =
    useState<ResolvedCategory>("");

  const [resolvedPriority, setResolvedPriority] =
    useState<ResolvedPriority>("");

  const [decisionNote, setDecisionNote] = useState("");

  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadReview() {
      try {
        const data = await getClassificationReview(reviewId);

        if (!active) return;

        setReview(data);

        setResolvedCategory(
          data.proposed_category === "bug" ||
            data.proposed_category === "feature"
            ? data.proposed_category
            : ""
        );

        setResolvedPriority(
          data.proposed_priority === "low" ||
            data.proposed_priority === "medium" ||
            data.proposed_priority === "high" ||
            data.proposed_priority === "critical"
            ? data.proposed_priority
            : ""
        );

        setError(null);
      } catch (err) {
        if (!active) return;

        setError(
          err instanceof Error
            ? err.message
            : "Unable to load this classification review."
        );
      } finally {
        if (active) setLoading(false);
      }
    }

    void loadReview();

    return () => {
      active = false;
    };
  }, [reviewId, reload]);

  function handleRetry() {
    setLoading(true);
    setError(null);
    setReload((current) => current + 1);
  }

  async function handleResolve(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!review || review.status !== "pending") return;

    if (!resolvedCategory || !resolvedPriority) {
      setActionError(
        "Select a category and an assessed priority before resolving."
      );
      return;
    }

    setActionLoading(true);
    setActionError(null);
    setActionMessage(null);

    const payload: ResolveClassificationPayload = {
      resolved_category: resolvedCategory,
      resolved_priority: resolvedPriority,
      decision_note: decisionNote.trim(),
    };

    try {
      const updated = await resolveClassificationReview(
        review.id,
        payload
      );

      setReview(updated);

      setActionMessage(
        updated.decision === "confirmed"
          ? "Classification confirmed. The workflow has resumed."
          : "Classification corrected. The workflow has resumed."
      );
    } catch (err) {
      setActionError(
        err instanceof Error
          ? err.message
          : "Unable to resolve this classification."
      );
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-64 items-center justify-center">
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-[#365a88]" />
          Loading classification review...
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
              Unable to load classification review
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

  return (
    <div className="space-y-7">
      <Link
        href="/reviews"
        className="inline-flex items-center gap-2 text-sm text-slate-500 transition-colors hover:text-[#294b76]"
      >
        <ArrowLeft size={16} />
        Back to reviews
      </Link>

      {/* Heading */}
      <section>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-blue-50 px-3 py-1 text-[11px] font-semibold text-blue-700">
            Classification review
          </span>

          <span
            className={`rounded-full px-3 py-1 text-[11px] font-semibold ${statusStyle(review.status)}`}
          >
            {formatLabel(review.status)}
          </span>
        </div>

        <h1 className="text-2xl font-semibold tracking-tight text-[#263750] sm:text-3xl">
          {review.ticket_title}
        </h1>

        <p className="mt-2 break-all text-xs text-slate-400">
          Review ID: {review.id}
        </p>
      </section>

      {/* Metadata */}
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
              Reviewed
            </span>
          </div>

          <p className="mt-3 text-sm font-medium text-[#34465f]">
            {formatDate(review.reviewed_at)}
          </p>
        </article>

        <article className="rounded-xl border border-[#e9edf3] bg-white p-4">
          <div className="flex items-center gap-2 text-slate-400">
            <Workflow size={16} />
            <span className="text-[11px] font-medium uppercase">
              Confidence
            </span>
          </div>

          <p className="mt-3 text-sm font-medium text-[#34465f]">
            {review.classification_confidence
              ? formatLabel(review.classification_confidence)
              : "Not provided"}
          </p>
        </article>
      </section>

      {/* Agent suggestion */}
      <DetailSection title="Receptionist classification">
        <p className="mb-4 text-xs leading-6 text-slate-500">
          This is the original suggestion produced by the Receptionist.
          It is preserved even if staff corrects the classification.
        </p>

        <div className="grid gap-5 sm:grid-cols-2">
          <DetailField
            label="Proposed category"
            value={formatLabel(review.proposed_category)}
          />

          <DetailField
            label="Proposed priority"
            value={formatLabel(review.proposed_priority)}
          />
        </div>
      </DetailSection>

      {/* Ticket context */}
      <DetailSection title="Ticket description">
        <p className="whitespace-pre-wrap">
          {review.ticket_description || "No description provided."}
        </p>
      </DetailSection>

      <DetailSection title="Environment">
        <p className="whitespace-pre-wrap">
          {review.ticket_environment || "No environment information provided."}
        </p>
      </DetailSection>

      <DetailSection title="Steps to reproduce">
        <p className="whitespace-pre-wrap">
          {review.ticket_steps_to_reproduce || "No reproduction steps provided."}
        </p>
      </DetailSection>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <DetailSection title="Expected behaviour">
          <p className="whitespace-pre-wrap">
            {review.ticket_expected_behavior || "Not provided."}
          </p>
        </DetailSection>

        <DetailSection title="Actual behaviour">
          <p className="whitespace-pre-wrap">
            {review.ticket_actual_behavior || "Not provided."}
          </p>
        </DetailSection>
      </section>

      {/* Resolution */}
      {review.status === "pending" ? (
        <section className="rounded-2xl border border-[#e9edf3] bg-white p-5 sm:p-6">
          <div>
            <h2 className="text-sm font-semibold text-[#263750]">
              Staff classification decision
            </h2>

            <p className="mt-1 text-xs leading-6 text-slate-500">
              Confirm the suggested classification or correct it.
              Bug reports continue to the Debugger; Feature requests
              continue to the Product Manager.
            </p>
          </div>

          <form onSubmit={handleResolve} className="mt-5 space-y-5">
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label
                  htmlFor="resolved-category"
                  className="text-xs font-medium text-[#34465f]"
                >
                  Final category
                </label>

                <select
                  id="resolved-category"
                  value={resolvedCategory}
                  onChange={(event) =>
                    setResolvedCategory(
                      event.target.value as ResolvedCategory
                    )
                  }
                  required
                  className="mt-2 h-11 w-full rounded-lg border border-[#e2e8f0] bg-white px-3 text-sm text-[#34465f] outline-none focus:border-[#91a9c7]"
                >
                  <option value="">Select category</option>
                  <option value="bug">Bug</option>
                  <option value="feature">Feature Request</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="resolved-priority"
                  className="text-xs font-medium text-[#34465f]"
                >
                  Final priority
                </label>

                <select
                  id="resolved-priority"
                  value={resolvedPriority}
                  onChange={(event) =>
                    setResolvedPriority(
                      event.target.value as ResolvedPriority
                    )
                  }
                  required
                  className="mt-2 h-11 w-full rounded-lg border border-[#e2e8f0] bg-white px-3 text-sm text-[#34465f] outline-none focus:border-[#91a9c7]"
                >
                  <option value="">Select priority</option>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>
            </div>

            <div>
              <label
                htmlFor="classification-decision-note"
                className="text-xs font-medium text-[#34465f]"
              >
                Decision note
              </label>

              <textarea
                id="classification-decision-note"
                value={decisionNote}
                onChange={(event) =>
                  setDecisionNote(event.target.value)
                }
                rows={3}
                maxLength={2000}
                placeholder="Explain the reason for confirming or correcting the classification..."
                className="mt-2 w-full resize-y rounded-lg border border-[#e2e8f0] bg-[#f8fafc] p-3 text-sm text-[#34465f] outline-none placeholder:text-slate-400 focus:border-[#91a9c7]"
              />
            </div>

            {actionError && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-3">
                <p className="text-xs leading-5 text-red-700">
                  {actionError}
                </p>
              </div>
            )}

            <div className="flex justify-end border-t border-[#edf0f4] pt-5">
              <button
                type="submit"
                disabled={
                  actionLoading ||
                  !resolvedCategory ||
                  !resolvedPriority
                }
                className="inline-flex items-center gap-2 rounded-lg bg-[#294b76] px-5 py-2.5 text-xs font-semibold text-white transition-colors hover:bg-[#203d61] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {actionLoading
                  ? "Recording decision..."
                  : "Confirm classification and continue"}
              </button>
            </div>
          </form>
        </section>
      ) : (
        <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 sm:p-6">
          <div className="flex items-center gap-2 text-emerald-800">
            <CheckCircle2 size={18} />

            <h2 className="text-sm font-semibold">
              Classification resolved
            </h2>
          </div>

          <div className="mt-5 grid gap-5 sm:grid-cols-2">
            <DetailField
              label="Final category"
              value={formatLabel(review.resolved_category)}
            />

            <DetailField
              label="Final priority"
              value={formatLabel(review.resolved_priority)}
            />

            <DetailField
              label="Decision"
              value={formatLabel(review.decision)}
            />

            <DetailField
              label="Reviewed by"
              value={review.reviewed_by_username}
            />
          </div>

          {review.decision_note && (
            <div className="mt-5 border-t border-emerald-200 pt-4">
              <p className="text-[11px] font-medium uppercase tracking-wide text-emerald-700">
                Decision note
              </p>

              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-emerald-900">
                {review.decision_note}
              </p>
            </div>
          )}
        </section>
      )}

      {actionMessage && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
          <p className="text-sm text-emerald-800">
            {actionMessage}
          </p>
        </div>
      )}

      {/* References */}
      <DetailSection title="Workflow references">
        <div className="grid gap-5 sm:grid-cols-2">
          <DetailField
            label="Ticket ID"
            value={review.ticket_id}
          />

          <DetailField
            label="Workflow ID"
            value={review.workflow_run_id}
          />

          <DetailField
            label="Agent execution ID"
            value={review.agent_execution_id}
          />

          <DetailField
            label="Review ID"
            value={review.id}
          />
        </div>
      </DetailSection>
    </div>
  );
}