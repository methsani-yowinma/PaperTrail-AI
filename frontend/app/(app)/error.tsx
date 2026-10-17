"use client";

import { ErrorState } from "@/components/common/states";

export default function AppError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <ErrorState
      title="This page failed to load"
      message="An unexpected error occurred while rendering this page. Try again, or return to the dashboard."
      requestId={error.digest}
      onRetry={reset}
    />
  );
}
