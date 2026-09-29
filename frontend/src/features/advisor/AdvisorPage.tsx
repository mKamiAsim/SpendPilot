import { lazy, Suspense } from "react";

import { AdvisorLive } from "./AdvisorLive";

const Fixture = import.meta.env.DEV ? lazy(() => import("./AdvisorFixture")) : null;

export function AdvisorPage() {
  if (!Fixture) return <AdvisorLive />;
  return (
    <Suspense fallback={<p className="text-sm text-ink-secondary">Loading the development preview…</p>}>
      <Fixture />
    </Suspense>
  );
}
