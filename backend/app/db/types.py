"""Database-agnostic column types.

Provides UUID, JSON, and StringList types that work with both
PostgreSQL (native UUID, JSONB, ARRAY) and SQLite (CHAR(36), JSON, TEXT
with comma separation).
"""
from __future__ import annotations

import json
import uuid

from sqlalchemy import String, Text, TypeDecorator, types

try:
    from sqlalchemy.dialects.postgresql import ARRAY, JSONB
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID

    _HAS_PG = True
except ImportError:  # pragma: no cover
    _HAS_PG = False


class GUID(TypeDecorator):
    """Platform-independent UUID type.

    Uses PostgreSQL's native UUID when available, otherwise stores as
    CHAR(36) in SQLite / other dialects.
    """

    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if _HAS_PG and dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(value)
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(str(value))
        return value


class JSONType(TypeDecorator):
    """Platform-independent JSON type.

    Uses PostgreSQL's JSONB when available, otherwise uses SQLAlchemy's
    generic JSON (which maps to TEXT/JSON in SQLite).
    """

    impl = types.JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if _HAS_PG and dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB)
        return dialect.type_descriptor(types.JSON)


class StringList(TypeDecorator):
    """Platform-independent list-of-strings type.

    Uses PostgreSQL's ARRAY(String) when available, otherwise stores as
    a JSON-encoded TEXT column in SQLite.
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if _HAS_PG and dialect.name == "postgresql":
            return dialect.type_descriptor(ARRAY(String))
        return dialect.type_descriptor(Text)

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return []
        if dialect.name == "postgresql":
            return value
        if isinstance(value, str):
            return json.loads(value)
        return value
