import { Suspense } from "react";

import { ReviewDetailsClient } from "@/components/reviews/review-details-client";

interface ReviewDetailsPageProps {
  params: Promise<{
    reviewId: string;
  }>;
}

async function ReviewDetailsContent({
  params,
}: ReviewDetailsPageProps) {
  const { reviewId } = await params;

  return <ReviewDetailsClient reviewId={reviewId} />;
}

function ReviewDetailsFallback() {
  return (
    <div className="flex min-h-64 items-center justify-center text-sm text-slate-500">
      Loading review...
    </div>
  );
}

export default function ReviewDetailsPage({
  params,
}: ReviewDetailsPageProps) {
  return (
    <Suspense fallback={<ReviewDetailsFallback />}>
      <ReviewDetailsContent params={params} />
    </Suspense>
  );
}