from __future__ import annotations

from app.jobs.queue import get_queue_app
from app.workers.runtime import start_liveness_thread


def main() -> None:
    start_liveness_thread()
    get_queue_app().run_worker(queues=["agents"], name="agent-worker")


if __name__ == "__main__":
    main()
