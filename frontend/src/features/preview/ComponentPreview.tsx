import { useState } from "react";

import { Button } from "../../components/ui/button";
import { transactions } from "./fixtures";
import { FixtureBanner, UnavailableNote } from "./states";
import { AccountBadge, ComparisonDelta, EvidenceDrawer, FindingCard, MoneyValue } from "./ui";

export default function ComponentPreview() {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState(false);
  const sample = transactions[0];
  return (
    <div>
      <FixtureBanner />
      <header className="mb-6">
        <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-secondary">Development only</p>
        <h1 className="mt-1 text-[1.75rem] font-semibold">Component preview</h1>
        <p className="mt-2 max-w-2xl text-sm text-ink-secondary">
          Shared pieces for the September fixture. This route is absent from the production build.
        </p>
      </header>
      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-xl border border-line bg-surface p-4">
          <h2 className="text-lg font-semibold">Money</h2>
          <div className="mt-3 flex flex-col gap-2">
            <MoneyValue value={4770.55} size="lg" />
            <MoneyValue value={-120} />
            <MoneyValue value={null} />
            <ComparisonDelta label="AED 349.85 less than August" tone="neutral" />
            <ComparisonDelta label="AED 35.00 higher than August" tone="attention" />
            <AccountBadge name="Everyday card ··4412" />
          </div>
        </section>
        <section className="rounded-xl border border-line bg-surface p-4">
          <h2 className="text-lg font-semibold">Controls</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button type="button">Primary</Button>
            <Button type="button" variant="secondary">
              Secondary
            </Button>
            <Button type="button" variant="ghost">
              Ghost
            </Button>
            <Button type="button" variant="secondary" onClick={() => setOpen(true)}>
              Open evidence
            </Button>
          </div>
        </section>
        <FindingCard
          severity="Attention"
          title="Finding with two actions"
          detail="Severity is a word, not colour alone."
          effect="AED 75.00 fee"
          evidenceCount={1}
          primary={{ label: "Open evidence", onClick: () => setOpen(true) }}
          secondary={{ label: "Unavailable action", onClick: () => setNote(true) }}
        />
        <section className="rounded-xl border border-dashed border-line p-4">
          <h2 className="text-lg font-semibold">Empty</h2>
          <p className="mt-2 text-sm text-ink-secondary">No rows for this filter. Reset the filter or import a statement later.</p>
        </section>
        <section className="rounded-xl border border-line bg-bad-bg p-4 text-bad">
          <h2 className="text-lg font-semibold">Error</h2>
          <p className="mt-2 text-sm">The preview could not load a second cycle. September is still available.</p>
        </section>
        <section className="rounded-xl border border-line bg-surface p-4">
          <h2 className="text-lg font-semibold">Partial</h2>
          <p className="mt-2 text-sm text-ink-secondary">1 of 2 cards have a statement. The missing card is unknown, not AED 0.00.</p>
          <p className="mt-2">
            <MoneyValue value={null} />
          </p>
        </section>
      </div>
      <EvidenceDrawer row={open ? sample : null} onClose={() => setOpen(false)} />
      {note ? (
        <UnavailableNote
          title="Not available"
          detail="Secondary actions explain themselves instead of failing silently."
          onClose={() => setNote(false)}
        />
      ) : null}
    </div>
  );
}
