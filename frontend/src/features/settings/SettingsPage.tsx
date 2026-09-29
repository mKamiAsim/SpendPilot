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
  const [memories, setMemories] = useState<{ id: string; body: string }[]>([]);
  const [memoryDraft, setMemoryDraft] = useState("");

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
    api("/api/v1/memories")
      .then((response) => readJson<{ memories: { id: string; body: string }[] }>(response))
      .then((body) => setMemories(body.memories))
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
      <form
        className="mt-6 grid gap-3 rounded-xl border border-line bg-surface p-6"
        onSubmit={async (event) => {
          event.preventDefault();
          setProviderError("");
          const saved = await readJson<{ id: string; body: string }>(
            await api("/api/v1/memories", { method: "POST", body: JSON.stringify({ body: memoryDraft }) }),
          );
          setMemories((current) => [...current, saved]);
          setMemoryDraft("");
        }}
      >
        <h2 className="text-base font-medium">Confirmed preferences</h2>
        <p className="text-sm text-ink-secondary">
          A preference is kept only when you save it. A review can read it. It is not treated as income or as a posted
          amount.
        </p>
        <Label htmlFor="memory-body">Preference</Label>
        <Input id="memory-body" value={memoryDraft} onChange={(event) => setMemoryDraft(event.target.value)} />
        <Button type="submit" disabled={!memoryDraft.trim()}>
          Save preference
        </Button>
        <ul className="grid gap-2">
          {memories.map((memory) => (
            <li key={memory.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span>{memory.body}</span>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={async () => {
                  await readJson(await api(`/api/v1/memories/${memory.id}`, { method: "DELETE" }));
                  setMemories((current) => current.filter((item) => item.id !== memory.id));
                }}
              >
                Delete
              </Button>
            </li>
          ))}
        </ul>
      </form>
      <CategoryPanel />
      <BackupPanel />
      <PurgePanel />
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

function PurgePanel() {
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  return (
    <form
      className="mt-6 grid gap-3 rounded-xl border border-line bg-surface p-6"
      onSubmit={async (event) => {
        event.preventDefault();
        setError("");
        setMessage("");
        try {
          await readJson(await api("/api/v1/lifecycle/purge", { method: "POST" }));
          setMessage("Entries and derived notes older than 18 months were removed. An instalment that still has a balance stays.");
        } catch (exc) {
          setError(exc instanceof ApiRequestError ? exc.message : "The purge could not be run.");
        }
      }}
    >
      <h2 className="text-base font-medium">18-month retention</h2>
      <p className="text-sm text-ink-secondary">
        This removes old posted rows, cash entries, and derived notes. A plan with money still outstanding keeps its
        record.
      </p>
      {error ? <p className="text-sm text-bad">{error}</p> : null}
      {message ? <p className="text-sm">{message}</p> : null}
      <Button type="submit" variant="secondary">
        Remove old entries
      </Button>
    </form>
  );
}

function CategoryPanel() {
  const [name, setName] = useState("");
  const [custom, setCustom] = useState<string[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api("/api/v1/categories")
      .then((response) => readJson<{ custom: string[] }>(response))
      .then((body) => setCustom(body.custom))
      .catch(() => undefined);
  }, []);

  return (
    <form
      className="mt-6 grid gap-3 rounded-xl border border-line bg-surface p-6"
      onSubmit={async (event) => {
        event.preventDefault();
        setError("");
        setMessage("");
        try {
          const saved = await readJson<{ name: string }>(
            await api("/api/v1/categories", { method: "POST", body: JSON.stringify({ name }) }),
          );
          setCustom((current) => [...current, saved.name]);
          setName("");
          setMessage("Category saved. It can be used on cash entries and instalments.");
        } catch (exc) {
          setError(exc instanceof ApiRequestError ? exc.message : "The category could not be saved.");
        }
      }}
    >
      <h2 className="text-base font-medium">Categories</h2>
      <p className="text-sm text-ink-secondary">
        The v1 list stays fixed. Add a name of your own when none of those fit. SpendPilot does not infer a merchant
        code.
      </p>
      <Label htmlFor="category-name">Your category</Label>
      <Input id="category-name" value={name} onChange={(event) => setName(event.target.value)} />
      {error ? <p className="text-sm text-bad">{error}</p> : null}
      {message ? <p className="text-sm">{message}</p> : null}
      <Button type="submit" disabled={!name.trim()}>
        Add category
      </Button>
      {custom.length > 0 ? <p className="text-sm text-ink-secondary">{custom.join(", ")}</p> : null}
    </form>
  );
}

function BackupPanel() {
  const [passphrase, setPassphrase] = useState("");
  const [restorePassphrase, setRestorePassphrase] = useState("");
  const [includeSecrets, setIncludeSecrets] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function download(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      const created = await readJson<{ id: string }>(
        await api("/api/v1/lifecycle/backups", {
          method: "POST",
          body: JSON.stringify({ passphrase, include_secrets: includeSecrets }),
        }),
      );
      const response = await api(`/api/v1/lifecycle/backups/${created.id}`);
      if (!response.ok) {
        throw new ApiRequestError(response.status, "request_failed", "The backup could not be downloaded.");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "spendpilot-backup.bin";
      link.click();
      URL.revokeObjectURL(url);
      setMessage("Backup downloaded. SpendPilot stores only the encrypted file.");
    } catch (exc) {
      setError(exc instanceof ApiRequestError ? exc.message : "The backup could not be created.");
    }
  }

  async function restore(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setError("");
    setMessage("");
    try {
      const body = new FormData();
      body.append("passphrase", restorePassphrase);
      body.append("file", file);
      await readJson(await api("/api/v1/lifecycle/restore", { method: "POST", body }));
      setMessage("Backup restored. Rows older than 18 months were removed again.");
    } catch (exc) {
      setError(exc instanceof ApiRequestError ? exc.message : "The backup could not be restored.");
    }
  }

  return (
    <div className="mt-6 grid gap-4">
      <form onSubmit={download} className="grid gap-4 rounded-xl border border-line bg-surface p-6">
        <h2 className="text-base font-medium">Encrypted backup</h2>
        <p className="text-sm text-ink-secondary">
          Choose a passphrase. The server stores ciphertext and cannot read it. Provider keys and saved PDF passwords stay
          out unless you include them.
        </p>
        <div className="grid gap-2">
          <Label htmlFor="backup-passphrase">Passphrase</Label>
          <Input
            id="backup-passphrase"
            type="password"
            autoComplete="new-password"
            value={passphrase}
            onChange={(event) => setPassphrase(event.target.value)}
            required
            minLength={8}
          />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={includeSecrets} onChange={(event) => setIncludeSecrets(event.target.checked)} />
          Include provider keys and saved PDF passwords
        </label>
        {error ? <p className="text-sm text-bad">{error}</p> : null}
        {message ? <p className="text-sm">{message}</p> : null}
        <Button type="submit">Download backup</Button>
      </form>
      <form onSubmit={restore} className="grid gap-4 rounded-xl border border-line bg-surface p-6">
        <h2 className="text-base font-medium">Restore</h2>
        <div className="grid gap-2">
          <Label htmlFor="restore-file">Backup file</Label>
          <Input id="restore-file" type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} required />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="restore-passphrase">Passphrase</Label>
          <Input
            id="restore-passphrase"
            type="password"
            autoComplete="off"
            value={restorePassphrase}
            onChange={(event) => setRestorePassphrase(event.target.value)}
            required
            minLength={8}
          />
        </div>
        <Button type="submit" variant="secondary">
          Restore backup
        </Button>
      </form>
    </div>
  );
}
