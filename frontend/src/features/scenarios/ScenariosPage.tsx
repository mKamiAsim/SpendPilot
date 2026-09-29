import { FormEvent, useState } from "react";

import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
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
  "Cash",
  "Other",
];

type Scenario = {
  id: string;
  category: string;
  baseline: string;
  reduction: string;
  proposed: string;
  calculation_id: string;
  income_total: string;
  affordability_amount: string | null;
  affordability_blocked: boolean;
};

export function ScenariosPage() {
  const [category, setCategory] = useState("Groceries");
  const [reduction, setReduction] = useState("10.00");
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [target, setTarget] = useState<{ id: string; status: string } | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function calculate(event: FormEvent) {
    event.preventDefault();
    setError("");
    setTarget(null);
    setPending(true);
    try {
      const body = await readJson<Scenario>(
        await api("/api/v1/scenarios", {
          method: "POST",
          body: JSON.stringify({ category, reduction }),
        }),
      );
      setScenario(body);
    } catch (exc) {
      setError(exc instanceof ApiRequestError ? exc.message : "The scenario could not be calculated.");
    } finally {
      setPending(false);
    }
  }

  async function stage() {
    if (!scenario) return;
    setError("");
    try {
      const body = await readJson<{ id: string; status: string }>(
        await api(`/api/v1/scenarios/${scenario.id}/target`, { method: "POST" }),
      );
      setTarget(body);
    } catch (exc) {
      setError(exc instanceof ApiRequestError ? exc.message : "The target could not be staged.");
    }
  }

  async function accept() {
    if (!target) return;
    setError("");
    try {
      const body = await readJson<{ id: string; status: string }>(
        await api(`/api/v1/targets/${target.id}/accept`, { method: "POST" }),
      );
      setTarget(body);
    } catch (exc) {
      setError(exc instanceof ApiRequestError ? exc.message : "The target could not be accepted.");
    }
  }

  return (
    <section className="mx-auto grid max-w-3xl gap-4">
      <div>
        <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-secondary">SpendPilot</p>
        <h1 className="mt-2 text-[1.75rem] font-semibold leading-tight">Scenarios</h1>
        <p className="mt-3 text-sm text-ink-secondary">
          Calculate a category reduction, then accept a target only if you want it kept. The calculation is not the
          acceptance.
        </p>
      </div>
      <form onSubmit={calculate} className="grid gap-4 rounded-xl border border-line bg-surface p-4 sm:grid-cols-2">
        <div className="grid gap-2">
          <Label htmlFor="scenario-category">Category</Label>
          <select
            id="scenario-category"
            className="h-11 rounded-lg border border-line bg-canvas px-3 text-sm"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            {categories.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="scenario-reduction">Reduction, AED</Label>
          <Input id="scenario-reduction" value={reduction} onChange={(event) => setReduction(event.target.value)} />
        </div>
        <Button type="submit" disabled={pending}>
          Calculate
        </Button>
      </form>
      {error ? <p className="text-sm text-bad">{error}</p> : null}
      {scenario ? (
        <article className="rounded-xl border border-line bg-surface p-4 text-sm">
          <p>
            {scenario.category} baseline {scenario.baseline} AED. Proposed {scenario.proposed} AED. Calculation{" "}
            {scenario.calculation_id}.
          </p>
          {scenario.affordability_blocked ? (
            <p className="mt-3">Income is not in this snapshot, so this is not an affordability claim.</p>
          ) : (
            <p className="mt-3">
              Leftover after the reduced net spending is {scenario.affordability_amount} AED. Income in the snapshot is{" "}
              {scenario.income_total} AED.
            </p>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            <Button type="button" variant="secondary" onClick={stage}>
              Stage target
            </Button>
            <Button type="button" onClick={accept} disabled={!target || target.status === "accepted"}>
              Accept target
            </Button>
          </div>
          {target ? <p className="mt-3 text-ink-secondary">Target {target.status}.</p> : null}
        </article>
      ) : null}
    </section>
  );
}
