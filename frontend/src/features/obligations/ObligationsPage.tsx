import { FormEvent, useEffect, useState } from "react";

import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { ApiRequestError, api, readJson } from "../../lib/api";

type Plan = {
  id: string;
  description: string;
  category: string;
  principal: string;
  parts: number;
  monthly_amount: string;
  posted_on: string;
  remaining: string;
  repaid: string;
};

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
  "Cash",
  "Other",
];

export function ObligationsPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [commitment, setCommitment] = useState("0.00");
  const [categories, setCategories] = useState(locked);
  const [error, setError] = useState("");
  const [description, setDescription] = useState("");
  const [principal, setPrincipal] = useState("");
  const [parts, setParts] = useState("12");
  const [postedOn, setPostedOn] = useState("");
  const [category, setCategory] = useState("Shopping");
  const [repayments, setRepayments] = useState<Record<string, string>>({});

  async function load() {
    const [body, cats] = await Promise.all([
      readJson<{ plans: Plan[]; monthly_commitment: string }>(await api("/api/v1/obligations")),
      readJson<{ categories: string[]; custom: string[] }>(await api("/api/v1/categories")),
    ]);
    setPlans(body.plans);
    setCommitment(body.monthly_commitment);
    setCategories([...cats.categories.filter((item) => item !== "Income"), ...cats.custom]);
  }

  useEffect(() => {
    load().catch((exc: unknown) => setError(exc instanceof ApiRequestError ? exc.message : "Obligations could not be loaded."));
  }, []);

  async function addPlan(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await readJson(
        await api("/api/v1/instalments", {
          method: "POST",
          body: JSON.stringify({
            description,
            category,
            principal,
            parts: Number(parts),
            posted_on: postedOn,
          }),
        }),
      );
      setDescription("");
      setPrincipal("");
      await load();
    } catch (exc) {
      setError(exc instanceof ApiRequestError ? exc.message : "The instalment could not be saved.");
    }
  }

  return (
    <section className="mx-auto min-w-0 max-w-3xl">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-secondary">SpendPilot</p>
      <h1 className="mt-2 text-[1.75rem] font-semibold leading-tight">Obligations</h1>
      <p className="mt-3 text-sm text-ink-secondary">
        A purchase on a plan is counted once. Each repayment reduces what is left. It is not extra spending.
      </p>
      <p className="mt-4 text-sm">Monthly commitment {commitment} AED</p>
      {error ? <p className="mt-4 text-sm text-bad">{error}</p> : null}
      <form onSubmit={addPlan} className="mt-6 grid min-w-0 gap-4 rounded-xl border border-line bg-surface p-4 sm:p-6">
        <h2 className="text-base font-medium">Add an instalment purchase</h2>
        <div className="grid gap-2">
          <Label htmlFor="plan-description">Description</Label>
          <Input id="plan-description" value={description} onChange={(event) => setDescription(event.target.value)} required />
        </div>
        <div className="grid min-w-0 gap-2 sm:grid-cols-3">
          <div className="grid gap-2">
            <Label htmlFor="plan-principal">Principal AED</Label>
            <Input id="plan-principal" inputMode="decimal" value={principal} onChange={(event) => setPrincipal(event.target.value)} required />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="plan-parts">Parts</Label>
            <Input id="plan-parts" inputMode="numeric" value={parts} onChange={(event) => setParts(event.target.value)} required />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="plan-date">Posted on</Label>
            <Input id="plan-date" type="date" value={postedOn} onChange={(event) => setPostedOn(event.target.value)} required />
          </div>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="plan-category">Category</Label>
          <select
            id="plan-category"
            className="h-11 rounded-lg border border-line bg-canvas px-2 text-sm"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            {categories.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </div>
        <Button type="submit">Save purchase</Button>
      </form>
      <ul className="mt-6 grid gap-3">
        {plans.map((plan) => (
          <li key={plan.id} className="rounded-xl border border-line bg-surface p-4">
            <p className="font-medium">{plan.description}</p>
            <p className="mt-1 text-sm text-ink-secondary">
              {plan.posted_on} · {plan.category} · {plan.parts} parts
            </p>
            <dl className="mt-3 grid gap-1 text-sm">
              <div className="flex flex-wrap justify-between gap-x-4">
                <dt className="text-ink-secondary">Purchase, counted once</dt>
                <dd>{plan.principal} AED</dd>
              </div>
              <div className="flex flex-wrap justify-between gap-x-4">
                <dt className="text-ink-secondary">Monthly</dt>
                <dd>{plan.monthly_amount} AED</dd>
              </div>
              <div className="flex flex-wrap justify-between gap-x-4">
                <dt className="text-ink-secondary">Repaid</dt>
                <dd>{plan.repaid} AED</dd>
              </div>
              <div className="flex flex-wrap justify-between gap-x-4">
                <dt className="text-ink-secondary">Remaining</dt>
                <dd>{plan.remaining} AED</dd>
              </div>
            </dl>
            <form
              className="mt-3 flex flex-wrap items-end gap-2"
              onSubmit={async (event) => {
                event.preventDefault();
                setError("");
                try {
                  await readJson(
                    await api(`/api/v1/instalments/${plan.id}/repayments`, {
                      method: "POST",
                      body: JSON.stringify({
                        posted_on: new Date().toISOString().slice(0, 10),
                        amount: repayments[plan.id] ?? "",
                      }),
                    }),
                  );
                  setRepayments((current) => ({ ...current, [plan.id]: "" }));
                  await load();
                } catch (exc) {
                  setError(exc instanceof ApiRequestError ? exc.message : "The repayment could not be saved.");
                }
              }}
            >
              <div className="grid gap-2">
                <Label htmlFor={`repay-${plan.id}`}>Repayment AED</Label>
                <Input
                  id={`repay-${plan.id}`}
                  inputMode="decimal"
                  value={repayments[plan.id] ?? ""}
                  onChange={(event) => setRepayments({ ...repayments, [plan.id]: event.target.value })}
                />
              </div>
              <Button type="submit" variant="secondary">
                Record repayment
              </Button>
            </form>
          </li>
        ))}
      </ul>
    </section>
  );
}
