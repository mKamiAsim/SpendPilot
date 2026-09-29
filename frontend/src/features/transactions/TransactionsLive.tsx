import { useEffect, useState } from "react";

import { Button } from "../../components/ui/button";
import { EmptyProduct } from "../preview/EmptyProduct";
import { ApiRequestError, api, readJson } from "../../lib/api";

const categories = [
  "Groceries",
  "Dining",
  "Transport",
  "Utilities",
  "Shopping",
  "Health",
  "Entertainment",
  "Travel",
  "Fees and interest",
  "Transfers",
  "Income",
  "Cash",
  "Other",
];

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
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [staged, setStaged] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");

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
      {note ? <p className="mt-4 text-sm">{note}</p> : null}
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
            {row.entry_type === "purchase" ? (
              <form
                className="col-span-2 flex flex-wrap items-center gap-2"
                onSubmit={async (event) => {
                  event.preventDefault();
                  setError("");
                  setNote("");
                  try {
                    const category = drafts[row.id] || row.category;
                    const correction = await readJson<{ id: string }>(
                      await api("/api/v1/corrections", {
                        method: "POST",
                        body: JSON.stringify({ transaction_id: row.id, category }),
                      }),
                    );
                    setStaged((current) => ({ ...current, [row.id]: correction.id }));
                    setNote("Correction staged. The posted category is unchanged until you confirm it.");
                  } catch (exc) {
                    setError(exc instanceof ApiRequestError ? exc.message : "The correction could not be staged.");
                  }
                }}
              >
                <label className="text-xs text-ink-secondary" htmlFor={`category-${row.id}`}>
                  Correct category
                </label>
                <select
                  id={`category-${row.id}`}
                  className="h-11 rounded-lg border border-line bg-canvas px-2 text-sm"
                  value={drafts[row.id] || row.category}
                  onChange={(event) => setDrafts({ ...drafts, [row.id]: event.target.value })}
                >
                  {categories.map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </select>
                <Button type="submit" size="sm" variant="secondary">
                  Stage
                </Button>
                {staged[row.id] ? (
                  <Button
                    type="button"
                    size="sm"
                    onClick={async () => {
                      setError("");
                      try {
                        await readJson(await api(`/api/v1/corrections/${staged[row.id]}/accept`, { method: "POST" }));
                        setRows((current) =>
                          current?.map((item) =>
                            item.id === row.id ? { ...item, category: drafts[row.id] || item.category } : item,
                          ) ?? null,
                        );
                        setNote("Correction confirmed. Affected findings are stale.");
                      } catch (exc) {
                        setError(exc instanceof ApiRequestError ? exc.message : "The correction could not be confirmed.");
                      }
                    }}
                  >
                    Confirm
                  </Button>
                ) : null}
              </form>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
