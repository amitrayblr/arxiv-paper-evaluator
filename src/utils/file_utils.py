import json
from pathlib import Path
from typing import Any


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


def is_non_empty_file(path: Path) -> bool:
    """Return True when the path exists, is a file, and has non-zero size."""

    return path.exists() and path.is_file() and path.stat().st_size > 0


def remove_file_if_exists(path: Path) -> None:
    """Delete a file if present; ignore missing file errors."""

    try:
        path.unlink()
    except FileNotFoundError:
        return
