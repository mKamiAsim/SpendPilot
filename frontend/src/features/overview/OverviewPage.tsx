import { lazy, Suspense } from "react";

import { OverviewLive } from "./OverviewLive";

const Fixture = import.meta.env.DEV ? lazy(() => import("./OverviewFixture")) : null;

export function OverviewPage() {
  if (!Fixture) return <OverviewLive />;
  return (
    <Suspense fallback={<p className="text-sm text-ink-secondary">Loading the development preview…</p>}>
      <Fixture />
    </Suspense>
  );
}
