import re

from src.utils.text_utils import normalize_document_text


def normalize_string_list(values: object) -> list[str]:
    """Normalize a generic list into a list of non-empty strings."""

    if not isinstance(values, list):
        return []

    normalized_values: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue

        text = normalize_document_text(value)
        if text:
            normalized_values.append(text)

    return normalized_values


def normalize_int_list(values: object) -> list[int]:
    """Normalize a generic list into sorted unique integers."""

    if not isinstance(values, list):
        return []

    numbers: list[int] = []
    for value in values:
        if isinstance(value, int):
            numbers.append(value)

    return sorted(set(numbers))


def coerce_int(value: object, default: int = 0) -> int:
    """Return an integer value when possible, otherwise return a default."""

    if isinstance(value, int):
        return value
    return default


def classify_section_type(title: str) -> str:
    """Classify a section heading into body, references, or appendix."""

    normalized_title = title.strip().lower()

    if re.compile(r"^(references?|bibliography|works\s+cited)$", re.IGNORECASE).fullmatch(normalized_title):
        return "references"
    if re.compile(r"^(appendix|appendices|supplementary|supplemental)\b", re.IGNORECASE).match(normalized_title):
        return "appendix"

    return "body"


def infer_heading_level(title: str) -> int:
    """Infer heading depth from numbered prefixes like '2.1.3'."""

    match = re.compile(r"^(\d+(?:\.\d+)*)\b").match(title.strip())
    if not match:
        return 1

    number_path = match.group(1)
    return number_path.count(".") + 1


def is_page_number_line(text: str) -> bool:
    """Return True when a line looks like an isolated page number."""

    return bool(re.compile(r"^(?:page\s+)?\d{1,4}$", re.IGNORECASE).fullmatch(text.strip()))


def is_boilerplate_candidate(paragraph: str) -> bool:
    """Return True when a short paragraph is likely repetitive boilerplate."""

    line = paragraph.strip()

    if not line:
        return False
    if len(line) > 140:
        return False
    if len(line.split()) > 20:
        return False
    if is_page_number_line(line):
        return True

    return any(character.isalpha() for character in line)


def looks_like_heading(paragraph: str) -> bool:
    """Return True when a paragraph resembles a section heading."""

    line = paragraph.strip()

    if not line:
        return False
    if "\n" in line:
        return False
    if len(line) > 140:
        return False
    if line.endswith(".") and not re.compile(r"^(references?|bibliography|works\s+cited)$", re.IGNORECASE).fullmatch(line.lower()):
        return False

    word_count = len(line.split())
    if word_count == 0 or word_count > 16:
        return False

    return bool(re.compile(r"^(?:\d+(?:\.\d+)*\s+)?[A-Za-z][A-Za-z0-9\s,:;()\-]{2,120}$").fullmatch(line))
