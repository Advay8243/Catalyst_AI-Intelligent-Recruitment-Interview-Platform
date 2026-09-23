import { Suspense } from "react";
import { ScreeningClient } from "@/components/screening-client";
import { Skeleton } from "@/components/ui";

export default function ScreeningPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-[1500px] space-y-5 p-8">
          <Skeleton className="h-24 rounded-xl" />
          <Skeleton className="h-40 rounded-xl" />
          <Skeleton className="h-96 rounded-xl" />
        </div>
      }
    >
      <ScreeningClient />
    </Suspense>
  );
}
