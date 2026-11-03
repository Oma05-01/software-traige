import { ReviewQueueClient } from "@/components/reviews/review-queue-client";

export default function ReviewsPage() {
  return (
    <div className="space-y-8">
      <section>
        <div className="mb-3 flex items-center gap-2 text-[10px] font-semibold tracking-[0.17em] text-slate-400 uppercase">
          <span>Workspace</span>
          <span>/</span>
          <span className="text-[#587eaf]">Human review</span>
        </div>

        <h1 className="text-2xl font-semibold tracking-tight text-[#263750] sm:text-3xl">
          Human review
        </h1>

        <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">
          Inspect proposed agent actions, review their supporting
          information and make approval decisions.
        </p>
      </section>

      <ReviewQueueClient />
    </div>
  );
}