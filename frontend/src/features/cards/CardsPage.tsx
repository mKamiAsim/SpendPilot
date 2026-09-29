import { FormEvent, useEffect, useState } from "react";

import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { ApiRequestError, api, readJson } from "../../lib/api";

type Card = {
  id: string;
  alias: string;
  last4: string;
  status: string;
  password_saved: boolean;
  account: { id: string; alias: string; last4: string };
};

const empty = {
  alias: "",
  last4: "",
  account_alias: "",
  account_last4: "",
  password: "",
};

export function CardsPage() {
  const [cards, setCards] = useState<Card[]>([]);
  const [form, setForm] = useState(empty);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function load() {
    const body = await readJson<{ cards: Card[] }>(await api("/api/v1/cards"));
    setCards(body.cards);
  }

  useEffect(() => {
    load().catch((exc: unknown) => setError(exc instanceof ApiRequestError ? exc.message : "The cards could not be loaded."));
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      await readJson(
        await api("/api/v1/cards", {
          method: "POST",
          body: JSON.stringify({
            alias: form.alias,
            last4: form.last4,
            account_alias: form.account_alias,
            account_last4: form.account_last4,
            password: form.password || null,
          }),
        }),
      );
      setForm(empty);
      await load();
    } catch (exc) {
      setError(exc instanceof ApiRequestError ? exc.message : "The card could not be saved.");
    } finally {
      setPending(false);
    }
  }

  async function close(card: Card) {
    setError("");
    try {
      await readJson(await api(`/api/v1/cards/${card.id}`, { method: "PATCH", body: JSON.stringify({ status: "closed" }) }));
      await load();
    } catch (exc) {
      setError(exc instanceof ApiRequestError ? exc.message : "The card could not be closed.");
    }
  }

  const active = cards.filter((card) => card.status === "active").length;

  return (
    <section className="mx-auto max-w-3xl">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-secondary">SpendPilot</p>
      <h1 className="mt-2 text-[1.75rem] font-semibold leading-tight">Cards & accounts</h1>
      <p className="mt-3 max-w-2xl text-sm text-ink-secondary">
        Up to ten active cards. Several cards can share one account. The shared closing balance stays on the statement,
        not on each card. A saved PDF password is encrypted and is not shown again.
      </p>
      <p className="mt-4 text-sm">
        {active} of 10 active
      </p>
      {error ? <p className="mt-4 text-sm text-bad">{error}</p> : null}
      <ul className="mt-4 grid gap-3">
        {cards.map((card) => (
          <li key={card.id} className="rounded-xl border border-line bg-surface p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-medium">
                  {card.alias} ··{card.last4}
                </p>
                <p className="mt-1 text-sm text-ink-secondary">
                  {card.account.alias} ··{card.account.last4} · {card.status === "active" ? "Active" : "Closed"}
                  {card.password_saved ? " · Password saved" : ""}
                </p>
              </div>
              {card.status === "active" ? (
                <Button variant="secondary" size="sm" onClick={() => close(card)}>
                  Close
                </Button>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
      <form onSubmit={onSubmit} className="mt-8 grid gap-4 rounded-xl border border-line bg-surface p-6">
        <h2 className="text-base font-medium">Add a card</h2>
        <div className="grid gap-2">
          <Label htmlFor="card-alias">Card name</Label>
          <Input id="card-alias" value={form.alias} onChange={(event) => setForm({ ...form, alias: event.target.value })} required />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="card-last4">Card last four</Label>
          <Input id="card-last4" inputMode="numeric" maxLength={4} value={form.last4} onChange={(event) => setForm({ ...form, last4: event.target.value })} required />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="account-alias">Shared account name</Label>
          <Input id="account-alias" value={form.account_alias} onChange={(event) => setForm({ ...form, account_alias: event.target.value })} required />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="account-last4">Account last four</Label>
          <Input id="account-last4" inputMode="numeric" maxLength={4} value={form.account_last4} onChange={(event) => setForm({ ...form, account_last4: event.target.value })} required />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="pdf-password">PDF password, optional</Label>
          <Input id="pdf-password" type="password" autoComplete="off" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} />
        </div>
        <Button type="submit" disabled={pending}>
          Save card
        </Button>
      </form>
    </section>
  );
}
