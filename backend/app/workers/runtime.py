from __future__ import annotations

import threading
import time
from pathlib import Path

ALIVE = Path("/tmp/spendpilot-worker-alive")


def mark_alive() -> None:
    ALIVE.write_text(str(time.time()))


def start_liveness_thread() -> None:
    def beat() -> None:
        while True:
            mark_alive()
            time.sleep(5)

    threading.Thread(target=beat, name="worker-liveness", daemon=True).start()
    mark_alive()
