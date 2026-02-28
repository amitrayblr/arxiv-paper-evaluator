import re
from urllib.parse import unquote, urlparse
from url_normalize import url_normalize


ARXIV_ID_PATTERN = re.compile(r"^(?:\d{4}\.\d{4,5}|[A-Za-z\-]+(?:\.[A-Za-z\-]+)?/\d{7})(?:v\d+)?$")


def _normalize_url(raw_url: str) -> str:
    if not isinstance(raw_url, str) or not raw_url.strip():
        raise ValueError("Invalid URL")

    candidate = raw_url.strip()

    # Reject malformed URLs
    if candidate.startswith("http:/") and not candidate.startswith("http://"):
        raise ValueError("Invalid URL")
    if candidate.startswith("https:/") and not candidate.startswith("https://"):
        raise ValueError("Invalid URL")
    if candidate.startswith("http//") or candidate.startswith("https//"):
        raise ValueError("Invalid URL")

    if "://" in candidate:
        scheme = candidate.split("://", 1)[0].lower()
        if scheme not in {"http", "https"}:
            raise ValueError("Invalid URL")

    normalized = url_normalize(candidate, default_scheme="https")
    if isinstance(normalized, str) and normalized:
        return normalized

    raise ValueError("Invalid URL")


def _path_parts(path: str) -> list[str]:
    decoded_path = unquote((path or "").strip())
    return [segment for segment in decoded_path.split("/") if segment]


def validate_arxiv_url(raw_url: str) -> str:
    """Validate an arXiv URL and return a normalized URL string."""

    normalized_url = _normalize_url(raw_url)
    parsed_url = urlparse(normalized_url)

    host = (parsed_url.hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]

    parts = _path_parts(parsed_url.path)
    if host != "arxiv.org" or len(parts) < 2 or parts[0] not in {"abs", "pdf", "html"}:
        raise ValueError("Invalid URL")

    return normalized_url


def extract_article_id(validated_url: str) -> str:
    """Extract article ID from a validated arXiv URL."""

    parsed_url = urlparse(validated_url)
    parts = _path_parts(parsed_url.path)

    if len(parts) < 2 or parts[0] not in {"abs", "pdf", "html"}:
        raise ValueError("Invalid URL")

    route = parts[0]
    article_id = "/".join(parts[1:]).strip().rstrip("/")

    if route == "pdf" and article_id.lower().endswith(".pdf"):
        article_id = article_id[:-4]

    if not article_id:
        raise ValueError("Invalid URL")

    return article_id


def validate_article_id(article_id: str) -> str:
    """Validate article ID format and return the cleaned ID."""

    if not isinstance(article_id, str) or not article_id.strip():
        raise ValueError("Article ID must be a non-empty string")

    cleaned_id = article_id.strip()

    if ARXIV_ID_PATTERN.fullmatch(cleaned_id):
        return cleaned_id

    raise ValueError(f"Invalid arXiv article ID: {cleaned_id!r}")
