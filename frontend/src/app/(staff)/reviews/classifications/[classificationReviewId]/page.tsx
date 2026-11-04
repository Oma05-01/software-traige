import { Suspense } from "react";

import { ClassificationReviewDetailsClient } from "@/components/reviews/classification-review-details-client";

interface ClassificationReviewPageProps {
  params: Promise<{
    classificationReviewId: string;
  }>;
}

async function ClassificationReviewPageContent({
  params,
}: ClassificationReviewPageProps) {
  const { classificationReviewId } = await params;

  return (
    <ClassificationReviewDetailsClient
      reviewId={classificationReviewId}
    />
  );
}

export default function ClassificationReviewPage({
  params,
}: ClassificationReviewPageProps) {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-64 items-center justify-center">
          <p className="text-sm text-slate-500">
            Loading classification review...
          </p>
        </div>
      }
    >
      <ClassificationReviewPageContent params={params} />
    </Suspense>
  );
}