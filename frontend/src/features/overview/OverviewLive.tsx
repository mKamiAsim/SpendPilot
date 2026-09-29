import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router";

import { Button } from "../../components/ui/button";
import { ApiRequestError, api, readJson } from "../../lib/api";

type Review = {
  id: string;
  status: string;
  live: boolean;
  failure_message: string | null;
  briefing: { title: string; explanation: string; stale: boolean } | null;
  scenario: {
    category: string;
    baseline: string;
    reduction: string;
    proposed: string;
    affordability_blocked: boolean;
    affordability_amount: string | null;
    stale: boolean;
  } | null;
  target: { id: string; status: string } | null;
};

export function OverviewLive() {
  const [review, setReview] = useState<Review | null>(null);
  const [consent, setConsent] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function load() {
    const [profile, list] = await Promise.all([
      api("/api/v1/provider").then((response) => readJson<{ provider: { consent: string } | null }>(response)),
      api("/api/v1/reviews").then((response) => readJson<{ reviews: Review[] }>(response)),
    ]);
    setConsent(profile.provider?.consent ?? "none");
    setReview(list.reviews[0] ?? null);
  }

  useEffect(() => {
    load().catch((exc: unknown) => setError(exc instanceof ApiRequestError ? exc.message : "The briefing could not be loaded."));
  }, []);

  async function runReview(event: FormEvent) {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      const created = await readJson<Review>(await api("/api/v1/reviews", { method: "POST", body: JSON.stringify({}) }));
      for (let attempt = 0; attempt < 12; attempt += 1) {
        const next = await readJson<Review>(await api(`/api/v1/reviews/${created.id}`));
        if (next.status === "published" || next.status === "failed" || next.status === "linked") {
          await load();
          break;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 400));
      }
    } catch (exc) {
      setError(exc instanceof ApiRequestError ? exc.message : "The monthly review could not be started.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="mx-auto grid max-w-5xl gap-4">
      <div>
        <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-secondary">SpendPilot</p>
        <h1 className="mt-2 text-[1.75rem] font-semibold leading-tight">Monthly briefing</h1>
        <p className="mt-3 max-w-2xl text-sm text-ink-secondary">
          One review freezes posted rows, checks two specialist roles, and publishes a briefing only when each amount
          matches its calculation. It does not call a specialist for every question.
        </p>
        {review && !review.live ? <p className="mt-3 text-sm">Deterministic test provider. This is not a live model.</p> : null}
      </div>
      {error ? <p className="text-sm text-bad">{error}</p> : null}
      {consent !== "selected_transactions" ? (
        <p className="text-sm text-ink-secondary">
          Choose selected transaction details in Settings before a monthly review can run. Summary consent does not send
          rows.
        </p>
      ) : null}
      <form onSubmit={runReview}>
        <Button type="submit" disabled={pending || consent !== "selected_transactions"}>
          Run monthly review
        </Button>
      </form>
      {review?.status === "failed" ? <p className="text-sm text-bad">{review.failure_message}</p> : null}
      {review?.briefing ? (
        <article className="rounded-xl border border-line bg-surface p-4">
          {review.briefing.stale ? <p className="text-sm text-warn">Stale after a category correction.</p> : null}
          <h2 className="mt-1 text-lg font-medium">{review.briefing.title}</h2>
          <p className="mt-2 text-sm leading-6">{review.briefing.explanation}</p>
          {review.scenario ? (
            <p className="mt-3 text-sm">
              {review.scenario.category} {review.scenario.baseline} AED, reduced by {review.scenario.reduction} AED, leaves{" "}
              {review.scenario.proposed} AED. Calculation category_reduction.
              {review.scenario.stale ? " This scenario is stale." : ""}
            </p>
          ) : null}
          {review.target ? <p className="mt-2 text-sm text-ink-secondary">Target {review.target.status}.</p> : null}
          <Link className="mt-4 inline-flex text-sm underline" to="/intelligence/scenarios">
            Open scenarios
          </Link>
        </article>
      ) : (
        <p className="text-sm text-ink-secondary">No briefing is published yet.</p>
      )}
    </section>
  );
}
