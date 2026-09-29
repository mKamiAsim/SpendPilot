from __future__ import annotations

import sys
import time

from app.workers.runtime import ALIVE


def main() -> None:
    if not ALIVE.exists():
        raise SystemExit("Worker liveness file is missing.")
    age = time.time() - float(ALIVE.read_text().strip())
    if age > 30:
        raise SystemExit(f"Worker liveness is stale ({age:.0f}s).")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
