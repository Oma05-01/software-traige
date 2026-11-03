"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  Copy,
  LoaderCircle,
} from "lucide-react";

import { submitTicket } from "@/lib/api/tickets";
import type { Ticket } from "@/lib/types/ticket";

interface FormValues {
  title: string;
  description: string;
  reporter_name: string;
  reporter_email: string;
  environment: string;
  steps_to_reproduce: string;
  expected_behavior: string;
  actual_behavior: string;
}

const initialForm: FormValues = {
  title: "",
  description: "",
  reporter_name: "",
  reporter_email: "",
  environment: "",
  steps_to_reproduce: "",
  expected_behavior: "",
  actual_behavior: "",
};

const inputClassName =
  "mt-2 w-full rounded-xl border border-[#e2e8f0] bg-white px-4 py-3 text-sm text-[#34465f] outline-none transition-colors placeholder:text-slate-400 focus:border-[#7896ba] focus:ring-2 focus:ring-[#7896ba]/10";

const labelClassName =
  "text-xs font-semibold text-[#34465f]";

export function TicketSubmissionForm() {
  const [form, setForm] = useState<FormValues>(initialForm);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submittedTicket, setSubmittedTicket] =
    useState<Ticket | null>(null);
  const [copied, setCopied] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (submitting) return;

    setSubmitting(true);
    setError(null);

    try {
      const ticket = await submitTicket({
        title: form.title.trim(),
        description: form.description.trim(),
        reporter_name: form.reporter_name.trim(),
        reporter_email: form.reporter_email.trim(),

        ...(form.environment.trim() && {
          environment: form.environment.trim(),
        }),

        ...(form.steps_to_reproduce.trim() && {
          steps_to_reproduce: form.steps_to_reproduce.trim(),
        }),

        ...(form.expected_behavior.trim() && {
          expected_behavior: form.expected_behavior.trim(),
        }),

        ...(form.actual_behavior.trim() && {
          actual_behavior: form.actual_behavior.trim(),
        }),
      });

      setSubmittedTicket(ticket);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong while submitting your report."
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function copyTicketReference() {
    if (!submittedTicket) return;

    try {
      await navigator.clipboard.writeText(submittedTicket.id);
      setCopied(true);
    } catch {
      setError("Unable to copy the ticket reference.");
    }
  }

  function handleSubmitAnother() {
    setForm(initialForm);
    setSubmittedTicket(null);
    setError(null);
    setCopied(false);
  }

  if (submittedTicket) {
    return (
      <div className="rounded-3xl border border-[#e5ebf3] bg-white p-6 shadow-[0_8px_35px_rgba(30,50,80,0.04)] sm:p-10">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-50">
          <CheckCircle2
            size={32}
            className="text-emerald-600"
            strokeWidth={1.7}
          />
        </div>

        <div className="mt-6 text-center">
          <p className="text-[10px] font-semibold tracking-[0.18em] text-emerald-600 uppercase">
            Submission received
          </p>

          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[#263750]">
            Your report is in our system.
          </h2>

          <p className="mx-auto mt-3 max-w-md text-sm leading-7 text-slate-500">
            Thank you for reporting this issue. Our triage workflow
            has been initiated, and the information will be reviewed
            by the appropriate agents.
          </p>
        </div>

        <div className="mt-8 rounded-2xl border border-[#e9edf3] bg-[#f8fafc] p-5">
          <p className="text-[10px] font-semibold tracking-wider text-slate-400 uppercase">
            Your ticket reference
          </p>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <p className="break-all text-sm font-semibold text-[#294b76]">
              {submittedTicket.id}
            </p>

            <button
              type="button"
              onClick={copyTicketReference}
              className="inline-flex items-center gap-2 rounded-lg border border-[#dce3ec] bg-white px-3 py-2 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50"
            >
              <Copy size={13} />
              {copied ? "Copied" : "Copy reference"}
            </button>
          </div>

          {submittedTicket.workflow_id && (
            <div className="mt-5 border-t border-[#e6ebf1] pt-4">
              <p className="text-[10px] font-semibold tracking-wider text-slate-400 uppercase">
                Workflow reference
              </p>

              <p className="mt-2 break-all text-xs text-slate-600">
                {submittedTicket.workflow_id}
              </p>
            </div>
          )}

          <div className="mt-5 flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-amber-400" />

            <span className="text-xs text-slate-500">
              Current ticket status:{" "}
              <span className="font-semibold text-[#34465f]">
                {submittedTicket.status.replaceAll("_", " ")}
              </span>
            </span>
          </div>
        </div>

        <div className="mt-7 flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            onClick={handleSubmitAnother}
            className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-[#294b76] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#203d61]"
          >
            Submit another report
            <ArrowRight size={16} />
          </button>

          <Link
            href="/login"
            className="flex items-center justify-center rounded-xl border border-[#e2e8f0] bg-white px-5 py-3 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50"
          >
            Staff sign in
          </Link>
        </div>

        <p className="mt-5 text-center text-[11px] leading-5 text-slate-400">
          Keep your ticket reference available for future correspondence.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-8">
      {/* Reporter information */}
      <section className="space-y-5">
        <div>
          <h2 className="text-sm font-semibold text-[#263750]">
            Your information
          </h2>

          <p className="mt-1 text-xs text-slate-500">
            How can our team identify and contact you?
          </p>
        </div>

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <div>
            <label htmlFor="reporter_name" className={labelClassName}>
              Full name <span className="text-red-500">*</span>
            </label>

            <input
              id="reporter_name"
              name="reporter_name"
              type="text"
              autoComplete="name"
              required
              value={form.reporter_name}
              onChange={(event) =>
                setForm({ ...form, reporter_name: event.target.value })
              }
              placeholder="Your full name"
              className={inputClassName}
            />
          </div>

          <div>
            <label htmlFor="reporter_email" className={labelClassName}>
              Email address <span className="text-red-500">*</span>
            </label>

            <input
              id="reporter_email"
              name="reporter_email"
              type="email"
              autoComplete="email"
              required
              value={form.reporter_email}
              onChange={(event) =>
                setForm({ ...form, reporter_email: event.target.value })
              }
              placeholder="you@example.com"
              className={inputClassName}
            />
          </div>
        </div>
      </section>

      <div className="h-px bg-[#edf0f4]" />

      {/* Issue details */}
      <section className="space-y-5">
        <div>
          <h2 className="text-sm font-semibold text-[#263750]">
            Issue details
          </h2>

          <p className="mt-1 text-xs text-slate-500">
            Describe the problem or feature you want to report.
          </p>
        </div>

        <div>
          <label htmlFor="title" className={labelClassName}>
            Issue title <span className="text-red-500">*</span>
          </label>

          <input
            id="title"
            name="title"
            type="text"
            required
            value={form.title}
            onChange={(event) =>
              setForm({ ...form, title: event.target.value })
            }
            placeholder="e.g. Unable to upload PDF documents"
            className={inputClassName}
          />
        </div>

        <div>
          <label htmlFor="description" className={labelClassName}>
            Description <span className="text-red-500">*</span>
          </label>

          <textarea
            id="description"
            name="description"
            required
            rows={5}
            value={form.description}
            onChange={(event) =>
              setForm({ ...form, description: event.target.value })
            }
            placeholder="Describe what happened and provide any useful context..."
            className={`${inputClassName} resize-y`}
          />

          <p className="mt-2 text-[11px] text-slate-400">
            Include enough detail to help the team understand the issue.
          </p>
        </div>
      </section>

      <div className="h-px bg-[#edf0f4]" />

      {/* Technical context */}
      <section className="space-y-5">
        <div>
          <h2 className="text-sm font-semibold text-[#263750]">
            Technical context
          </h2>

          <p className="mt-1 text-xs text-slate-500">
            These details help our team investigate the report. They are
            optional, but useful.
          </p>
        </div>

        <div>
          <label htmlFor="environment" className={labelClassName}>
            Environment
          </label>

          <input
            id="environment"
            name="environment"
            type="text"
            value={form.environment}
            onChange={(event) =>
              setForm({ ...form, environment: event.target.value })
            }
            placeholder="e.g. Windows 11, Chrome 130"
            className={inputClassName}
          />
        </div>

        <div>
          <label htmlFor="steps_to_reproduce" className={labelClassName}>
            Steps to reproduce
          </label>

          <textarea
            id="steps_to_reproduce"
            name="steps_to_reproduce"
            rows={4}
            value={form.steps_to_reproduce}
            onChange={(event) =>
              setForm({
                ...form,
                steps_to_reproduce: event.target.value,
              })
            }
            placeholder={"1. Open the application\n2. Navigate to...\n3. Perform the action..."}
            className={`${inputClassName} resize-y`}
          />
        </div>

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <div>
            <label htmlFor="expected_behavior" className={labelClassName}>
              Expected behaviour
            </label>

            <textarea
              id="expected_behavior"
              name="expected_behavior"
              rows={4}
              value={form.expected_behavior}
              onChange={(event) =>
                setForm({
                  ...form,
                  expected_behavior: event.target.value,
                })
              }
              placeholder="What should have happened?"
              className={`${inputClassName} resize-y`}
            />
          </div>

          <div>
            <label htmlFor="actual_behavior" className={labelClassName}>
              Actual behaviour
            </label>

            <textarea
              id="actual_behavior"
              name="actual_behavior"
              rows={4}
              value={form.actual_behavior}
              onChange={(event) =>
                setForm({
                  ...form,
                  actual_behavior: event.target.value,
                })
              }
              placeholder="What actually happened?"
              className={`${inputClassName} resize-y`}
            />
          </div>
        </div>
      </section>

      {/* System-managed classification */}
      <div className="flex gap-3 rounded-xl border border-[#e4eaf2] bg-[#f7f9fc] p-4">
        <ClipboardCheck
          size={19}
          className="mt-0.5 shrink-0 text-[#587eaf]"
        />

        <div>
          <p className="text-xs font-semibold text-[#34465f]">
            Our triage team handles classification
          </p>

          <p className="mt-1 text-xs leading-5 text-slate-500">
            Ticket category, priority and processing status are determined
            by the system. You do not need to select them.
          </p>
        </div>
      </div>

      {/* Submission error */}
      {error && (
        <div
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 p-4"
        >
          <p className="text-sm font-semibold text-red-700">
            Submission unsuccessful
          </p>

          <p className="mt-1 text-xs leading-5 text-red-600">
            {error}
          </p>
        </div>
      )}

      {/* Submit */}
      <div className="border-t border-[#edf0f4] pt-6">
        <button
          type="submit"
          disabled={submitting}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#294b76] px-6 py-3.5 text-sm font-semibold text-white transition-colors hover:bg-[#203d61] disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
        >
          {submitting ? (
            <>
              <LoaderCircle size={17} className="animate-spin" />
              Submitting report...
            </>
          ) : (
            <>
              Submit report
              <ArrowRight size={17} />
            </>
          )}
        </button>

        <p className="mt-3 text-[11px] leading-5 text-slate-400">
          By submitting, you are providing the information needed for our
          team to review your report.
        </p>
      </div>
    </form>
  );
}