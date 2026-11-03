import { Suspense } from "react";

import { TicketDetailsClient } from "@/components/tickets/ticket-details-client";

interface TicketDetailsPageProps {
  params: Promise<{
    ticketId: string;
  }>;
}

async function TicketDetailsContent({
  params,
}: TicketDetailsPageProps) {
  const { ticketId } = await params;

  return <TicketDetailsClient ticketId={ticketId} />;
}

function TicketDetailsFallback() {
  return (
    <div className="flex min-h-64 items-center justify-center text-sm text-slate-500">
      Loading ticket...
    </div>
  );
}

export default function TicketDetailsPage({
  params,
}: TicketDetailsPageProps) {
  return (
    <Suspense fallback={<TicketDetailsFallback />}>
      <TicketDetailsContent params={params} />
    </Suspense>
  );
}