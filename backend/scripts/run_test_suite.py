"""Run the backend test suite hermetically, matching CI.

The application ``Settings`` class reads the repository ``.env`` when it exists, so
a developer machine with a populated ``.env`` runs a different configuration than
CI (which has no ``.env``). Concretely, a local ``.env`` that points the AI
provider at DeepSeek makes the legacy-key substitution fire, which changes which
startup-validation errors are reported and therefore which assertions pass. That
is why the documented ``pytest -q`` command can fail locally on tests that assert
on default/placeholder configuration.

This runner imports ``app.core.config`` first, disables its ``env_file`` source for
the duration of the session, then hands control to pytest. Real environment
variables still apply, so ``PROMPTCODE_JWT_SECRET=ci-test-secret`` reaches the
application exactly as it does in CI. No file on disk is modified.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main(argv: list[str] | None = None) -> int:
    import app.core.config as config

    config.Settings.model_config["env_file"] = None
    import pytest

    exit_code = int(pytest.main(argv if argv is not None else sys.argv[1:]))
    # Some tests build a FastAPI lifespan (background worker/reaper tasks). pytest
    # can then block in interpreter shutdown waiting on those non-daemon threads,
    # which looks like a hang. Flush and exit deterministically instead.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)


if __name__ == "__main__":
    main()
