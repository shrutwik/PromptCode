"""Run the persistent evaluation queue worker.

Usage:
    cd backend && python -m scripts.run_queue_worker
"""

from __future__ import annotations

import asyncio

from app.core.logging import configure_logging
from app.core.config import get_settings
from app.core.startup_security import validate_production_startup
from app.workers.queue import worker_loop


def main() -> None:
    configure_logging()
    validate_production_startup(get_settings())
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
