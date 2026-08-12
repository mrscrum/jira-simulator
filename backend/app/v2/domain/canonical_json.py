"""Stable JSON and semantic identity helpers for persisted v2 data."""

import hashlib
import json
from uuid import UUID, uuid5

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
CANONICAL_JSON_V1 = "RFC8785_JSON_V1"
SEMANTIC_ID_V1_NAMESPACE = UUID("0f896a61-4777-57d8-9e81-62c5c4ab2b7f")


def canonical_json(value: JsonValue) -> str:
    """Encode JSON data with deterministic UTF-8 compatible ordering."""
    return json.dumps(
        value, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )


def canonical_sha256(value: JsonValue) -> str:
    """Return the lower-case SHA-256 digest of canonical JSON bytes."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def semantic_uuid(path: str) -> UUID:
    """Derive the fixed-namespace UUIDv5 for one canonical semantic path."""
    return uuid5(SEMANTIC_ID_V1_NAMESPACE, path)
