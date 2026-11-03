"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowLeft,
  CalendarDays,
  Clock3,
  Mail,
  RefreshCw,
  UserRound,
} from "lucide-react";

import { getTicket } from "@/lib/api/tickets";
import type { Ticket } from "@/lib/types/ticket";
import { getTicketWorkflow } from "@/lib/api/workflows";
import type { WorkflowRun } from "@/lib/types/workflow";
import { WorkflowTimeline } from "@/components/workflows/workflow-timeline";

interface TicketDetailsClientProps {
  ticketId: string;
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (char) =>
    char.toUpperCase()
  );
}

function formatDate(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unavailable";
  }

  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function statusStyle(status: string) {
  switch (status) {
    case "completed":
    case "closed":
      return "bg-emerald-50 text-emerald-700";

    case "in_progress":
      return "bg-amber-50 text-amber-700";

    case "awaiting_review":
      return "bg-violet-50 text-violet-700";

    case "submitted":
      return "bg-blue-50 text-blue-700";

    default:
      return "bg-slate-100 text-slate-600";
  }
}

function priorityStyle(priority: string) {
  switch (priority) {
    case "critical":
      return "bg-red-50 text-red-700";

    case "high":
      return "bg-orange-50 text-orange-700";

    case "medium":
      return "bg-amber-50 text-amber-700";

    case "low":
      return "bg-slate-100 text-slate-600";

    default:
      return "bg-slate-100 text-slate-600";
  }
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
      <p className="text-[11px] font-medium tracking-wide text-slate-400 uppercase">
        {label}
      </p>

      <p className="mt-1 text-sm text-[#34465f]">
        {value?.trim() || "Not provided"}
      </p>
    </div>
  );
}

export function TicketDetailsClient({
  ticketId,
}: TicketDetailsClientProps) {
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [workflow, setWorkflow] = useState<WorkflowRun | null>(null);
const [workflowError, setWorkflowError] = useState<string | null>(null);

  useEffect(() => {
  let active = true;
  let timer: ReturnType<typeof setTimeout> | undefined;

  async function loadData() {
    let shouldPoll = false;

    const [ticketResult, workflowResult] = await Promise.allSettled([
      getTicket(ticketId),
      getTicketWorkflow(ticketId),
    ]);

    if (!active) return;

    if (ticketResult.status === "fulfilled") {
      setTicket(ticketResult.value);
      setError(null);
    } else {
      setError(
        ticketResult.reason instanceof Error
          ? ticketResult.reason.message
          : "Unable to load this ticket."
      );
    }

    if (workflowResult.status === "fulfilled") {
      const data = workflowResult.value;

      setWorkflow(data);
      setWorkflowError(null);

      shouldPoll =
        data.status === "queued" ||
        data.status === "running";
    } else {
      setWorkflow(null);
      setWorkflowError(
        workflowResult.reason instanceof Error
          ? workflowResult.reason.message
          : "Workflow information is unavailable."
      );
    }

    setLoading(false);

    // Poll while automated processing is still active.
    if (active && shouldPoll) {
      timer = setTimeout(loadData, 5000);
    }
  }

  void loadData();

  return () => {
    active = false;

    if (timer) {
      clearTimeout(timer);
    }
  };
}, [ticketId, reload]);

  function handleRetry() {
    setLoading(true);
    setError(null);
    setReload((current) => current + 1);
  }

  if (loading) {
    return (
      <div className="flex min-h-64 items-center justify-center">
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-[#365a88]" />
          Loading ticket details...
        </div>
      </div>
    );
  }

  if (error || !ticket) {
    return (
      <div className="space-y-5">
        <Link
          href="/tickets"
          className="inline-flex items-center gap-2 text-sm text-slate-500 transition-colors hover:text-[#294b76]"
        >
          <ArrowLeft size={16} />
          Back to tickets
        </Link>

        <div className="rounded-2xl border border-red-200 bg-red-50 p-6">
          <div className="flex items-center gap-2 text-red-700">
            <AlertCircle size={18} />

            <p className="text-sm font-semibold">
              Unable to load ticket
            </p>
          </div>

          <p className="mt-2 text-sm text-red-600">
            {error || "The requested ticket could not be found."}
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
      {/* Back navigation */}
      <Link
        href="/tickets"
        className="inline-flex items-center gap-2 text-sm text-slate-500 transition-colors hover:text-[#294b76]"
      >
        <ArrowLeft size={16} />
        Back to tickets
      </Link>

      {/* Ticket heading */}
      <section>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span
            className={`rounded-full px-3 py-1 text-[11px] font-medium ${statusStyle(ticket.status)}`}
          >
            {formatLabel(ticket.status)}
          </span>

          <span
            className={`rounded-full px-3 py-1 text-[11px] font-medium ${priorityStyle(ticket.priority)}`}
          >
            {formatLabel(ticket.priority)}
          </span>

          <span className="text-xs text-slate-400">
            {formatLabel(ticket.category)}
          </span>
        </div>

        <h1 className="text-2xl font-semibold tracking-tight text-[#263750] sm:text-3xl">
          {ticket.title}
        </h1>

        <p className="mt-2 break-all text-xs text-slate-400">
          Ticket ID: {ticket.id}
        </p>
      </section>

      {/* Metadata */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <article className="rounded-xl border border-[#e9edf3] bg-white p-4">
          <div className="flex items-center gap-2 text-slate-400">
            <UserRound size={16} />
            <span className="text-[11px] font-medium uppercase">
              Reporter
            </span>
          </div>

          <p className="mt-3 text-sm font-semibold text-[#34465f]">
            {ticket.reporter_name}
          </p>
        </article>

        <article className="rounded-xl border border-[#e9edf3] bg-white p-4">
          <div className="flex items-center gap-2 text-slate-400">
            <Mail size={16} />
            <span className="text-[11px] font-medium uppercase">
              Reporter email
            </span>
          </div>

          <p className="mt-3 break-all text-sm font-medium text-[#34465f]">
            {ticket.reporter_email}
          </p>
        </article>

        <article className="rounded-xl border border-[#e9edf3] bg-white p-4">
          <div className="flex items-center gap-2 text-slate-400">
            <CalendarDays size={16} />
            <span className="text-[11px] font-medium uppercase">
              Submitted
            </span>
          </div>

          <p className="mt-3 text-sm font-medium text-[#34465f]">
            {formatDate(ticket.created_at)}
          </p>
        </article>

        <article className="rounded-xl border border-[#e9edf3] bg-white p-4">
          <div className="flex items-center gap-2 text-slate-400">
            <Clock3 size={16} />
            <span className="text-[11px] font-medium uppercase">
              Last updated
            </span>
          </div>

          <p className="mt-3 text-sm font-medium text-[#34465f]">
            {formatDate(ticket.updated_at)}
          </p>
        </article>
      </section>

      {/* Description */}
      <DetailSection title="Ticket description">
        <p className="whitespace-pre-wrap">
          {ticket.description || "No description provided."}
        </p>
      </DetailSection>

      {/* Environment */}
      <DetailSection title="Environment">
        <p className="whitespace-pre-wrap">
          {ticket.environment || "No environment information provided."}
        </p>
      </DetailSection>

      {/* Reproduction steps */}
      <DetailSection title="Steps to reproduce">
        <p className="whitespace-pre-wrap">
          {ticket.steps_to_reproduce || "No reproduction steps provided."}
        </p>
      </DetailSection>

      {/* Expected and actual behaviour */}
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <DetailSection title="Expected behaviour">
          <p className="whitespace-pre-wrap">
            {ticket.expected_behavior || "Not provided."}
          </p>
        </DetailSection>

        <DetailSection title="Actual behaviour">
          <p className="whitespace-pre-wrap">
            {ticket.actual_behavior || "Not provided."}
          </p>
        </DetailSection>
      </section>

      <WorkflowTimeline
        workflow={workflow}
        category={ticket.category}
        error={workflowError}
      />

      {/* Workflow reference */}
      {ticket.workflow_id && (
        <DetailSection title="Workflow reference">
          <DetailField
            label="Workflow ID"
            value={ticket.workflow_id}
          />
        </DetailSection>
      )}
    </div>
  );
}