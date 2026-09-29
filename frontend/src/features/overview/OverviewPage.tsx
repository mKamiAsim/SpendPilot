import { lazy, Suspense } from "react";

import { EmptyProduct } from "../preview/EmptyProduct";

const Fixture = import.meta.env.DEV ? lazy(() => import("./OverviewFixture")) : null;

export function OverviewPage() {
  if (!Fixture) return <EmptyProduct title="Overview" />;
  return (
    <Suspense fallback={<p className="text-sm text-ink-secondary">Loading the development preview…</p>}>
      <Fixture />
    </Suspense>
  );
}
