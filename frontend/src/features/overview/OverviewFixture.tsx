import { useState } from "react";
import { Link } from "react-router";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Button } from "../../components/ui/button";
import { useTheme } from "../../app/theme";
import { formatAed } from "../preview/format";
import {
  cards,
  categoryTotal,
  fees,
  instalmentPurchase,
  instalmentRepayment,
  netSpending,
  priorFees,
  priorNetSpending,
  shoppingShare,
  spendingCategories,
  transactions,
  trend,
} from "../preview/fixtures";
import { FixtureBanner, UnavailableNote } from "../preview/states";
import { ComparisonDelta, CoverageIndicator, FindingCard, MoneyValue } from "../preview/ui";

const categoryColor = {
  light: {
    Groceries: "#0f766e",
    Dining: "#b45309",
    Transport: "#0e7490",
    Shopping: "#1e3a5f",
    "Fees and interest": "#9f1239",
    Other: "#526174",
  },
  dark: {
    Groceries: "#5eead4",
    Dining: "#fbbf24",
    Transport: "#67e8f9",
    Shopping: "#93c5fd",
    "Fees and interest": "#fda4af",
    Other: "#b1bdcc",
  },
} as const;

export default function OverviewFixture() {
  const { theme } = useTheme();
  const [cycle, setCycle] = useState("2026-09");
  const [blocked, setBlocked] = useState<string | null>(null);
  const ink = theme === "dark" ? "#f1f5f9" : "#17212f";
  const muted = theme === "dark" ? "#b1bdcc" : "#526174";
  const spendingDelta = Math.round((priorNetSpending - netSpending) * 100) / 100;

  return (
    <div>
      <FixtureBanner />
      <header className="flex flex-col gap-4 border-b border-line pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-secondary">September 2026</p>
          <h1 className="mt-1 text-[1.75rem] font-semibold leading-tight">Monthly briefing</h1>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
            <label className="text-sm text-ink-secondary" htmlFor="cycle">
              Scope
            </label>
            <select
              id="cycle"
              value={cycle}
              onChange={(event) => setCycle(event.target.value)}
              className="h-11 w-full rounded-lg border border-line bg-surface px-3 text-sm sm:w-auto"
            >
              <option value="2026-09">September 2026 statement cycle</option>
              <option value="2026-08">August 2026 statement cycle</option>
            </select>
          </div>
          <div className="mt-3">
            <CoverageIndicator />
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" onClick={() => setBlocked("upload")}>
            Upload statements
          </Button>
          <Button type="button" variant="secondary" onClick={() => setBlocked("review")}>
            Run review
          </Button>
        </div>
      </header>

      {cycle !== "2026-09" ? (
        <section className="mt-6 rounded-2xl border border-line bg-surface p-6">
          <h2 className="text-lg font-semibold">No August statements in this preview</h2>
          <p className="mt-2 max-w-xl text-sm text-ink-secondary">
            There is no figure to show. Unknown is not zero, and this development preview only contains September.
          </p>
          <Button className="mt-4" type="button" variant="secondary" onClick={() => setCycle("2026-09")}>
            Back to September
          </Button>
        </section>
      ) : (
        <div className="mt-6 grid gap-6 xl:grid-cols-12">
          <section className="order-1 rounded-2xl border border-line bg-surface p-5 xl:order-none xl:col-span-8">
            <h2 className="text-xl font-semibold leading-snug">
              Shopping was {shoppingShare}% of September net spending, mostly one Noon order.
            </h2>
            <p className="mt-3 text-sm text-ink-secondary">
              Both cards have a statement dated 27–28 September 2026. Income was not imported, so this is not an
              affordability view.
            </p>
            <p className="mt-2 text-sm text-ink-secondary">
              The everyday card’s statement due of AED {formatAed(3240.15)} already includes the AED{" "}
              {formatAed(instalmentRepayment)} instalment repayment. That repayment is not added again to spending.
            </p>
            <div className="mt-4 grid gap-3">
              <FindingCard
                severity="Attention"
                title="Shopping is concentrated in one posted order"
                detail="Noon on the travel card, after a smaller refund on the next day."
                effect={`AED ${formatAed(categoryTotal("Shopping"))} net shopping · ${shoppingShare}% of net spending`}
                evidenceCount={2}
                primary={{ label: "Explore", to: "/money/transactions?category=Shopping" }}
              />
              <FindingCard
                severity="Watch"
                title="A card fee posted this cycle"
                detail="The fee is inside net spending. It is not a purchase and not a payment."
                effect={`AED ${formatAed(fees)} · AED ${formatAed(fees - priorFees)} higher than August`}
                evidenceCount={1}
                primary={{ label: "Explore", to: "/money/transactions?category=Fees%20and%20interest" }}
              />
              <FindingCard
                severity="Note"
                title="Income is missing, so affordability stays closed"
                detail="September coverage is complete for both cards. Nothing here estimates what you can afford."
                evidenceCount={0}
                primary={{ label: "Why this is closed", onClick: () => setBlocked("income") }}
              />
            </div>
          </section>

          <section className="order-3 rounded-2xl border border-line bg-surface p-5 xl:order-none xl:col-span-4">
            <h2 className="text-lg font-semibold">Coming due</h2>
            <p className="mt-1 text-sm text-ink-secondary">Observed statement amounts. Not a live balance.</p>
            <ol className="mt-4 flex flex-col gap-4">
              <li className="border-t border-line pt-3">
                <p className="text-xs text-ink-secondary">18 Oct 2026 · source 28 Sep 2026</p>
                <p className="mt-1 text-sm font-medium">{cards.everyday}</p>
                <p className="mt-1 text-sm">Statement due</p>
                <MoneyValue value={3240.15} />
              </li>
              <li className="border-t border-line pt-3">
                <p className="text-xs text-ink-secondary">18 Oct 2026 · part 5 of 12 · source 28 Sep 2026</p>
                <p className="mt-1 text-sm font-medium">Instalment repayment</p>
                <MoneyValue value={instalmentRepayment} />
                <p className="mt-1 text-sm text-ink-secondary">
                  Included in the everyday statement due. The original AED {formatAed(instalmentPurchase)} purchase posted
                  in May and is not in September spending.
                </p>
              </li>
              <li className="border-t border-line pt-3">
                <p className="text-xs text-ink-secondary">22 Oct 2026 · source 27 Sep 2026</p>
                <p className="mt-1 text-sm font-medium">{cards.travel}</p>
                <p className="mt-1 text-sm">Statement due</p>
                <MoneyValue value={1650.4} />
              </li>
            </ol>
          </section>

          <section className="order-2 grid gap-3 sm:grid-cols-3 xl:order-none xl:col-span-12">
            <article className="rounded-xl border border-line bg-surface p-4">
              <h2 className="text-sm font-medium">Net spending</h2>
              <p className="mt-2">
                <MoneyValue value={netSpending} size="lg" />
              </p>
              <p className="mt-2 text-xs text-ink-secondary">September statement cycle · purchases, refunds, and fees</p>
              <ComparisonDelta label={`AED ${formatAed(spendingDelta)} less than August`} tone="neutral" />
            </article>
            <article className="rounded-xl border border-line bg-surface p-4">
              <h2 className="text-sm font-medium">Fees and interest</h2>
              <p className="mt-2">
                <MoneyValue value={fees} size="lg" />
              </p>
              <p className="mt-2 text-xs text-ink-secondary">September statement cycle</p>
              <ComparisonDelta
                label={`AED ${formatAed(fees - priorFees)} higher than August`}
                tone="attention"
              />
            </article>
            <article className="rounded-xl border border-line bg-surface p-4">
              <h2 className="text-sm font-medium">Instalment repayments</h2>
              <p className="mt-2">
                <MoneyValue value={instalmentRepayment} size="lg" />
              </p>
              <p className="mt-2 text-xs text-ink-secondary">Due 18 Oct 2026 · known from the 28 Sep statement</p>
              <ComparisonDelta label="Already inside the everyday statement due" tone="neutral" />
            </article>
          </section>

          <section className="order-4 rounded-xl border border-line bg-surface p-4 xl:order-none xl:col-span-8">
            <h2 className="text-lg font-semibold">Net spending by month</h2>
            <p className="mt-1 text-sm text-ink-secondary">Development preview history. Card payments are excluded.</p>
            <div className="mt-4 h-52 w-full min-w-0">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={trend} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <XAxis dataKey="month" tick={{ fill: muted, fontSize: 12 }} axisLine={false} tickLine={false} />
                  <YAxis
                    width={48}
                    tick={{ fill: muted, fontSize: 12 }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(value: number) => `${Math.round(value / 100) / 10}k`}
                  />
                  <Tooltip
                    formatter={(value) => [`AED ${formatAed(Number(value))}`, "Net spending"]}
                    contentStyle={{
                      background: theme === "dark" ? "#18212c" : "#ffffff",
                      border: theme === "dark" ? "1px solid #354354" : "1px solid #dce3eb",
                      borderRadius: 8,
                      color: ink,
                    }}
                  />
                  <Bar dataKey="net" fill={theme === "dark" ? "#5eead4" : "#0f766e"} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <table className="mt-4 w-full text-left text-sm">
              <caption className="mb-2 text-left text-xs text-ink-secondary">Same figures as the chart</caption>
              <thead>
                <tr className="text-ink-secondary">
                  <th className="py-1 font-medium">Month</th>
                  <th className="py-1 text-right font-medium">Net spending (AED)</th>
                </tr>
              </thead>
              <tbody>
                {trend.map((row) => (
                  <tr key={row.month} className="border-t border-line">
                    <td className="py-1">{row.month}</td>
                    <td className="money py-1 text-right">{formatAed(row.net)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="order-5 rounded-xl border border-line bg-surface p-4 xl:order-none xl:col-span-4">
            <h2 className="text-lg font-semibold">Where September went</h2>
            <ul className="mt-4 flex flex-col gap-3">
              {spendingCategories.map((category) => {
                const total = categoryTotal(category);
                const width = Math.max(4, (total / netSpending) * 100);
                return (
                  <li key={category}>
                    <div className="flex items-baseline justify-between gap-3 text-sm">
                      <Link className="underline" to={`/money/transactions?category=${encodeURIComponent(category)}`}>
                        {category}
                      </Link>
                      <span className="money">{formatAed(total)}</span>
                    </div>
                    <div className="mt-1 h-2 rounded bg-surface-secondary">
                      <div
                        className="h-2 rounded"
                        style={{ width: `${width}%`, background: categoryColor[theme][category] }}
                      />
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>

          <section className="order-6 rounded-xl border border-line bg-surface p-4 xl:order-none xl:col-span-12">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold">Recent posted rows</h2>
              <Link className="text-sm underline" to="/money/transactions">
                View all
              </Link>
            </div>
            <ul className="mt-3 divide-y divide-line">
              {transactions.slice(0, 4).map((row) => (
                <li key={row.id} className="flex items-center justify-between gap-3 py-3 text-sm">
                  <span className="min-w-0">
                    <span className="block font-medium" dir={row.arabic ? "auto" : undefined}>
                      {row.description}
                    </span>
                    <span className="text-ink-secondary">{row.category}</span>
                  </span>
                  <MoneyValue value={row.amount} />
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}

      {blocked ? (
        <UnavailableNote
          title={blocked === "income" ? "Affordability is closed" : "Not in this preview"}
          detail={
            blocked === "upload"
              ? "Statement upload starts in a later phase. These rows are a development fixture."
              : blocked === "review"
                ? "Run review needs a configured model. This preview does not call one."
                : "Income was not imported, so SpendPilot will not estimate what is affordable."
          }
          onClose={() => setBlocked(null)}
        />
      ) : null}
    </div>
  );
}
