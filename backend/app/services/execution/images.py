"""Modal sandbox image requirements and build recipe.

The sandbox image must reproduce the Docker runner image layout, because the
service-owned command builders address those exact paths:

- ``/source``      candidate tree for one run (uploaded by the backend)
- ``/workspace``   writable working copy (built by the bootstrap/probe code)
- ``/opt/promptcode-deps/<slug>/node_modules``
                   reviewed per-challenge Node dependencies
- the runtime toolchain for the stack (node 20 / python 3.12 + pytest)

``docker/Dockerfile.interview-node`` builds ``/opt/promptcode-deps`` from the
repository's ``challenges/*/node_modules`` (about 608 MB across the six Node
challenges) and the probe bootstrap loads esbuild from that path, so the Modal
image needs the same layer at the same location. Candidate-submitted files are
never copied into an image.

Dependencies are baked **at build time**, not per run: sandbox creation only does
``modal.Image.from_registry`` on the reference published to
``PROMPTCODE_MODAL_SANDBOX_IMAGE_NODE``/``_PYTHON``, so no dependency upload
happens per graded job. :func:`challenge_dependency_mounts` returns the exact
local-to-sandbox directory pairs and :func:`build_sandbox_image` applies them to a
base registry image; call the latter from the Modal app definition
(``backend/modal_app.py``, owned by the deployment engineer) or from a one-off
``modal run`` build step, then set the two settings to the published reference.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .policy import DEPS_ROOT

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CHALLENGES_DIR = REPO_ROOT / "challenges"

# A slug becomes part of a sandbox path, so only registered-looking slugs are used.
_SAFE_SLUG = re.compile(r"[a-z0-9][a-z0-9-]*")

# The stack each sandbox image must satisfy. Kept beside the dependency layer so
# a rebuilt image is checked against both at once.
STACK_BASE_IMAGES = {
    "node": "node:20.19-bookworm-slim",
    "python": "python:3.12-slim-bookworm",
}


def challenge_dependency_mounts(
    challenges_dir: str | Path | None = None,
) -> dict[str, str]:
    """Map local ``challenges/<slug>/node_modules`` dirs to their sandbox paths.

    Returned pairs are ``{local_directory: remote_directory}`` suitable for
    ``modal.Image.add_local_dir``. Only real directories with a safe slug are
    included, so a stray file cannot inject a path into the image.
    """
    root = Path(challenges_dir) if challenges_dir is not None else DEFAULT_CHALLENGES_DIR
    mounts: dict[str, str] = {}
    if not root.is_dir():
        return mounts
    for node_modules in sorted(root.glob("*/node_modules")):
        slug = node_modules.parent.name
        if node_modules.is_dir() and _SAFE_SLUG.fullmatch(slug):
            mounts[str(node_modules)] = f"{DEPS_ROOT}/{slug}/node_modules"
    return mounts


def build_sandbox_image(
    modal: Any,
    *,
    base_image: str,
    challenges_dir: str | Path | None = None,
) -> Any:
    """Build-time recipe: a base image plus the per-challenge dependency layer.

    Not used when creating sandboxes. Build and publish once per stack, then point
    ``PROMPTCODE_MODAL_SANDBOX_IMAGE_NODE``/``_PYTHON`` at the result.
    """
    image = modal.Image.from_registry(base_image)
    for local_dir, remote_dir in challenge_dependency_mounts(challenges_dir).items():
        image = image.add_local_dir(local_dir, remote_dir)
    return image
