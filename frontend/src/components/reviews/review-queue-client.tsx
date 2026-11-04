"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Clock3,
  FileText,
  Layers3,
  RefreshCw,
  Workflow,
} from "lucide-react";

import {
  getReviews,
  getClassificationReviews,
} from "@/lib/api/reviews";

import type {
  ReviewRequest,
  ReviewStatus,
  ClassificationReview,
  ClassificationReviewStatus,
} from "@/lib/types/review";

type QueueItem =
  | {
      kind: "classification";
      review: ClassificationReview;
    }
  | {
      kind: "action";
      review: ReviewRequest;
    };

type TypeFilter = "all" | "classification" | "action";

type StatusFilter =
  | "all"
  | ReviewStatus
  | ClassificationReviewStatus;

function relationId(value: ReviewRequest["workflow_run"]): string {
  if (value === null || value === undefined) return "Not available";

  if (typeof value === "object") {
    return value.id === undefined ? "Not available" : String(value.id);
  }

  return String(value);
}

function formatLabel(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (char) =>
    char.toUpperCase()
  );
}

function formatDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "Date unavailable";

  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function statusStyle(status: string): string {
  switch (status) {
    case "pending":
      return "bg-amber-50 text-amber-700";

    case "changes_requested":
      return "bg-violet-50 text-violet-700";

    case "approved":
    case "resolved":
      return "bg-emerald-50 text-emerald-700";

    case "rejected":
      return "bg-red-50 text-red-700";

    default:
      return "bg-slate-100 text-slate-600";
  }
}

const typeFilters: { label: string; value: TypeFilter }[] = [
  { label: "All review types", value: "all" },
  { label: "Classification", value: "classification" },
  { label: "Action proposals", value: "action" },
];

const statusFilters: { label: string; value: StatusFilter }[] = [
  { label: "All statuses", value: "all" },
  { label: "Pending", value: "pending" },
  { label: "Changes requested", value: "changes_requested" },
  { label: "Approved", value: "approved" },
  { label: "Rejected", value: "rejected" },
  { label: "Resolved", value: "resolved" },
];

export function ReviewQueueClient() {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
  const [statusFilter, setStatusFilter] =
    useState<StatusFilter>("all");
  const [search, setSearch] = useState("");

  useEffect(() => {
    let active = true;

    async function loadReviews() {
      try {
        const [actionReviews, classificationReviews] =
          await Promise.all([
            getReviews(),
            getClassificationReviews("all"),
          ]);

        if (!active) return;

        const combined: QueueItem[] = [
          ...classificationReviews.map((review) => ({
            kind: "classification" as const,
            review,
          })),
          ...actionReviews.map((review) => ({
            kind: "action" as const,
            review,
          })),
        ];

        combined.sort(
          (a, b) =>
            new Date(b.review.created_at).getTime() -
            new Date(a.review.created_at).getTime()
        );

        setItems(combined);
        setError(null);
      } catch (err) {
        if (!active) return;

        setError(
          err instanceof Error
            ? err.message
            : "Unable to load reviews."
        );
      } finally {
        if (active) setLoading(false);
      }
    }

    void loadReviews();

    return () => {
      active = false;
    };
  }, [reload]);

  function handleRetry() {
    setLoading(true);
    setError(null);
    setReload((current) => current + 1);
  }

  const classificationReviews = items.filter(
    (item) => item.kind === "classification"
  );

  const actionReviews = items.filter(
    (item) => item.kind === "action"
  );

  const pendingCount = items.filter(
    (item) => item.review.status === "pending"
  ).length;

  const classificationPendingCount = classificationReviews.filter(
    (item) => item.review.status === "pending"
  ).length;

  const actionPendingCount = actionReviews.filter(
    (item) => item.review.status === "pending"
  ).length;

  const filteredItems = items.filter((item) => {
    const matchesType =
      typeFilter === "all" || item.kind === typeFilter;

    const matchesStatus =
      statusFilter === "all" ||
      item.review.status === statusFilter;

    const workflowId =
      item.kind === "classification"
        ? item.review.workflow_run_id
        : relationId(
            item.review.workflow_run_id ??
              item.review.workflow_run
          );

    const searchParts =
      item.kind === "classification"
        ? [
            item.review.id,
            item.review.ticket_title,
            item.review.ticket_id,
            item.review.proposed_category,
            item.review.proposed_priority,
            item.review.status,
            workflowId,
          ]
        : [
            item.review.id,
            item.review.action_type,
            item.review.status,
            workflowId,
          ];

    const searchText = searchParts.join(" ").toLowerCase();

    return (
      matchesType &&
      matchesStatus &&
      searchText.includes(search.trim().toLowerCase())
    );
  });

  if (loading) {
    return (
      <div className="flex min-h-56 items-center justify-center">
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-[#365a88]" />
          Loading reviews...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-6">
        <p className="text-sm font-semibold text-red-700">
          Unable to load reviews
        </p>

        <p className="mt-2 text-sm text-red-600">{error}</p>

        <button
          type="button"
          onClick={handleRetry}
          className="mt-4 inline-flex items-center gap-2 rounded-lg bg-[#294b76] px-4 py-2 text-sm font-medium text-white hover:bg-[#203d61]"
        >
          <RefreshCw size={14} />
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-7">
      {/* Summary */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {[
          {
            label: "Pending reviews",
            value: pendingCount,
            icon: Clock3,
            accent: "bg-amber-50 text-amber-700",
          },
          {
            label: "Classification reviews",
            value: classificationPendingCount,
            icon: Workflow,
            accent: "bg-blue-50 text-blue-700",
          },
          {
            label: "Action proposals",
            value: actionPendingCount,
            icon: Layers3,
            accent: "bg-violet-50 text-violet-700",
          },
        ].map((card) => {
          const Icon = card.icon;

          return (
            <article
              key={card.label}
              className="rounded-2xl border border-[#e9edf3] bg-white p-5"
            >
              <div className="flex items-center justify-between">
                <p className="text-xs font-medium text-slate-500">
                  {card.label}
                </p>

                <div
                  className={`flex h-10 w-10 items-center justify-center rounded-xl ${card.accent}`}
                >
                  <Icon size={19} />
                </div>
              </div>

              <p className="mt-4 text-3xl font-semibold text-[#263750]">
                {card.value}
              </p>
            </article>
          );
        })}
      </section>

      {/* Filters */}
      <section className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-[#263750]">
              Human review queue
            </h2>

            <p className="mt-1 text-xs text-slate-500">
              Review agent classifications and proposed actions.
            </p>
          </div>

          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search ticket, review or workflow..."
            className="h-10 w-full rounded-lg border border-[#e9edf3] bg-white px-3 text-sm outline-none placeholder:text-slate-400 focus:border-[#91a9c7] sm:max-w-xs"
          />
        </div>

        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
            Review type
          </p>

          <div className="flex gap-2 overflow-x-auto pb-1">
            {typeFilters.map((filter) => (
              <button
                key={filter.value}
                type="button"
                onClick={() => setTypeFilter(filter.value)}
                className={`shrink-0 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                  typeFilter === filter.value
                    ? "bg-[#294b76] text-white"
                    : "border border-[#e9edf3] bg-white text-slate-600 hover:bg-slate-50"
                }`}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
            Status
          </p>

          <div className="flex gap-2 overflow-x-auto pb-1">
            {statusFilters.map((filter) => (
              <button
                key={filter.value}
                type="button"
                onClick={() => setStatusFilter(filter.value)}
                className={`shrink-0 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                  statusFilter === filter.value
                    ? "bg-[#294b76] text-white"
                    : "border border-[#e9edf3] bg-white text-slate-600 hover:bg-slate-50"
                }`}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Records */}
      <section className="space-y-3">
        {filteredItems.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-[#dce3ec] bg-white px-6 py-14 text-center">
            <FileText
              size={28}
              className="mx-auto text-slate-300"
            />

            <p className="mt-4 text-sm font-semibold text-[#34465f]">
              No reviews found
            </p>

            <p className="mt-1 text-xs text-slate-500">
              {items.length === 0
                ? "There are currently no reviews requiring staff attention."
                : "Try changing your review type, status or search."}
            </p>
          </div>
        ) : (
          filteredItems.map((item) => {
            const isClassification =
              item.kind === "classification";

            const review = item.review;

            const workflowId = isClassification
              ? item.review.workflow_run_id
              : relationId(
                  item.review.workflow_run_id ??
                    item.review.workflow_run
                );

            const href = isClassification
              ? `/reviews/classifications/${encodeURIComponent(review.id)}`
              : `/reviews/${encodeURIComponent(review.id)}`;

            return (
              <Link
                key={`${item.kind}-${review.id}`}
                href={href}
                className="group block rounded-2xl border border-[#e9edf3] bg-white p-5 transition-all hover:border-[#cbd8e8] hover:shadow-[0_4px_16px_rgba(30,50,80,0.05)]"
              >
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded-full px-2.5 py-1 text-[10px] font-semibold ${
                          isClassification
                            ? "bg-blue-50 text-blue-700"
                            : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {isClassification
                          ? "Classification"
                          : "Action proposal"}
                      </span>

                      <span
                        className={`rounded-full px-2.5 py-1 text-[10px] font-semibold ${statusStyle(review.status)}`}
                      >
                        {formatLabel(review.status)}
                      </span>
                    </div>

                    <h3 className="mt-3 text-sm font-semibold text-[#263750]">
                      {isClassification
                        ? item.review.ticket_title
                        : formatLabel(item.review.action_type)}
                    </h3>

                    {isClassification ? (
                      <p className="mt-1 text-xs text-slate-500">
                        Suggested classification:{" "}
                        <span className="font-medium text-[#34465f]">
                          {formatLabel(item.review.proposed_category)}
                        </span>
                        {" · "}
                        Priority:{" "}
                        <span className="font-medium text-[#34465f]">
                          {formatLabel(item.review.proposed_priority)}
                        </span>
                      </p>
                    ) : (
                      <p className="mt-1 text-xs text-slate-500">
                        Revision {item.review.revision_number}
                      </p>
                    )}

                    <p className="mt-2 break-all text-xs text-slate-400">
                      Review: {review.id}
                    </p>

                    <p className="mt-1 break-all text-xs text-slate-400">
                      Workflow: {workflowId}
                    </p>
                  </div>

                  <div className="flex shrink-0 items-center justify-between gap-4 sm:justify-end">
                    <div className="text-left sm:text-right">
                      <p className="text-[10px] text-slate-400">
                        Submitted
                      </p>

                      <p className="mt-1 text-xs font-medium text-slate-600">
                        {formatDate(review.created_at)}
                      </p>
                    </div>

                    <ArrowRight
                      size={17}
                      className="text-slate-300 transition-transform group-hover:translate-x-1 group-hover:text-[#365a88]"
                    />
                  </div>
                </div>
              </Link>
            );
          })
        )}
      </section>
    </div>
  );
}