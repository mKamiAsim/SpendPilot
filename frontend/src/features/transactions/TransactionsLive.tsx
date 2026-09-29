import { FormEvent, useEffect, useState } from "react";

import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { ApiRequestError, api, readJson } from "../../lib/api";

const locked = [
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
  const [categories, setCategories] = useState(locked);
  const [error, setError] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [staged, setStaged] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const [manual, setManual] = useState({ posted_on: "", description: "", category: "Groceries", amount: "", kind: "expense" });

  async function load() {
    const [body, cats] = await Promise.all([
      readJson<{ transactions: Transaction[] }>(await api("/api/v1/transactions")),
      readJson<{ categories: string[]; custom: string[] }>(await api("/api/v1/categories")),
    ]);
    setRows(body.transactions);
    setCategories([...cats.categories, ...cats.custom]);
  }

  useEffect(() => {
    load().catch((exc: unknown) => setError(exc instanceof ApiRequestError ? exc.message : "Transactions could not be loaded."));
  }, []);

  async function addManual(event: FormEvent) {
    event.preventDefault();
    setError("");
    setNote("");
    try {
      await readJson(
        await api("/api/v1/cash-entries", {
          method: "POST",
          body: JSON.stringify({
            posted_on: manual.posted_on,
            description: manual.description,
            category: manual.kind === "income" ? "Income" : manual.category,
            amount: manual.amount,
          }),
        }),
      );
      setManual((current) => ({ ...current, description: "", amount: "" }));
      setNote(manual.kind === "income" ? "Income saved. It is not counted as spending." : "Cash purchase saved.");
      await load();
    } catch (exc) {
      setError(exc instanceof ApiRequestError ? exc.message : "The entry could not be saved.");
    }
  }

  if (rows === null && error) {
    return (
      <section className="mx-auto max-w-3xl">
        <h1 className="text-[1.75rem] font-semibold">Transactions</h1>
        <p className="mt-4 text-sm text-bad">{error}</p>
      </section>
    );
  }
  return (
    <section className="mx-auto max-w-3xl">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-secondary">SpendPilot</p>
      <h1 className="mt-2 text-[1.75rem] font-semibold leading-tight">Transactions</h1>
      <p className="mt-3 text-sm text-ink-secondary">
        Posted amounts from accepted statements, plus cash, income, and expenses you enter. These figures are not a live
        balance.
      </p>
      {error ? <p className="mt-4 text-sm text-bad">{error}</p> : null}
      {note ? <p className="mt-4 text-sm">{note}</p> : null}
      <form onSubmit={addManual} className="mt-6 grid gap-4 rounded-xl border border-line bg-surface p-6">
        <h2 className="text-base font-medium">Manual entry</h2>
        <fieldset className="flex flex-wrap gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="entry-kind"
              checked={manual.kind === "expense"}
              onChange={() => setManual({ ...manual, kind: "expense" })}
            />
            Expense
          </label>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="entry-kind"
              checked={manual.kind === "income"}
              onChange={() => setManual({ ...manual, kind: "income" })}
            />
            Income
          </label>
        </fieldset>
        <div className="grid gap-2 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="manual-date">Date</Label>
            <Input id="manual-date" type="date" value={manual.posted_on} onChange={(event) => setManual({ ...manual, posted_on: event.target.value })} required />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="manual-amount">Amount AED</Label>
            <Input id="manual-amount" inputMode="decimal" value={manual.amount} onChange={(event) => setManual({ ...manual, amount: event.target.value })} required />
          </div>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="manual-description">Description</Label>
          <Input id="manual-description" value={manual.description} onChange={(event) => setManual({ ...manual, description: event.target.value })} required />
        </div>
        {manual.kind === "expense" ? (
          <div className="grid gap-2">
            <Label htmlFor="manual-category">Category</Label>
            <select
              id="manual-category"
              className="h-11 rounded-lg border border-line bg-canvas px-2 text-sm"
              value={manual.category}
              onChange={(event) => setManual({ ...manual, category: event.target.value })}
            >
              {categories.filter((item) => item !== "Income").map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </div>
        ) : null}
        <Button type="submit">Save entry</Button>
      </form>
      {rows && rows.length === 0 ? (
        <p className="mt-6 text-sm text-ink-secondary">There is no statement data here.</p>
      ) : null}
      <ul className="mt-6 grid gap-2">
        {(rows ?? []).map((row) => (
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
