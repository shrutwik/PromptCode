"""Run the persistent evaluation queue worker.

Usage:
    cd backend && python -m scripts.run_queue_worker
"""

from __future__ import annotations

import asyncio
import logging

from app.workers.queue import worker_loop


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
