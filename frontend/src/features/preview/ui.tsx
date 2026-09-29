import { useEffect, useRef } from "react";
import { Link } from "react-router";

import { Button } from "../../components/ui/button";
import { cn } from "../../lib/cn";
import { formatAed } from "./format";
import type { FixtureTransaction } from "./fixtures";

export function MoneyValue({
  value,
  size = "md",
  className,
}: {
  value: number | null;
  size?: "md" | "lg";
  className?: string;
}) {
  const unknown = value === null;
  return (
    <span className={cn("money inline-flex items-baseline gap-1", size === "lg" && "text-[2rem] font-semibold leading-none", className)}>
      {unknown ? (
        <span>Unknown</span>
      ) : (
        <>
          <span className={cn("text-ink-secondary", size === "lg" ? "text-sm" : "text-xs")}>AED</span>
          <span>{formatAed(value)}</span>
        </>
      )}
    </span>
  );
}

export function ComparisonDelta({
  label,
  tone,
}: {
  label: string;
  tone: "neutral" | "attention";
}) {
  return (
    <p className={cn("text-sm", tone === "attention" ? "text-warn" : "text-ink-secondary")}>{label}</p>
  );
}

export function AccountBadge({ name }: { name: string }) {
  return (
    <span className="inline-flex max-w-full items-center rounded-lg bg-surface-secondary px-2 py-1 text-xs text-ink">
      {name}
    </span>
  );
}

export function CoverageIndicator() {
  return (
    <p className="text-sm text-ink-secondary">
      <span className="font-medium text-ink">2 of 2 cards</span>
      {" · statements through 28 Sep 2026 · income not imported"}
    </p>
  );
}

const severityStyle = {
  Attention: "bg-warn-bg text-warn",
  Watch: "bg-bad-bg text-bad",
  Note: "bg-info-bg text-info",
} as const;

export function FindingCard({
  severity,
  title,
  detail,
  effect,
  evidenceCount,
  primary,
  secondary,
}: {
  severity: keyof typeof severityStyle;
  title: string;
  detail: string;
  effect?: string;
  evidenceCount: number;
  primary: { label: string; to?: string; onClick?: () => void };
  secondary?: { label: string; onClick: () => void };
}) {
  return (
    <article className="rounded-xl border border-line bg-surface p-4">
      <p className={cn("inline-flex rounded-md px-2 py-0.5 text-xs font-medium", severityStyle[severity])}>{severity}</p>
      <h3 className="mt-2 text-base font-semibold leading-snug">{title}</h3>
      <p className="mt-1 text-sm text-ink-secondary">{detail}</p>
      {effect ? <p className="money mt-2 text-sm font-medium">{effect}</p> : null}
      <p className="mt-2 text-xs text-ink-secondary">
        {evidenceCount} {evidenceCount === 1 ? "source row" : "source rows"}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {primary.to ? (
          <Button size="sm" variant="secondary" asChild>
            <Link to={primary.to}>{primary.label}</Link>
          </Button>
        ) : (
          <Button size="sm" variant="secondary" type="button" onClick={primary.onClick}>
            {primary.label}
          </Button>
        )}
        {secondary ? (
          <Button size="sm" variant="ghost" type="button" onClick={secondary.onClick}>
            {secondary.label}
          </Button>
        ) : null}
      </div>
    </article>
  );
}

export function EvidenceBody({ row }: { row: FixtureTransaction }) {
  return (
    <div className="flex flex-col gap-4 text-sm">
      <div>
        <p className="text-xs uppercase tracking-[0.14em] text-ink-secondary">Description</p>
        <p className="mt-1 text-base font-medium" dir={row.arabic ? "auto" : undefined}>
          {row.description}
        </p>
      </div>
      <dl className="grid grid-cols-2 gap-3">
        <div>
          <dt className="text-xs text-ink-secondary">Amount</dt>
          <dd className="mt-1">
            <MoneyValue value={row.amount} />
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink-secondary">Type</dt>
          <dd className="mt-1">{row.type}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-secondary">Category</dt>
          <dd className="mt-1">{row.category}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-secondary">Card</dt>
          <dd className="mt-1">{row.card}</dd>
        </div>
        <div className="col-span-2">
          <dt className="text-xs text-ink-secondary">Source</dt>
          <dd className="mt-1">
            {row.statement}, page {row.sourcePage}
          </dd>
        </div>
      </dl>
      <p className="text-ink-secondary">{row.note}</p>
      <p className="rounded-lg bg-surface-secondary px-3 py-2 text-ink-secondary">
        {row.countsInSpending
          ? "Included in September net spending."
          : "Not included in September net spending."}
      </p>
    </div>
  );
}

export function EvidenceDrawer({
  row,
  onClose,
}: {
  row: FixtureTransaction | null;
  onClose: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!row) return;
    closeRef.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [row, onClose]);
  if (!row) return null;
  return (
    <div className="fixed inset-0 z-40 md:left-[232px]" data-testid="evidence-drawer">
      <button className="absolute inset-0 bg-[#17212f]/40" aria-label="Close evidence" onClick={onClose} />
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidence-title"
        className="absolute inset-y-0 right-0 flex w-full max-w-[440px] flex-col border-l border-line bg-surface shadow-sm"
      >
        <header className="flex items-center justify-between border-b border-line px-4 py-3">
          <h2 id="evidence-title" className="text-base font-semibold">
            Evidence
          </h2>
          <Button ref={closeRef} variant="ghost" size="sm" type="button" onClick={onClose}>
            Close
          </Button>
        </header>
        <div className="flex-1 overflow-y-auto px-4 py-4">
          <EvidenceBody row={row} />
        </div>
      </aside>
    </div>
  );
}
