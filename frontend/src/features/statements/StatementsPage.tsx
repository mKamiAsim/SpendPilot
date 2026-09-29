import { FormEvent, useEffect, useState } from "react";

import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { ApiRequestError, api, readJson } from "../../lib/api";

type DocumentRow = {
  id: string;
  original_name: string;
  status: string;
  failure_code: string | null;
  failure_message: string | null;
};

type StatementRow = {
  id: string;
  account_alias: string;
  account_last4: string;
  period_start: string;
  period_end: string;
  closing_liability: string;
  computed_closing: string;
  difference: string;
  reconciliation: string;
  accept_reason: string | null;
};

type ReviewRow = {
  id: string;
  original_name: string;
  failure_code: string | null;
  failure_message: string | null;
  closing_liability: string | null;
  computed_closing: string | null;
  difference: string | null;
};

export function StatementsPage() {
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [statements, setStatements] = useState<StatementRow[]>([]);
  const [review, setReview] = useState<ReviewRow[]>([]);
  const [password, setPassword] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function load() {
    const [docs, posted, queue] = await Promise.all([
      readJson<{ documents: DocumentRow[] }>(await api("/api/v1/documents")),
      readJson<{ statements: StatementRow[] }>(await api("/api/v1/statements")),
      readJson<{ review: ReviewRow[] }>(await api("/api/v1/review")),
    ]);
    setDocuments(docs.documents);
    setStatements(posted.statements);
    setReview(queue.review);
  }

  useEffect(() => {
    load().catch((exc: unknown) => setError(exc instanceof ApiRequestError ? exc.message : "Statements could not be loaded."));
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!files || files.length === 0) return;
    setError("");
    setPending(true);
    try {
      const body = new FormData();
      const passwords = Array.from(files, () => password || null);
      Array.from(files).forEach((file) => body.append("files", file));
      body.append("passwords", JSON.stringify(passwords));
      const uploaded = await readJson<{ documents: DocumentRow[] }>(
        await api("/api/v1/imports", { method: "POST", body }),
      );
      setPassword("");
      setFiles(null);
      await load();
      const queued = uploaded.documents.filter((row) => row.status === "queued").map((row) => row.id);
      if (queued.length > 0) {
        window.setTimeout(() => {
          load().catch(() => undefined);
        }, 1500);
      }
    } catch (exc) {
      setError(exc instanceof ApiRequestError ? exc.message : "The upload could not be started.");
    } finally {
      setPending(false);
    }
  }

  async function accept(documentId: string) {
    setError("");
    try {
      await readJson(
        await api(`/api/v1/review/${documentId}/accept`, {
          method: "POST",
          body: JSON.stringify({ reason: reasons[documentId] ?? "" }),
        }),
      );
      await load();
    } catch (exc) {
      setError(exc instanceof ApiRequestError ? exc.message : "The file could not be accepted.");
    }
  }

  return (
    <section className="mx-auto max-w-3xl">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-secondary">SpendPilot</p>
      <h1 className="mt-2 text-[1.75rem] font-semibold leading-tight">Statements</h1>
      <p className="mt-3 max-w-2xl text-sm text-ink-secondary">
        Upload PDF statements. This build reads one synthetic generic AED card layout and does not name a bank. A wrong
        password fails that file only. OCR is not installed, so a scanned page stays unread.
      </p>
      {error ? <p className="mt-4 text-sm text-bad">{error}</p> : null}
      <form onSubmit={onSubmit} className="mt-6 grid gap-4 rounded-xl border border-line bg-surface p-6">
        <div className="grid gap-2">
          <Label htmlFor="statement-files">PDF files</Label>
          <Input
            id="statement-files"
            type="file"
            accept="application/pdf,.pdf"
            multiple
            onChange={(event) => setFiles(event.target.files)}
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="statement-password">Password for this batch, optional</Label>
          <Input
            id="statement-password"
            type="password"
            autoComplete="off"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>
        <Button type="submit" disabled={pending}>
          Upload
        </Button>
      </form>
      <h2 className="mt-8 text-base font-medium">Review</h2>
      {review.length === 0 ? <p className="mt-2 text-sm text-ink-secondary">Nothing is waiting for review.</p> : null}
      <ul className="mt-3 grid gap-3">
        {review.map((item) => (
          <li key={item.id} className="rounded-xl border border-line bg-surface p-4">
            <p className="font-medium">{item.original_name}</p>
            <p className="mt-1 text-sm text-ink-secondary">{item.failure_message}</p>
            {item.closing_liability ? (
              <p className="mt-2 text-sm">
                Stated {item.closing_liability} · Computed {item.computed_closing} · Difference {item.difference}
              </p>
            ) : null}
            <div className="mt-3 grid gap-2">
              <Label htmlFor={`reason-${item.id}`}>Reason</Label>
              <Input
                id={`reason-${item.id}`}
                value={reasons[item.id] ?? ""}
                onChange={(event) => setReasons({ ...reasons, [item.id]: event.target.value })}
              />
              <Button type="button" variant="secondary" onClick={() => accept(item.id)}>
                Accept with reason
              </Button>
            </div>
          </li>
        ))}
      </ul>
      <h2 className="mt-8 text-base font-medium">Posted statements</h2>
      <ul className="mt-3 grid gap-3">
        {statements.map((statement) => (
          <li key={statement.id} className="rounded-xl border border-line bg-surface p-4">
            <p className="font-medium">
              {statement.account_alias} ··{statement.account_last4}
            </p>
            <p className="mt-1 text-sm text-ink-secondary">
              {statement.period_start} to {statement.period_end}
            </p>
            <p className="mt-2 text-sm">Closing liability {statement.closing_liability} AED</p>
            <p className="mt-1 text-sm text-ink-secondary">
              {statement.reconciliation === "verified" ? "Verified" : "Accepted discrepancy"}
              {statement.accept_reason ? ` · ${statement.accept_reason}` : ""}
            </p>
          </li>
        ))}
      </ul>
      <h2 className="mt-8 text-base font-medium">Files</h2>
      <ul className="mt-3 grid gap-2">
        {documents.map((document) => (
          <li key={document.id} className="text-sm">
            <span className="font-medium">{document.original_name}</span>
            <span className="text-ink-secondary"> · {document.status.replaceAll("_", " ")}</span>
            {document.failure_message ? <span className="text-ink-secondary"> · {document.failure_message}</span> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
