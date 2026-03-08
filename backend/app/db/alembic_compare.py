from __future__ import annotations

from sqlalchemy import String, types

from app.db.types import GUID, JSONType

try:
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID
except ImportError:  # pragma: no cover
    PG_UUID = None


def compare_type(_context, _inspected_column, _metadata_column, inspected_type, metadata_type):
    """Suppress drift for platform-portable custom types.

    The repo's baseline migration stores UUIDs as VARCHAR(36) and JSON as the
    generic SQLAlchemy JSON type for cross-database compatibility. The runtime
    models use GUID/JSONType wrappers that adapt per dialect, so Alembic needs a
    narrow equivalence rule here to avoid reporting false drift.
    """

    if isinstance(metadata_type, GUID):
        if isinstance(inspected_type, String) and getattr(inspected_type, "length", None) == 36:
            return False
        if PG_UUID is not None and isinstance(inspected_type, PG_UUID):
            return False

    if isinstance(metadata_type, JSONType) and isinstance(inspected_type, types.JSON):
        return False

    return None
