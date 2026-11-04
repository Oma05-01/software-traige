import { apiRequest } from "./client";

import type {
  ReviewRequest,
  PaginatedReviewResponse,
  ClassificationReview,
  PaginatedClassificationReviewResponse,
  ResolveClassificationPayload,
} from "@/lib/types/review";

type ReviewListResponse =
  | ReviewRequest[]
  | PaginatedReviewResponse;

export async function getReviews(): Promise<ReviewRequest[]> {
  // Include historical reviews so every status filter works.
  const response = await apiRequest<ReviewListResponse>(
    "/reviews/?status=all"
  );

  return Array.isArray(response)
    ? response
    : response.results;
}

export async function getReview(
  reviewId: string
): Promise<ReviewRequest> {
  return apiRequest<ReviewRequest>(
    `/reviews/${encodeURIComponent(reviewId)}/`
  );
}

export async function updateReviewProposal(
  reviewId: string,
  proposedPayload: Record<string, unknown>
): Promise<ReviewRequest> {
  return apiRequest<ReviewRequest>(
    `/reviews/${encodeURIComponent(reviewId)}/edit/`,
    {
      method: "PATCH",
      body: JSON.stringify({
        proposed_payload: proposedPayload,
      }),
    }
  );
}

export async function approveReview(
  reviewId: string,
  decisionNote = ""
): Promise<ReviewRequest> {
  return apiRequest<ReviewRequest>(
    `/reviews/${encodeURIComponent(reviewId)}/approve/`,
    {
      method: "POST",
      body: JSON.stringify({
        decision_note: decisionNote,
      }),
    }
  );
}

export async function rejectReview(
  reviewId: string,
  decisionNote = ""
): Promise<ReviewRequest> {
  return apiRequest<ReviewRequest>(
    `/reviews/${encodeURIComponent(reviewId)}/reject/`,
    {
      method: "POST",
      body: JSON.stringify({
        decision_note: decisionNote,
      }),
    }
  );
}

export async function requestReviewChanges(
  reviewId: string,
  decisionNote: string
): Promise<ReviewRequest> {
  return apiRequest<ReviewRequest>(
    `/reviews/${encodeURIComponent(reviewId)}/request-changes/`,
    {
      method: "POST",
      body: JSON.stringify({
        decision_note: decisionNote,
      }),
    }
  );
}

export async function reviseReview(
  reviewId: string,
  proposedPayload: Record<string, unknown>
): Promise<ReviewRequest> {
  return apiRequest<ReviewRequest>(
    `/reviews/${encodeURIComponent(reviewId)}/revise/`,
    {
      method: "PATCH",
      body: JSON.stringify({
        proposed_payload: proposedPayload,
      }),
    }
  );
}

type ClassificationListResponse =
  | ClassificationReview[]
  | PaginatedClassificationReviewResponse;

export async function getClassificationReviews(
  status = "all",
  workflowRunId?: string
): Promise<ClassificationReview[]> {
  const params = new URLSearchParams({ status });

  if (workflowRunId) {
    params.set("workflow_run_id", workflowRunId);
  }

  const response = await apiRequest<ClassificationListResponse>(
    `/reviews/classifications/?${params.toString()}`
  );

  return Array.isArray(response)
    ? response
    : response.results;
}

export async function getClassificationReview(
  reviewId: string
): Promise<ClassificationReview> {
  return apiRequest<ClassificationReview>(
    `/reviews/classifications/${encodeURIComponent(reviewId)}/`
  );
}

export async function resolveClassificationReview(
  reviewId: string,
  payload: ResolveClassificationPayload
): Promise<ClassificationReview> {
  return apiRequest<ClassificationReview>(
    `/reviews/classifications/${encodeURIComponent(reviewId)}/resolve/`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}
