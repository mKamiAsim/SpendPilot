import { useState } from "react";

import { Button } from "../../components/ui/button";
import { transactions } from "../preview/fixtures";
import { FixtureBanner, UnavailableNote } from "../preview/states";
import { EvidenceBody, FindingCard } from "../preview/ui";

const noon = transactions.find((row) => row.id === "tx-05")!;
const refund = transactions.find((row) => row.id === "tx-07")!;

const conversations = [
  { id: "sep", title: "September spending" },
  { id: "fees", title: "Fees on the everyday card" },
];

export default function AdvisorFixture() {
  const [active, setActive] = useState("sep");
  const [listOpen, setListOpen] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [activityOpen, setActivityOpen] = useState(false);

  return (
    <div>
      <FixtureBanner />
      <header className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-secondary">Intelligence</p>
          <h1 className="mt-1 text-[1.75rem] font-semibold">Advisor</h1>
        </div>
        <div className="flex gap-2 xl:hidden">
          <Button type="button" size="sm" variant="secondary" onClick={() => setListOpen(true)}>
            Conversations
          </Button>
          <Button type="button" size="sm" variant="secondary" onClick={() => setEvidenceOpen(true)}>
            Evidence
          </Button>
        </div>
      </header>
      <div className="grid gap-4 xl:grid-cols-[220px_minmax(0,1fr)_320px]">
        <nav className="hidden rounded-xl border border-line bg-surface p-2 xl:block" aria-label="Conversations">
          <ConversationList active={active} onPick={setActive} />
        </nav>
        <section className="flex min-w-0 flex-col rounded-xl border border-line bg-surface">
          <div className="border-b border-line px-4 py-3">
            <div className="flex flex-wrap gap-2">
              <span className="rounded-lg bg-surface-secondary px-2 py-1 text-xs">September 2026</span>
              <span className="rounded-lg bg-surface-secondary px-2 py-1 text-xs">Both cards</span>
            </div>
            <p className="mt-2 text-xs text-ink-secondary">Preview answer. No model was called.</p>
          </div>
          <div className="flex flex-col gap-4 px-4 py-4">
            {active === "sep" ? (
              <>
                <p className="text-sm text-ink-secondary">You asked what changed this month.</p>
                <p className="text-sm leading-6">
                  September net spending is lower than August in this preview. The change is a shopping refund and a
                  smaller set of dining rows, not a card payment. One Noon purchase still dominates shopping.
                </p>
                <FindingCard
                  severity="Attention"
                  title="One Noon order is most of shopping"
                  detail="The refund the next day reduces that order. It does not erase it, and it is not income."
                  effect="AED 1,984.30 net shopping"
                  evidenceCount={2}
                  primary={{ label: "Open evidence", onClick: () => setEvidenceOpen(true) }}
                  secondary={{ label: "Ask a follow-up", onClick: () => setDraft("What changed this month?") }}
                />
                <div className="rounded-xl border border-line">
                  <button
                    type="button"
                    className="flex h-11 w-full items-center justify-between px-3 text-left text-sm"
                    aria-expanded={activityOpen}
                    onClick={() => setActivityOpen((open) => !open)}
                  >
                    Completed activity
                    <span className="text-ink-secondary">{activityOpen ? "Hide" : "Show"}</span>
                  </button>
                  {activityOpen ? (
                    <ol className="border-t border-line px-3 py-2 text-sm text-ink-secondary">
                      <li>Compared the September and August preview totals.</li>
                      <li>Opened the Noon purchase and the Noon refund.</li>
                    </ol>
                  ) : null}
                </div>
              </>
            ) : (
              <p className="text-sm text-ink-secondary">
                The everyday card fee in this preview is AED 75.00, posted 21 Sep 2026. Open evidence from the September
                conversation for the shopping rows. This thread does not invent a second finding.
              </p>
            )}
          </div>
          <form
            className="mt-auto border-t border-line p-3"
            onSubmit={(event) => {
              event.preventDefault();
              setNote("send");
            }}
          >
            <label className="text-xs text-ink-secondary" htmlFor="composer">
              Message
            </label>
            <textarea
              id="composer"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              rows={3}
              className="mt-1 w-full resize-y rounded-lg border border-line bg-canvas px-3 py-2 text-base"
              placeholder="What changed this month?"
            />
            <div className="mt-2 flex flex-wrap gap-2">
              <Button type="button" size="sm" variant="secondary" onClick={() => setDraft("What changed this month?")}>
                What changed this month?
              </Button>
              <Button type="submit" size="sm">
                Send
              </Button>
              <Button type="button" size="sm" variant="secondary" disabled>
                Stop
              </Button>
            </div>
          </form>
        </section>
        <aside className="hidden rounded-xl border border-line bg-surface p-4 xl:block" data-testid="advisor-evidence">
          <h2 className="text-base font-semibold">Evidence</h2>
          <div className="mt-4 flex flex-col gap-4">
            <EvidenceBody row={noon} />
            <EvidenceBody row={refund} />
          </div>
        </aside>
      </div>

      {listOpen ? (
        <div className="fixed inset-0 z-40 xl:hidden">
          <button className="absolute inset-0 bg-[#17212f]/40" aria-label="Close conversations" onClick={() => setListOpen(false)} />
          <nav aria-label="Conversations" className="absolute inset-y-0 left-0 w-[min(100%,320px)] bg-surface p-4">
            <ConversationList
              active={active}
              onPick={(id) => {
                setActive(id);
                setListOpen(false);
              }}
            />
          </nav>
        </div>
      ) : null}
      {evidenceOpen ? (
        <div className="fixed inset-0 z-40 xl:hidden" data-testid="advisor-evidence-sheet">
          <button className="absolute inset-0 bg-[#17212f]/40" aria-label="Close evidence" onClick={() => setEvidenceOpen(false)} />
          <aside className="absolute inset-0 overflow-y-auto bg-surface p-4 sm:left-auto sm:w-[min(100%,440px)] sm:border-l sm:border-line">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base font-semibold">Evidence</h2>
              <Button type="button" size="sm" variant="ghost" onClick={() => setEvidenceOpen(false)}>
                Close
              </Button>
            </div>
            <div className="flex flex-col gap-6">
              <EvidenceBody row={noon} />
              <EvidenceBody row={refund} />
            </div>
          </aside>
        </div>
      ) : null}
      {note ? (
        <UnavailableNote
          title="This preview cannot send"
          detail="Send stays on screen so the composer can be reviewed. No model endpoint is configured, and this fixture will not invent a reply."
          onClose={() => setNote(null)}
        />
      ) : null}
    </div>
  );
}

function ConversationList({ active, onPick }: { active: string; onPick: (id: string) => void }) {
  return (
    <ul className="flex flex-col gap-1">
      {conversations.map((item) => (
        <li key={item.id}>
          <button
            type="button"
            className={`h-11 w-full rounded-lg px-3 text-left text-sm ${active === item.id ? "bg-surface-secondary font-medium" : ""}`}
            onClick={() => onPick(item.id)}
          >
            {item.title}
          </button>
        </li>
      ))}
    </ul>
  );
}
