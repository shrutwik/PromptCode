from __future__ import annotations

from sqlalchemy import String, types

from app.db.types import GUID, JSONType

try:
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID
except ImportError:  # pragma: no cover
    PG_UUID = None

_SQLITE_LEADERBOARD_UNIQUE_COLUMNS = ("challenge_id", "user_id")


def _column_names(object_) -> tuple[str, ...]:
    return tuple(column.name for column in getattr(object_, "columns", ()))


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

    if isinstance(metadata_type, JSONType) and isinstance(
        inspected_type, (types.JSON, types.Text)
    ):
        return False

    return None


def should_include_object(
    dialect_name: str,
    object_,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to,
) -> bool:
    """Hide SQLite's index/constraint representation mismatch for leaderboard."""

    if dialect_name != "sqlite" or name != "uq_leaderboard_challenge_user":
        return True

    if (
        type_ == "index"
        and reflected
        and getattr(object_, "unique", False)
        and _column_names(object_) == _SQLITE_LEADERBOARD_UNIQUE_COLUMNS
    ):
        return False

    if (
        type_ == "unique_constraint"
        and not reflected
        and _column_names(object_) == _SQLITE_LEADERBOARD_UNIQUE_COLUMNS
    ):
        return False

    return True
