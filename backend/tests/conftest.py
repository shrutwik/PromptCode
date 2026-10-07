from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings

# Match a clean CI checkout; developer deployment credentials and budget caps
# must not change unit-test behavior. Tests can explicitly select a fixture file.
Settings.model_config["env_file"] = None
os.environ.setdefault("PROMPTCODE_JWT_SECRET", "ci-test-secret")
os.environ.setdefault("PROMPTCODE_DEBUG", "true")


def _isolated_artifact_root() -> None:
    """Point the interview artifact root at a throwaway directory for the session.

    Retention/accounting state (workspaces, immutable snapshots and the
    incremental storage ledger) is persistent by design. Without this, a test run
    would read and mutate the developer's real ``backend/data`` tree, which leaks
    state between runs and makes quota assertions depend on history. Tests that
    set ``PROMPTCODE_INTERVIEW_WORKSPACE_ROOT`` explicitly still take precedence.
    """
    if os.environ.get("PROMPTCODE_INTERVIEW_WORKSPACE_ROOT"):
        return
    root = tempfile.mkdtemp(prefix="promptcode-test-artifacts-")
    os.environ["PROMPTCODE_INTERVIEW_WORKSPACE_ROOT"] = root
    atexit.register(shutil.rmtree, root, True)


_isolated_artifact_root()
