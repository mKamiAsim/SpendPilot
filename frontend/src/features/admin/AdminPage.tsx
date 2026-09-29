import { useQuery, useQueryClient } from "@tanstack/react-query";

import { useSession } from "../../app/session";
import { Button } from "../../components/ui/button";
import { api, readJson } from "../../lib/api";

type Registration = { registration_enabled: boolean };
type Status = { database: string; email_delivery: string; queue_schema: string; worker_liveness: string };

export function AdminPage() {
  const { user } = useSession();
  const queryClient = useQueryClient();
  const registration = useQuery({
    queryKey: ["admin-registration"],
    queryFn: async () => readJson<Registration>(await api("/api/v1/admin/registration")),
    enabled: user?.role === "admin",
  });
  const status = useQuery({
    queryKey: ["admin-status"],
    queryFn: async () => readJson<Status>(await api("/api/v1/admin/status")),
    enabled: user?.role === "admin",
  });

  if (user?.role !== "admin") {
    return <p>Administration is only available to an administrator.</p>;
  }

  return (
    <section className="mx-auto max-w-3xl">
      <h1 className="text-[1.75rem] font-semibold">Administration</h1>
      <p className="mt-3 text-sm text-ink-secondary">
        This screen changes registration only. It does not show anyone’s statements.
      </p>
      <div className="mt-6 rounded-xl border border-line bg-surface p-6">
        <h2 className="text-lg font-medium">Public registration</h2>
        <p className="mt-2 text-sm text-ink-secondary">
          {registration.data?.registration_enabled ? "Open to new accounts." : "Turned off."}
        </p>
        <Button
          className="mt-4"
          variant="secondary"
          onClick={async () => {
            await readJson(
              await api("/api/v1/admin/registration", {
                method: "PATCH",
                body: JSON.stringify({ enabled: !registration.data?.registration_enabled }),
              }),
            );
            await queryClient.invalidateQueries({ queryKey: ["admin-registration"] });
          }}
        >
          {registration.data?.registration_enabled ? "Turn registration off" : "Turn registration on"}
        </Button>
      </div>
      <dl className="mt-4 grid gap-3 rounded-xl border border-line bg-surface p-6 text-sm">
        <div className="flex justify-between gap-4">
          <dt className="text-ink-secondary">Database</dt>
          <dd>{status.data?.database ?? "…"}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-ink-secondary">Email delivery</dt>
          <dd>{status.data?.email_delivery ?? "…"}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-ink-secondary">Queue schema</dt>
          <dd>{status.data?.queue_schema ?? "…"}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-ink-secondary">Worker liveness</dt>
          <dd>{status.data?.worker_liveness ?? "unverified"}</dd>
        </div>
      </dl>
    </section>
  );
}
