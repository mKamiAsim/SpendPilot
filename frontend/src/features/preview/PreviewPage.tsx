import { lazy, Suspense } from "react";
import { Navigate } from "react-router";

const Preview = import.meta.env.DEV ? lazy(() => import("./ComponentPreview")) : null;

export function PreviewPage() {
  if (!Preview) return <Navigate to="/overview" replace />;
  return (
    <Suspense fallback={<p className="text-sm text-ink-secondary">Loading the development preview…</p>}>
      <Preview />
    </Suspense>
  );
}
