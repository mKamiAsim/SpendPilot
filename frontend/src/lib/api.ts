import type { paths } from "./api-types";

export type ApiPaths = paths;

type ErrorBody = {
  error?: { code?: string; message?: string };
};

let csrfToken = "";

export class ApiRequestError extends Error {
  code: string;
  status: number;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export function rememberCsrf(token: string) {
  csrfToken = token;
}

export async function ensureCsrf() {
  if (csrfToken) return csrfToken;
  const response = await fetch("/api/v1/auth/csrf", { credentials: "include" });
  const body = (await response.json()) as { csrf_token: string };
  csrfToken = body.csrf_token;
  return csrfToken;
}

export async function api(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  const method = (init.method ?? "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD") {
    headers.set("X-CSRF-Token", await ensureCsrf());
    if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
  }
  return fetch(path, { ...init, headers, credentials: "include" });
}

export async function readJson<T>(response: Response): Promise<T> {
  const body = (await response.json()) as T & ErrorBody;
  if (!response.ok) {
    throw new ApiRequestError(
      response.status,
      body.error?.code ?? "request_failed",
      body.error?.message ?? "The request could not be completed.",
    );
  }
  return body;
}
