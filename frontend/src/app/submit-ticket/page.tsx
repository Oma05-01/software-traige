import Link from "next/link";
import {
  ArrowLeft,
  ClipboardList,
  ShieldCheck,
} from "lucide-react";

import { TicketSubmissionForm } from "@/components/tickets/ticket-submission-form";

export default function SubmitTicketPage() {
  return (
    <main className="min-h-screen bg-[#f6f8fb] px-4 py-8 sm:px-6 sm:py-12 lg:px-8">
      <div className="mx-auto max-w-3xl">

        {/* Brand header */}
        <header className="mb-10 flex items-center justify-between">
          <Link
            href="/submit-ticket"
            className="flex items-center gap-3"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#294b76] text-white">
              <ClipboardList size={21} />
            </div>

            <div>
              <p className="text-sm font-bold text-[#263750]">
                Software Triage Team
              </p>

              <p className="text-[10px] text-slate-400">
                Issue reporting portal
              </p>
            </div>
          </Link>

          <Link
            href="/login"
            className="text-xs font-medium text-slate-500 transition-colors hover:text-[#294b76]"
          >
            Staff sign in
          </Link>
        </header>

        {/* Page heading */}
        <section className="mb-8">
          <Link
            href="/submit-ticket"
            className="mb-6 inline-flex items-center gap-2 text-xs text-slate-400 transition-colors hover:text-[#294b76]"
          >
            <ArrowLeft size={14} />
            Issue reporting
          </Link>

          <div className="mb-4">
            <span className="rounded-full bg-[#eaf0f8] px-3 py-1.5 text-[10px] font-semibold tracking-wider text-[#587eaf] uppercase">
              Public support portal
            </span>
          </div>

          <h1 className="text-3xl font-semibold tracking-tight text-[#263750] sm:text-4xl">
            Tell us what happened.
          </h1>

          <p className="mt-3 max-w-xl text-sm leading-7 text-slate-500">
            Report a software issue or suggest an improvement. Provide as
            much relevant information as possible so our triage team can
            investigate effectively.
          </p>
        </section>

        {/* Submission form */}
        <div className="rounded-3xl border border-[#e5ebf3] bg-white p-5 shadow-[0_8px_35px_rgba(30,50,80,0.04)] sm:p-8 lg:p-10">
          <TicketSubmissionForm />
        </div>

        {/* Trust note */}
        <footer className="mt-8 flex items-start justify-center gap-2 text-center">
          <ShieldCheck
            size={16}
            className="mt-0.5 shrink-0 text-slate-400"
          />

          <p className="max-w-md text-[11px] leading-5 text-slate-400">
            Your report is submitted to our internal triage workflow.
            Category, priority and agent processing are handled by the
            application.
          </p>
        </footer>

        <p className="mt-6 text-center text-[10px] text-slate-400">
          Software Triage Team
        </p>
      </div>
    </main>
  );
}