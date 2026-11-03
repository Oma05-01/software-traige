import { apiRequest } from "./client";

import type { ActionExecution } from "@/lib/types/action-execution";

export async function executeApprovedReview(
  reviewId: string
): Promise<ActionExecution> {
  return apiRequest<ActionExecution>(
    `/integrations/reviews/${encodeURIComponent(reviewId)}/execute/`,
    {
      method: "POST",
      body: JSON.stringify({}),
    }
  );
}

export async function getActionExecution(
  actionId: string
): Promise<ActionExecution> {
  return apiRequest<ActionExecution>(
    `/integrations/actions/${encodeURIComponent(actionId)}/`
  );
}