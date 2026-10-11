import { lazy, Suspense } from "react";
import type { Sample } from "./api";

const SignalChart = lazy(() => import("./SignalChart"));
export function Chart({ samples }: { samples: Sample[] }) {
  return (
    <Suspense
      fallback={
        <div className="chart chart-empty" role="status">
          Loading chart…
        </div>
      }
    >
      <SignalChart samples={samples} />
    </Suspense>
  );
}
