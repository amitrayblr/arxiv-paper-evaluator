from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.clients import ArxivClient, download_pdf
from src.config import settings
from src.object_types import IngestionResult
from src.utils import (
    extract_article_id,
    read_json_object,
    utc_now_iso,
    validate_article_id,
    validate_arxiv_url,
    write_json_object,
)

METADATA_FILENAME = "metadata.json"
PDF_FILENAME = "source.pdf"
INGESTION_LOG_FILENAME = "ingestion.json"


def _read_cached_pdf_url(metadata_path: Path) -> str | None:
    if not metadata_path.exists():
        return None

    try:
        metadata_payload = read_json_object(metadata_path)
    except (OSError, ValueError):
        return None

    pdf_url = metadata_payload.get("pdf_url")
    if not isinstance(pdf_url, str) or not pdf_url.strip():
        return None

    return pdf_url.strip()


class IngestionService:
    """Coordinates URL validation, metadata fetch, cache checks, and persistence."""

    def ingest_from_url(self, raw_url: str) -> IngestionResult:
        """Run ingestion for an arXiv URL and persist all artifacts."""

        validated_url = validate_arxiv_url(raw_url)
        article_id = validate_article_id(extract_article_id(validated_url))

        article_dir = Path(settings.data_articles_dir) / article_id
        article_dir.mkdir(parents=True, exist_ok=True)

        metadata_path = article_dir / METADATA_FILENAME
        pdf_path = article_dir / PDF_FILENAME
        ingestion_log_path = article_dir / INGESTION_LOG_FILENAME

        timestamp_utc = utc_now_iso()

        cached_pdf_url = _read_cached_pdf_url(metadata_path)
        if cached_pdf_url and pdf_path.exists() and pdf_path.stat().st_size > 0:
            result = IngestionResult(
                input_url=raw_url.strip(),
                validated_url=validated_url,
                article_id=article_id,
                article_dir=str(article_dir),
                metadata_path=str(metadata_path),
                pdf_path=str(pdf_path),
                ingestion_log_path=str(ingestion_log_path),
                pdf_url=cached_pdf_url,
                cache_hit=True,
                downloaded_pdf=False,
                pdf_size_bytes=pdf_path.stat().st_size,
                timestamp_utc=timestamp_utc,
            )
            write_json_object(
                ingestion_log_path,
                {**result.to_dict(), "logged_at_utc": utc_now_iso()},
            )
            return result

        metadata = ArxivClient().fetch_metadata(article_id)

        pdf_url = metadata.pdf_url.strip() if isinstance(metadata.pdf_url, str) else ""
        if not pdf_url:
            raise ValueError("Missing PDF URL in metadata")

        download_result = download_pdf(pdf_url, pdf_path)

        metadata_payload: dict[str, Any] = asdict(metadata)
        metadata_payload["input_url"] = raw_url.strip()
        metadata_payload["validated_url"] = validated_url
        metadata_payload["article_id"] = article_id
        metadata_payload["fetched_at_utc"] = timestamp_utc
        write_json_object(metadata_path, metadata_payload)

        result = IngestionResult(
            input_url=raw_url.strip(),
            validated_url=validated_url,
            article_id=article_id,
            article_dir=str(article_dir),
            metadata_path=str(metadata_path),
            pdf_path=str(pdf_path),
            ingestion_log_path=str(ingestion_log_path),
            pdf_url=pdf_url,
            cache_hit=False,
            downloaded_pdf=True,
            pdf_size_bytes=download_result.size_bytes,
            timestamp_utc=timestamp_utc,
        )
        write_json_object(
            ingestion_log_path,
            {**result.to_dict(), "logged_at_utc": utc_now_iso()},
        )
        return result
