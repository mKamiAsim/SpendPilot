# ADR 0006: Version pins

Date: 29 September 2026

Pins below were read from the registries on this date. They are not remembered from an earlier draft.

## Backend

PyPI JSON `info.version` on 29 September 2026, locked in `backend/pyproject.toml` and `backend/uv.lock`:

| Package | Pin |
|---|---|
| fastapi | 0.141.1 |
| pydantic | 2.13.5 |
| pydantic-settings | 2.15.0 |
| SQLAlchemy | 2.1.1 (`[asyncio]`) |
| greenlet | 3.5.6 |
| alembic | 1.20.0 |
| psycopg | 3.3.6 (`[binary,pool]`) |
| uvicorn | 0.54.0 |
| argon2-cffi | 25.1.0 |
| cryptography | 50.0.1 |
| email-validator | 2.3.0 |
| procrastinate | 3.10.0 |
| httpx | 0.28.1 |
| hatchling | 1.32.4 |
| pytest | 9.1.1 |
| pytest-asyncio | 1.4.0 |
| uv | 0.12.20 |

Optional extras are locked and not installed in the runtime image: `pypdf` 6.19.0, `pikepdf` 10.15.0, `pdfplumber` 0.11.10, `ocrmypdf` 17.13.0, `langchain` 1.4.3, `langgraph` 1.2.12, `deepagents` 0.7.19.

## Frontend

npm `latest` on 29 September 2026, except TypeScript:

| Package | Pin |
|---|---|
| react / react-dom | 19.3.0 |
| vite | 8.3.1 |
| @vitejs/plugin-react | 6.1.1 |
| tailwindcss / @tailwindcss/vite | 4.3.3 |
| @tanstack/react-query | 5.104.0 |
| @tanstack/react-table | 9.2.4 |
| react-hook-form | 7.89.0 |
| @hookform/resolvers | 5.9.1 |
| zod | 4.6.5 |
| recharts | 3.10.1 |
| react-router | 8.4.0 |
| @fontsource/inter | 5.3.0 |
| lucide-react | 1.48.0 |
| @radix-ui/react-slot | 1.3.3 |
| class-variance-authority | 0.7.1 |
| clsx | 2.1.1 |
| tailwind-merge | 3.7.0 |
| openapi-fetch | 0.17.0 |
| openapi-typescript | 7.13.0 |
| @playwright/test | 1.63.0 |
| @types/react / @types/react-dom | 19.3.0 |
| typescript | 5.9.3 |

npm `latest` for TypeScript that day was 7.0.2. `openapi-typescript` 7.13.0 declares a peer of TypeScript `^5`, so the app pins 5.9.3, which exists on the registry. TanStack Table and Recharts are dependencies for later screens. The foundation shell does not render a table or a chart.

`react-router` 8.4.0 asks for Node `>=22.22.0`. The gateway image uses `node:22.23.3-bookworm-slim` because Node 22.23.3 was the newest 22.x release on nodejs.org (`dist/index.json`, 23 September 2026).

## PostgreSQL

`https://www.postgresql.org/versions.json` on 29 September 2026 lists major 18 as `current: true` with `latestMinor` 6 (release date 13 August 2026). The Compose image is `postgres:18.6`. Major 19 is not the current stable line. Postgres is not published on a host port.

## Base images

Digests observed when Compose built on 29 September 2026:

| Tag | Digest |
|---|---|
| `postgres:18.6` | `sha256:5a5a84b19854a9ffaa54082c166ff4ec27473a361e496e5ea167f298f2da9722` |
| `python:3.12-slim-bookworm` | `sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e` (CPython 3.12.14) |
| `ghcr.io/astral-sh/uv:0.12.20` | `sha256:100047e74f30778ab704942321a09750d6158739573ff58bf3924085cc6cd2d8` |
| `node:22.23.3-bookworm-slim` | `sha256:43ac6c60b8f89723f746e8a92ce91abd5017e627ce1ddfe4238355d3a30b772c` |
| `nginxinc/nginx-unprivileged:1.29-alpine` | `sha256:0c79d56aee561a1d81c63f00eee5fb5fe29279560cdc55e91425133104c7fbe6` (nginx 1.29.8) |

The official Postgres image starts as root and then drops to the `postgres` user. The API, both workers, and the gateway run as non-root. These digests are build inputs, not a production-hardening claim.
