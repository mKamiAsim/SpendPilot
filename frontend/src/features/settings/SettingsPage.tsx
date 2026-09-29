import { useNavigate } from "react-router";

import { useSession } from "../../app/session";
import { Button } from "../../components/ui/button";
import { api, readJson, rememberCsrf } from "../../lib/api";

export function SettingsPage() {
  const { user, refresh } = useSession();
  const navigate = useNavigate();
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
