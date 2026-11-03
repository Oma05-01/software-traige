import type { Ticket } from "@/lib/types/ticket";

export const mockTickets: Ticket[] = [
  {
    id: "STT-0001",
    title: "PDF upload failure",
    description:
      "The application crashes when uploading PDF files larger than 25 MB.",
    reporter_name: "Test Reporter",
    reporter_email: "reporter@example.com",
    environment: "Windows 11, Chrome",
    steps_to_reproduce:
      "Select a PDF larger than 25 MB and upload it.",
    expected_behavior: "The PDF should upload successfully.",
    actual_behavior: "The application crashes.",
    category: "bug",
    priority: "high",
    status: "awaiting_review",
    created_at: "2026-11-01T13:35:24Z",
    updated_at: "2026-11-01T13:35:24Z",
  },
  {
    id: "STT-0002",
    title: "Dashboard freezes during report generation",
    description:
      "The dashboard becomes unresponsive when generating reports containing more than 500 records.",
    reporter_name: "Sample Reporter",
    reporter_email: "sample@example.com",
    environment: "Windows 11, Chrome",
    steps_to_reproduce:
      "Open reports, select more than 500 records and click Generate.",
    expected_behavior: "The report should generate successfully.",
    actual_behavior: "The dashboard becomes unresponsive.",
    category: "bug",
    priority: "medium",
    status: "in_progress",
    created_at: "2026-11-01T12:15:00Z",
    updated_at: "2026-11-01T12:15:00Z",
  },
  {
    id: "STT-0003",
    title: "Request for dark mode",
    description:
      "It would be useful to have a dark mode option across the application.",
    reporter_name: "Sample User",
    reporter_email: "user@example.com",
    environment: "macOS, Safari",
    steps_to_reproduce: "Not applicable.",
    expected_behavior: "Users can select a dark appearance.",
    actual_behavior: "Only the existing appearance is available.",
    category: "feature",
    priority: "low",
    status: "submitted",
    created_at: "2026-10-31T15:30:00Z",
    updated_at: "2026-10-31T15:30:00Z",
  },
  {
    id: "STT-0004",
    title: "Password reset email not received",
    description:
      "The password reset confirmation does not arrive after requesting a reset.",
    reporter_name: "Demo Reporter",
    reporter_email: "demo@example.com",
    environment: "Ubuntu, Firefox",
    steps_to_reproduce:
      "Request a password reset and check the registered email inbox.",
    expected_behavior: "A password reset email should arrive.",
    actual_behavior: "The email does not arrive.",
    category: "bug",
    priority: "high",
    status: "completed",
    created_at: "2026-10-30T10:20:00Z",
    updated_at: "2026-10-30T10:20:00Z",
  },
  {
    id: "STT-0005",
    title: "Duplicate notification emails",
    description:
      "The application appears to send duplicate notification emails.",
    reporter_name: "Example User",
    reporter_email: "example@example.com",
    environment: "Windows 11, Edge",
    steps_to_reproduce:
      "Trigger an application notification and inspect the inbox.",
    expected_behavior: "One notification should be received.",
    actual_behavior: "Duplicate notifications are received.",
    category: "bug",
    priority: "critical",
    status: "closed",
    created_at: "2026-10-29T09:00:00Z",
    updated_at: "2026-10-29T09:00:00Z",
  },
];