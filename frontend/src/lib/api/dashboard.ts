import { apiRequest } from "./client";
import type { DashboardOverview } from "@/lib/types/dashboard";

export async function getDashboardOverview(): Promise<DashboardOverview> {
  return apiRequest<DashboardOverview>("/dashboard/");
}