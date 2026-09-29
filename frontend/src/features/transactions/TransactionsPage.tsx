import { lazy, Suspense } from "react";

import { TransactionsLive } from "./TransactionsLive";

const Fixture = import.meta.env.DEV ? lazy(() => import("./TransactionsFixture")) : null;

export function TransactionsPage() {
  if (!Fixture) return <TransactionsLive />;
  return (
    <Suspense fallback={<p className="text-sm text-ink-secondary">Loading the development preview…</p>}>
      <Fixture />
    </Suspense>
  );
}
