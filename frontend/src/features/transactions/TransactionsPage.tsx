import { lazy, Suspense } from "react";

import { EmptyProduct } from "../preview/EmptyProduct";

const Fixture = import.meta.env.DEV ? lazy(() => import("./TransactionsFixture")) : null;

export function TransactionsPage() {
  if (!Fixture) return <EmptyProduct title="Transactions" />;
  return (
    <Suspense fallback={<p className="text-sm text-ink-secondary">Loading the development preview…</p>}>
      <Fixture />
    </Suspense>
  );
}
