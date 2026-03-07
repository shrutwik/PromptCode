"""Run the persistent evaluation queue worker.

Usage:
    cd backend && python -m scripts.run_queue_worker
"""

from __future__ import annotations

import asyncio

from app.core.logging import configure_logging
from app.workers.queue import worker_loop


def main() -> None:
    configure_logging()
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
