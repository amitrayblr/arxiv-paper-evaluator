from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Any


def clean_text(value: Any) -> str:
    """Convert any value to a trimmed string; return empty string for None."""

    if value is None:
        return ""
    return str(value).strip()


def to_iso(value: datetime | date | None) -> str | None:
    """Convert a date/datetime value to ISO string."""

    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def utc_now_iso() -> str:
    """Return current UTC timestamp as ISO string."""

    return datetime.now(timezone.utc).isoformat()


def read_json_object(path: Path) -> dict[str, Any]:
    """Read a JSON file and ensure the payload is an object."""

    with path.open("r", encoding="utf-8") as file_handle:
        payload = json.load(file_handle)

    if not isinstance(payload, dict):
        raise ValueError("Invalid JSON object")

    return payload


def write_json_object(path: Path, payload: dict[str, Any]) -> None:
    """Write an object as formatted JSON."""

    with path.open("w", encoding="utf-8") as file_handle:
        json.dump(payload, file_handle, indent=2, sort_keys=True)
