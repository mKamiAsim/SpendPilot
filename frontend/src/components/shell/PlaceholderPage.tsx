export function PlaceholderPage({ title, detail }: { title: string; detail: string }) {
  return (
    <section className="mx-auto max-w-3xl">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-secondary">SpendPilot</p>
      <h1 className="mt-2 text-[1.75rem] font-semibold leading-tight">{title}</h1>
      <p className="mt-4 max-w-2xl text-base text-ink-secondary">{detail}</p>
    </section>
  );
}
