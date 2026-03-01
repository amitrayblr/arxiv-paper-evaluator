from datetime import date, datetime, timezone
import re
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


def _normalize_line(line: str) -> str:
    """Collapse extra inline whitespace inside a single line."""

    return re.compile(r"[ \t]+").sub(" ", line).strip()


def _should_merge_lines(previous_line: str, next_line: str) -> bool:
    """Decide whether two adjacent lines likely belong to one sentence."""

    if not previous_line or not next_line:
        return False

    if previous_line.endswith((".", "!", "?", ":")):
        return False

    if previous_line.endswith("-"):
        return True

    if next_line.startswith(("-", "*", "•")):
        return False

    if next_line[:1].isupper() and previous_line.endswith((")", "]")):
        return False

    return True


def normalize_document_text(text: str) -> str:
    """Normalize whitespace, repair broken lines, and preserve paragraph breaks."""

    source_text = str(text or "")
    source_text = source_text.replace("\r\n", "\n").replace("\r", "\n")
    source_text = re.sub(r"(\w)-\n(\w)", r"\1\2", source_text)

    paragraphs: list[str] = []
    current_paragraph_lines: list[str] = []

    for raw_line in source_text.split("\n"):
        normalized_line = _normalize_line(raw_line)

        if not normalized_line:
            if current_paragraph_lines:
                paragraphs.append("\n".join(current_paragraph_lines))
                current_paragraph_lines = []
            continue

        if not current_paragraph_lines:
            current_paragraph_lines.append(normalized_line)
            continue

        previous_line = current_paragraph_lines[-1]
        if _should_merge_lines(previous_line, normalized_line):
            if previous_line.endswith("-"):
                current_paragraph_lines[-1] = previous_line[:-1] + normalized_line
            else:
                current_paragraph_lines[-1] = f"{previous_line} {normalized_line}".strip()
        else:
            current_paragraph_lines.append(normalized_line)

    if current_paragraph_lines:
        paragraphs.append("\n".join(current_paragraph_lines))

    compact_text = "\n\n".join(paragraphs)
    compact_text = re.compile(r"\n{3,}").sub("\n\n", compact_text)

    return compact_text.strip()


def split_paragraphs(text: str) -> list[str]:
    """Split normalized text into non-empty paragraphs."""

    paragraphs = [part.strip() for part in str(text or "").split("\n\n")]
    return [paragraph for paragraph in paragraphs if paragraph]


def split_sentences(text: str) -> list[str]:
    """Split text into sentence-like units while preserving non-empty chunks."""

    normalized_text = normalize_document_text(text)
    if not normalized_text:
        return []

    raw_sentences = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])").split(normalized_text)
    sentences = [sentence.strip() for sentence in raw_sentences if sentence.strip()]

    if sentences:
        return sentences

    return split_paragraphs(normalized_text)


def deduplicate_consecutive_strings(values: list[str]) -> list[str]:
    """Remove only adjacent duplicates while preserving ordering."""

    deduplicated: list[str] = []
    for value in values:
        if not deduplicated or deduplicated[-1] != value:
            deduplicated.append(value)
    return deduplicated
