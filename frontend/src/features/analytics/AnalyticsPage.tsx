import { useEffect, useState } from "react";
import { Link } from "react-router";

import { ApiRequestError, api, readJson } from "../../lib/api";

type Summary = {
  gross_purchases: string;
  refunds: string;
  cash_purchases: string;
  instalment_purchases: string;
  net_spending: string;
  fees: string;
  interest: string;
  payments: string;
  transfers: string;
  cash_withdrawals: string;
  cashback: string;
  statement_count: number;
  includes_accepted_discrepancy: boolean;
};

type Coverage = {
  complete: boolean;
  months_covered: number;
  gaps: string[];
  partial_periods: { period_start: string; period_end: string }[];
  note: string;
};

const rows: { key: keyof Summary; label: string }[] = [
  { key: "net_spending", label: "Net spending" },
  { key: "gross_purchases", label: "Card purchases" },
  { key: "instalment_purchases", label: "Instalment purchases" },
  { key: "refunds", label: "Refunds" },
  { key: "cash_purchases", label: "Cash purchases" },
  { key: "payments", label: "Card payments" },
  { key: "transfers", label: "Transfers" },
  { key: "cash_withdrawals", label: "Cash withdrawals" },
  { key: "fees", label: "Fees" },
  { key: "interest", label: "Interest" },
];

export function AnalyticsPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api("/api/v1/analytics/summary").then((response) => readJson<Summary>(response)),
      api("/api/v1/analytics/coverage").then((response) => readJson<Coverage>(response)),
    ])
      .then(([totals, months]) => {
        setSummary(totals);
        setCoverage(months);
      })
      .catch((exc: unknown) => setError(exc instanceof ApiRequestError ? exc.message : "Analytics could not be loaded."));
  }, []);

  return (
    <section className="mx-auto max-w-3xl">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-secondary">SpendPilot</p>
      <h1 className="mt-2 text-[1.75rem] font-semibold leading-tight">Analytics</h1>
      <p className="mt-3 text-sm text-ink-secondary">
        Posted amounts only. Card payments, transfers, and cash withdrawals are not spending. An instalment purchase is
        counted once. These figures stay available when the model is off.
      </p>
      {error ? <p className="mt-4 text-sm text-bad">{error}</p> : null}
      {coverage ? (
        <p className="mt-4 text-sm">
          {coverage.note} {coverage.months_covered} month{coverage.months_covered === 1 ? "" : "s"} posted.
          {coverage.gaps.length > 0 ? ` Missing ${coverage.gaps.join(", ")}.` : ""}
          {coverage.partial_periods.length > 0 ? " A partial period is marked." : ""}
        </p>
      ) : null}
      <table className="mt-6 w-full text-sm">
        <caption className="sr-only">Posted totals in AED</caption>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key} className="border-b border-line">
              <th scope="row" className="py-3 text-left font-normal text-ink-secondary">
                {row.label}
              </th>
              <td className="py-3 text-right font-medium">{summary ? `${summary[row.key]} AED` : "…"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {summary?.includes_accepted_discrepancy ? (
        <p className="mt-4 text-sm text-ink-secondary">One statement was accepted with a difference.</p>
      ) : null}
      <Link className="mt-6 inline-flex text-sm underline" to="/money/obligations">
        Open obligations
      </Link>
    </section>
  );
}
