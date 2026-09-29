import { useEffect, useState } from "react";

import { EmptyProduct } from "../preview/EmptyProduct";
import { ApiRequestError, api, readJson } from "../../lib/api";

type Transaction = {
  id: string;
  posted_on: string;
  description: string;
  category: string;
  entry_type: string;
  amount: string;
  card_last4: string | null;
};

export function TransactionsLive() {
  const [rows, setRows] = useState<Transaction[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/api/v1/transactions")
      .then((response) => readJson<{ transactions: Transaction[] }>(response))
      .then((body) => setRows(body.transactions))
      .catch((exc: unknown) => setError(exc instanceof ApiRequestError ? exc.message : "Transactions could not be loaded."));
  }, []);

  if (error) {
    return (
      <section className="mx-auto max-w-3xl">
        <h1 className="text-[1.75rem] font-semibold">Transactions</h1>
        <p className="mt-4 text-sm text-bad">{error}</p>
      </section>
    );
  }
  if (!rows || rows.length === 0) return <EmptyProduct title="Transactions" />;
  return (
    <section className="mx-auto max-w-3xl">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-secondary">SpendPilot</p>
      <h1 className="mt-2 text-[1.75rem] font-semibold leading-tight">Transactions</h1>
      <p className="mt-3 text-sm text-ink-secondary">Posted amounts from accepted statements. These figures are not a live balance.</p>
      <ul className="mt-6 grid gap-2">
        {rows.map((row) => (
          <li key={row.id} className="grid grid-cols-[1fr_auto] gap-3 rounded-xl border border-line bg-surface px-4 py-3 text-sm">
            <div>
              <p className="font-medium">{row.description}</p>
              <p className="text-ink-secondary">
                {row.posted_on} · {row.category} · {row.entry_type.replaceAll("_", " ")}
                {row.card_last4 ? ` · ··${row.card_last4}` : ""}
              </p>
            </div>
            <p className="font-medium">{row.amount} AED</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
