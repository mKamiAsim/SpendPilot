import { flexRender } from "@tanstack/react-table";
import { getCoreRowModel, useLegacyTable, type LegacyColumnDef } from "@tanstack/react-table/legacy";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router";

import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { formatDate } from "../preview/format";
import { cards, transactions, type FixtureTransaction } from "../preview/fixtures";
import { FixtureBanner, UnavailableNote } from "../preview/states";
import { AccountBadge, EvidenceDrawer, MoneyValue } from "../preview/ui";

const categories = ["Groceries", "Dining", "Transport", "Shopping", "Fees and interest", "Other", "Transfers"];

export default function TransactionsFixture() {
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const [card, setCard] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);
  const [checked, setChecked] = useState<string[]>([]);
  const [blocked, setBlocked] = useState(false);
  const category = params.get("category") ?? "all";

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return transactions.filter((row) => {
      if (category !== "all" && row.category !== category) return false;
      if (card !== "all" && row.card !== card) return false;
      if (!needle) return true;
      return row.description.toLowerCase().includes(needle) || row.category.toLowerCase().includes(needle);
    });
  }, [query, category, card]);

  const columns = useMemo<LegacyColumnDef<FixtureTransaction>[]>(
    () => [
      {
        id: "select",
        header: "",
        cell: ({ row }) => (
          <input
            type="checkbox"
            className="h-4 w-4"
            aria-label={`Select ${row.original.description}`}
            checked={checked.includes(row.original.id)}
            onChange={() =>
              setChecked((current) =>
                current.includes(row.original.id)
                  ? current.filter((id) => id !== row.original.id)
                  : [...current, row.original.id],
              )
            }
            onClick={(event) => event.stopPropagation()}
          />
        ),
      },
      { accessorKey: "date", header: "Date", cell: (info) => formatDate(String(info.getValue())) },
      {
        accessorKey: "description",
        header: "Description",
        cell: ({ row }) => (
          <span dir={row.original.arabic ? "auto" : undefined}>{row.original.description}</span>
        ),
      },
      { accessorKey: "category", header: "Category" },
      {
        accessorKey: "card",
        header: "Card",
        cell: ({ row }) => <AccountBadge name={row.original.card} />,
      },
      { accessorKey: "type", header: "Type" },
      {
        accessorKey: "amount",
        header: () => <span className="block text-right">Amount</span>,
        cell: ({ row }) => (
          <span className="block text-right">
            <MoneyValue value={row.original.amount} />
          </span>
        ),
      },
    ],
    [checked],
  );

  const table = useLegacyTable({ data: filtered, columns, getCoreRowModel: getCoreRowModel() });
  const open = filtered.find((row) => row.id === selected) ?? null;

  function setCategory(next: string) {
    const copy = new URLSearchParams(params);
    if (next === "all") copy.delete("category");
    else copy.set("category", next);
    setParams(copy);
  }

  return (
    <div>
      <FixtureBanner />
      <header className="mb-4">
        <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-secondary">Money</p>
        <h1 className="mt-1 text-[1.75rem] font-semibold">Transactions</h1>
        <p className="mt-2 max-w-2xl text-sm text-ink-secondary">
          September 2026 statement cycle. Payments stay visible and are marked so they are not treated as spending.
        </p>
      </header>
      <div className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-3">
        <div className="grid gap-2 md:grid-cols-4">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search description"
            aria-label="Search description"
          />
          <select className="h-11 rounded-lg border border-line bg-surface px-3 text-sm" aria-label="Date range" defaultValue="september">
            <option value="september">1 Sep 2026 – 30 Sep 2026</option>
          </select>
          <select className="h-11 rounded-lg border border-line bg-surface px-3 text-sm" aria-label="Card" value={card} onChange={(event) => setCard(event.target.value)}>
            <option value="all">All cards</option>
            <option value={cards.everyday}>{cards.everyday}</option>
            <option value={cards.travel}>{cards.travel}</option>
          </select>
          <select className="h-11 rounded-lg border border-line bg-surface px-3 text-sm" aria-label="Category" value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="all">All categories</option>
            {categories.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {category !== "all" ? (
            <button type="button" className="h-11 rounded-lg bg-surface-secondary px-3 text-sm" onClick={() => setCategory("all")}>
              {category} ×
            </button>
          ) : null}
          {card !== "all" ? (
            <button type="button" className="h-11 rounded-lg bg-surface-secondary px-3 text-sm" onClick={() => setCard("all")}>
              {card} ×
            </button>
          ) : null}
          {query ? (
            <button type="button" className="h-11 rounded-lg bg-surface-secondary px-3 text-sm" onClick={() => setQuery("")}>
              “{query}” ×
            </button>
          ) : null}
          <button
            type="button"
            className="h-9 px-2 text-sm text-ink-secondary underline"
            onClick={() => {
              setQuery("");
              setCard("all");
              setCategory("all");
            }}
          >
            Reset
          </button>
        </div>
      </div>

      {checked.length > 0 ? (
        <div className="mt-3 flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface-secondary px-3 py-2 text-sm">
          <span>{checked.length} selected</span>
          <Button type="button" size="sm" variant="secondary" onClick={() => setBlocked(true)}>
            Change category
          </Button>
        </div>
      ) : null}

      <div className="mt-4 hidden overflow-x-auto rounded-xl border border-line bg-surface md:block">
        <table className="w-full min-w-[720px] border-collapse text-sm">
          <thead className="sticky top-0 bg-surface">
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id} className="border-b border-line text-left text-ink-secondary">
                {group.headers.map((header) => (
                  <th key={header.id} className="px-3 py-3 font-medium">
                    {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                className="cursor-pointer border-b border-line last:border-0"
                onClick={() => setSelected(row.original.id)}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="h-14 px-3">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 ? <p className="px-3 py-6 text-sm text-ink-secondary">No rows match these filters.</p> : null}
      </div>

      <ul className="mt-4 flex flex-col gap-3 md:hidden">
        {filtered.map((row) => (
          <li key={row.id}>
            <button
              type="button"
              className="w-full rounded-xl border border-line bg-surface p-4 text-left"
              onClick={() => setSelected(row.id)}
            >
              <span className="flex items-start justify-between gap-3">
                <span>
                  <span className="block text-xs text-ink-secondary">{formatDate(row.date)}</span>
                  <span className="mt-1 block font-medium" dir={row.arabic ? "auto" : undefined}>
                    {row.description}
                  </span>
                  <span className="mt-1 block text-sm text-ink-secondary">
                    {row.category} · {row.type}
                  </span>
                </span>
                <MoneyValue value={row.amount} />
              </span>
              <span className="mt-3 block">
                <AccountBadge name={row.card} />
              </span>
            </button>
          </li>
        ))}
        {filtered.length === 0 ? <li className="text-sm text-ink-secondary">No rows match these filters.</li> : null}
      </ul>

      <EvidenceDrawer row={open} onClose={() => setSelected(null)} />
      {blocked ? (
        <UnavailableNote
          title="Category changes are not in this preview"
          detail="Corrections wait until statement import exists. This fixture will not pretend a category was saved."
          onClose={() => setBlocked(false)}
        />
      ) : null}
    </div>
  );
}
