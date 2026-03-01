from pathlib import Path

from src.clients import DoclingClient
from src.config import settings
from src.object_types import ExtractionResult
from src.utils import (
    is_non_empty_file,
    read_json_object,
    utc_now_iso,
    validate_article_id,
    write_json_object,
)


def _read_cached_extraction_result(log_path: Path) -> ExtractionResult | None:
    if not is_non_empty_file(log_path):
        return None

    try:
        payload = read_json_object(log_path)
        return ExtractionResult(**payload)
    except (OSError, TypeError, ValueError):
        return None


class ExtractionService:
    """Coordinates text extraction and chunk generation for an ingested article."""

    def extract_article(self, article_id: str) -> ExtractionResult:
        normalized_article_id = validate_article_id(article_id)

        article_dir = Path(settings.data_articles_dir) / normalized_article_id
        source_pdf_path = article_dir / "source.pdf"
        extracted_text_path = article_dir / "extracted_text.txt"
        chunks_path = article_dir / "chunks.json"
        extraction_log_path = article_dir / "extraction.json"

        cached_result = _read_cached_extraction_result(extraction_log_path)
        if cached_result and is_non_empty_file(extracted_text_path) and is_non_empty_file(chunks_path):
            cached_result.cache_hit = True
            return cached_result

        if not is_non_empty_file(source_pdf_path):
            raise ValueError(
                f"Missing source PDF for article '{normalized_article_id}'"
            )

        extracted_document = DoclingClient().extract_pdf(source_pdf_path)

        extracted_text_path.write_text(extracted_document.text, encoding="utf-8")
        write_json_object(
            chunks_path,
            {
                "article_id": normalized_article_id,
                "chunks": [chunk.to_dict() for chunk in extracted_document.chunks],
            },
        )

        result = ExtractionResult(
            article_id=normalized_article_id,
            article_dir=str(article_dir),
            source_pdf_path=str(source_pdf_path),
            extracted_text_path=str(extracted_text_path),
            chunks_path=str(chunks_path),
            extraction_log_path=str(extraction_log_path),
            cache_hit=False,
            chunk_count=len(extracted_document.chunks),
            page_count=extracted_document.page_count,
            text_char_count=len(extracted_document.text),
            timestamp_utc=utc_now_iso(),
        )

        write_json_object(extraction_log_path, result.to_dict())
        return result
