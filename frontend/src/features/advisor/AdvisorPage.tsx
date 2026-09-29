import { lazy, Suspense } from "react";

import { EmptyProduct } from "../preview/EmptyProduct";

const Fixture = import.meta.env.DEV ? lazy(() => import("./AdvisorFixture")) : null;

export function AdvisorPage() {
  if (!Fixture) return <EmptyProduct title="Advisor" />;
  return (
    <Suspense fallback={<p className="text-sm text-ink-secondary">Loading the development preview…</p>}>
      <Fixture />
    </Suspense>
  );
}
