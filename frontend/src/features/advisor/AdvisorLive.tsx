import { FormEvent, useEffect, useState } from "react";

import { Button } from "../../components/ui/button";
import { ApiRequestError, api, readJson } from "../../lib/api";

type Evidence = {
  id: string;
  posted_on: string;
  description: string;
  category: string;
  entry_type: string;
  amount: string;
  card_last4: string | null;
};

type Finding = {
  id: string;
  title: string;
  explanation: string;
  severity: string;
  amount: string;
  calculation_id: string;
  evidence: Evidence[];
};

type Investigation = {
  id: string;
  question: string;
  status: string;
  provider_mode: string;
  live: boolean;
  failure_message: string | null;
  activity: string[];
  statements: { closing_liability: string; period_start: string; period_end: string; reconciliation: string }[];
  finding: Finding | null;
};

type ProviderState = {
  provider: { consent: string; endpoint: string; model: string } | null;
  live_provider: boolean;
};

export function AdvisorLive() {
  const [provider, setProvider] = useState<ProviderState | null>(null);
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function loadLatest() {
    const body = await readJson<{ investigations: Investigation[] }>(await api("/api/v1/investigations"));
    setInvestigation(body.investigations[0] ?? null);
  }

  useEffect(() => {
    Promise.all([
      api("/api/v1/provider").then((response) => readJson<ProviderState>(response)),
      api("/api/v1/investigations").then((response) => readJson<{ investigations: Investigation[] }>(response)),
    ])
      .then(([profile, list]) => {
        setProvider(profile);
        setInvestigation(list.investigations[0] ?? null);
      })
      .catch((exc: unknown) => setError(exc instanceof ApiRequestError ? exc.message : "The advisor could not be loaded."));
  }, []);

  async function investigateSpend(event: FormEvent) {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      const created = await readJson<Investigation>(
        await api("/api/v1/investigations", { method: "POST", body: JSON.stringify({}) }),
      );
      setInvestigation(created);
      for (let attempt = 0; attempt < 8 && created.status === "queued"; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 400));
        const next = await readJson<Investigation>(await api(`/api/v1/investigations/${created.id}`));
        setInvestigation(next);
        if (next.status !== "queued") break;
      }
    } catch (exc) {
      setError(exc instanceof ApiRequestError ? exc.message : "The investigation could not be started.");
    } finally {
      setPending(false);
      loadLatest().catch(() => undefined);
    }
  }

  const finding = investigation?.finding ?? null;
  const consent = provider?.provider?.consent;

  return (
    <section className="mx-auto grid max-w-5xl gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div>
        <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-secondary">SpendPilot</p>
        <h1 className="mt-2 text-[1.75rem] font-semibold leading-tight">Advisor</h1>
        <p className="mt-3 max-w-2xl text-sm text-ink-secondary">
          One investigation reads the frozen snapshot and publishes a finding only when the amount matches net spending.
          Payments, transfers, and cash withdrawals are not spending.
        </p>
        {provider && !provider.live_provider ? (
          <p className="mt-3 text-sm">Deterministic test provider. This is not a live model.</p>
        ) : null}
        {consent !== "selected_transactions" ? (
          <p className="mt-3 text-sm text-ink-secondary">
            Choose selected transaction details in Settings before an investigation can cite rows. Summary consent does
            not send descriptions, and consent off sends nothing.
          </p>
        ) : null}
        {error ? <p className="mt-4 text-sm text-bad">{error}</p> : null}
        <form onSubmit={investigateSpend} className="mt-4">
          <Button type="submit" disabled={pending || consent !== "selected_transactions"}>
            Investigate posted spending
          </Button>
        </form>
        {investigation?.status === "failed" ? (
          <p className="mt-4 text-sm text-bad">{investigation.failure_message}</p>
        ) : null}
        {finding ? (
          <article className="mt-6 rounded-xl border border-line bg-surface p-4">
            <p className="text-xs uppercase tracking-[0.14em] text-ink-secondary">{finding.severity}</p>
            <h2 className="mt-2 text-lg font-medium">{finding.title}</h2>
            <p className="mt-2 text-sm leading-6">{finding.explanation}</p>
            <p className="mt-3 text-sm">Net spending {finding.amount} AED</p>
            <p className="mt-1 text-xs text-ink-secondary">Calculation {finding.calculation_id}</p>
            <Button className="mt-4" type="button" variant="secondary" size="sm" onClick={() => setEvidenceOpen(true)}>
              Open evidence
            </Button>
            {investigation?.activity?.length ? (
              <ol className="mt-4 list-decimal pl-5 text-sm text-ink-secondary">
                {investigation.activity.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
            ) : null}
          </article>
        ) : null}
      </div>
      <aside
        data-testid="advisor-evidence"
        className={evidenceOpen ? "rounded-xl border border-line bg-surface p-4" : "hidden rounded-xl border border-line bg-surface p-4 xl:block"}
      >
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-base font-medium">Evidence</h2>
          {evidenceOpen ? (
            <Button type="button" variant="secondary" size="sm" className="xl:hidden" onClick={() => setEvidenceOpen(false)}>
              Close
            </Button>
          ) : null}
        </div>
        {finding ? (
          <ul className="mt-3 grid gap-3">
            {finding.evidence.map((row) => (
              <li key={row.id} className="text-sm">
                <p className="font-medium">{row.description}</p>
                <p className="text-ink-secondary">
                  {row.posted_on} · {row.category} · {row.amount} AED
                  {row.card_last4 ? ` · ··${row.card_last4}` : ""}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-ink-secondary">A published finding opens its posted rows here.</p>
        )}
        {investigation?.statements?.[0] ? (
          <p className="mt-4 text-sm text-ink-secondary">
            Statement closing {investigation.statements[0].closing_liability} AED is stored once for{" "}
            {investigation.statements[0].period_start} to {investigation.statements[0].period_end}.
          </p>
        ) : null}
      </aside>
    </section>
  );
}
