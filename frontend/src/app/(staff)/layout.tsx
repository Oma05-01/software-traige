import type { ReactNode } from "react";

import { DashboardShell } from "@/components/layout/dashboard-shell";
import { StaffAuthGuard } from "@/components/auth/staff-auth-guard";

interface StaffLayoutProps {
  children: ReactNode;
}

export default function StaffLayout({
  children,
}: StaffLayoutProps) {
  return (
    <DashboardShell>
      <StaffAuthGuard>
        {children}
      </StaffAuthGuard>
    </DashboardShell>
  );
}