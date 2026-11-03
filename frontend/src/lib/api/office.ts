import { apiRequest } from "./client";

import type {
  OfficeActivity,
} from "@/lib/types/office";

export async function getOfficeActivity(): Promise<OfficeActivity> {
  return apiRequest<OfficeActivity>("/workflows/office/");
}