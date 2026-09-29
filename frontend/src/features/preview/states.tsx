import { Link } from "react-router";

import { FIXTURE_LABEL } from "./fixtures";

export function FixtureBanner() {
  return (
    <p
      className="mb-4 rounded-lg border border-warn/40 bg-warn-bg px-3 py-2 text-sm text-warn"
      data-testid="dev-fixture-banner"
    >
      {FIXTURE_LABEL}{" "}
      <Link className="underline" to="/dev/components">
        Component preview
      </Link>
    </p>
  );
}

export function UnavailableNote({
  title,
  detail,
  onClose,
}: {
  title: string;
  detail: string;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center px-4 py-6 sm:items-center" role="presentation">
      <button className="absolute inset-0 bg-[#17212f]/40" aria-label="Close" onClick={onClose} />
      <div role="dialog" aria-labelledby="unavailable-title" className="relative w-full max-w-md rounded-xl border border-line bg-surface p-5">
        <h2 id="unavailable-title" className="text-lg font-semibold">
          {title}
        </h2>
        <p className="mt-2 text-sm text-ink-secondary">{detail}</p>
        <button className="mt-4 h-11 rounded-lg bg-action px-4 text-sm font-medium text-action-ink" type="button" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}
