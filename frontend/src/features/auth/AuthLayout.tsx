import type { ReactNode } from "react";
import { Link } from "react-router";

import { useTheme } from "../../app/theme";
import { Button } from "../../components/ui/button";

export function AuthLayout({
  title,
  children,
  footer,
}: {
  title: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const { theme, toggle } = useTheme();
  return (
    <main className="min-h-screen bg-canvas px-4 py-8 text-ink md:px-8">
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-5xl items-center justify-center">
        <div className="grid w-full items-center gap-8 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
          <section className="rounded-2xl border border-line bg-surface p-6 md:p-8">
            <div className="mb-8 flex items-center justify-between">
              <Link to="/login" className="flex items-center gap-2 text-sm font-semibold">
                <span aria-hidden="true" className="h-2.5 w-2.5 rounded-sm bg-action" />
                SpendPilot
              </Link>
              <Button variant="ghost" size="sm" type="button" onClick={toggle}>
                {theme === "dark" ? "Light" : "Dark"}
              </Button>
            </div>
            <h1 className="text-[1.75rem] font-semibold leading-tight">{title}</h1>
            <div className="mt-6">{children}</div>
            {footer ? <div className="mt-6 text-sm text-ink-secondary">{footer}</div> : null}
          </section>
          <aside className="hidden rounded-2xl border border-line bg-surface-secondary p-8 lg:block">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-secondary">On this installation</p>
            <h2 className="mt-3 text-xl font-semibold">Your statements stay on this backend.</h2>
            <p className="mt-3 text-sm text-ink-secondary">
              SpendPilot keeps records on the operator’s server. A model is optional, and nothing is sent to one until
              you choose that later. This foundation build does not import statements yet.
            </p>
          </aside>
        </div>
      </div>
    </main>
  );
}

export function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <p className="text-sm text-[#9f1239] dark:text-[#fecdd3]">{message}</p>;
}
