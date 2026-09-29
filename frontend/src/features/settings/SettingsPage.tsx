import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router";

import { useSession } from "../../app/session";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { ApiRequestError, api, readJson, rememberCsrf } from "../../lib/api";

type ProviderForm = {
  endpoint: string;
  model: string;
  api_key: string;
  consent: string;
};

export function SettingsPage() {
  const { user, refresh } = useSession();
  const navigate = useNavigate();
  const [form, setForm] = useState<ProviderForm>({
    endpoint: "",
    model: "",
    api_key: "",
    consent: "none",
  });
  const [keySaved, setKeySaved] = useState(false);
  const [providerMessage, setProviderMessage] = useState("");
  const [providerError, setProviderError] = useState("");

  useEffect(() => {
    api("/api/v1/provider")
      .then((response) =>
        readJson<{ provider: { endpoint: string; model: string; consent: string; api_key_saved: boolean } | null }>(
          response,
        ),
      )
      .then((body) => {
        if (!body.provider) return;
        setForm((current) => ({
          ...current,
          endpoint: body.provider?.endpoint ?? "",
          model: body.provider?.model ?? "",
          consent: body.provider?.consent ?? "none",
        }));
        setKeySaved(body.provider.api_key_saved);
      })
      .catch(() => undefined);
  }, []);

  async function saveProvider(event: FormEvent) {
    event.preventDefault();
    setProviderError("");
    setProviderMessage("");
    try {
      const saved = await readJson<{ provider: { api_key_saved: boolean } }>(
        await api("/api/v1/provider", {
          method: "PUT",
          body: JSON.stringify({
            endpoint: form.endpoint,
            model: form.model,
            consent: form.consent,
            api_key: form.api_key ? form.api_key : null,
          }),
        }),
      );
      setKeySaved(saved.provider.api_key_saved);
      setForm((current) => ({ ...current, api_key: "" }));
      setProviderMessage("Provider saved. The API key is not shown again.");
    } catch (exc) {
      setProviderError(exc instanceof ApiRequestError ? exc.message : "The provider could not be saved.");
    }
  }

  async function testConnection() {
    setProviderError("");
    setProviderMessage("");
    try {
      const result = await readJson<{ message: string }>(await api("/api/v1/provider/test", { method: "POST" }));
      setProviderMessage(result.message);
    } catch (exc) {
      setProviderError(exc instanceof ApiRequestError ? exc.message : "The connection test could not be run.");
    }
  }

  if (!user) return null;

  return (
    <section className="mx-auto max-w-3xl">
      <h1 className="text-[1.75rem] font-semibold">Settings</h1>
      <dl className="mt-6 grid gap-4 rounded-xl border border-line bg-surface p-6">
        <div>
          <dt className="text-xs uppercase tracking-[0.14em] text-ink-secondary">Username</dt>
          <dd className="mt-1">{user.username}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-[0.14em] text-ink-secondary">Email</dt>
          <dd className="mt-1">{user.email}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-[0.14em] text-ink-secondary">Verification</dt>
          <dd className="mt-1">{user.email_verified ? "Verified" : "Not verified"}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-[0.14em] text-ink-secondary">Idle lock</dt>
          <dd className="mt-1 text-sm text-ink-secondary">
            The server locks a session after 15 minutes without a real request. Heartbeats do not count.
          </dd>
        </div>
      </dl>
      <form onSubmit={saveProvider} className="mt-6 grid gap-4 rounded-xl border border-line bg-surface p-6">
        <h2 className="text-base font-medium">Model connection</h2>
        <p className="text-sm text-ink-secondary">
          SpendPilot calls only the endpoint you save. It does not fall back to a hosted model. Document assistance stays
          off, so page text is not sent. An automatic review may include selected dates, descriptions, amounts,
          categories, and statement totals.
        </p>
        <div className="grid gap-2">
          <Label htmlFor="model-endpoint">Endpoint</Label>
          <Input
            id="model-endpoint"
            value={form.endpoint}
            onChange={(event) => setForm({ ...form, endpoint: event.target.value })}
            placeholder="https://example.invalid/v1"
            required
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="model-name">Model name</Label>
          <Input
            id="model-name"
            value={form.model}
            onChange={(event) => setForm({ ...form, model: event.target.value })}
            required
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="model-key">API key, optional</Label>
          <Input
            id="model-key"
            type="password"
            autoComplete="off"
            value={form.api_key}
            onChange={(event) => setForm({ ...form, api_key: event.target.value })}
          />
          <p className="text-xs text-ink-secondary">{keySaved ? "A key is saved." : "No key is saved."}</p>
        </div>
        <fieldset className="grid gap-2">
          <legend className="text-sm font-medium">Consent</legend>
          {[
            ["none", "Do not send ledger details"],
            ["summary", "Summary totals only"],
            ["selected_transactions", "Selected transaction details"],
          ].map(([value, label]) => (
            <label key={value} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="consent"
                value={value}
                checked={form.consent === value}
                onChange={() => setForm({ ...form, consent: value })}
              />
              {label}
            </label>
          ))}
        </fieldset>
        {providerError ? <p className="text-sm text-bad">{providerError}</p> : null}
        {providerMessage ? <p className="text-sm">{providerMessage}</p> : null}
        <div className="flex flex-wrap gap-2">
          <Button type="submit">Save provider</Button>
          <Button type="button" variant="secondary" onClick={testConnection}>
            Test connection
          </Button>
        </div>
      </form>
      <Button
        className="mt-6"
        variant="secondary"
        onClick={async () => {
          await readJson(await api("/api/v1/auth/logout", { method: "POST" }));
          rememberCsrf("");
          await refresh();
          navigate("/login");
        }}
      >
        Sign out
      </Button>
    </section>
  );
}
