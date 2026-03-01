from pathlib import Path
from typing import Iterable

import requests

from src.config import settings
from src.object_types import PdfDownloadResult
from src.utils import remove_file_if_exists


def download_pdf(pdf_url: str, output_path: str | Path) -> PdfDownloadResult:
    """Download a PDF to disk with content validation."""

    output_file_path = Path(output_path)
    output_file_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with requests.get(
            pdf_url,
            headers={"User-Agent": settings.pdf_user_agent},
            stream=True,
            timeout=settings.pdf_timeout,
        ) as response:
            response.raise_for_status()
            content_type = _validate_pdf_content_type(response.headers.get("Content-Type"))
            downloaded_size = _save_pdf_chunks(
                chunks=response.iter_content(chunk_size=settings.pdf_chunk_size),
                output_file_path=output_file_path,
            )
    except requests.RequestException as error:
        remove_file_if_exists(output_file_path)
        raise RuntimeError(f"Failed to download PDF: {pdf_url}") from error
    except (OSError, ValueError):
        remove_file_if_exists(output_file_path)
        raise

    return PdfDownloadResult(
        url=pdf_url,
        output_path=str(output_file_path),
        size_bytes=downloaded_size,
        content_type=content_type,
    )


def _validate_pdf_content_type(content_type_header: str | None) -> str | None:
    normalized_content_type = (content_type_header or "").lower().strip()

    if not normalized_content_type:
        return None

    if "pdf" in normalized_content_type or "octet-stream" in normalized_content_type:
        return normalized_content_type

    raise ValueError(f"Expected PDF response, got Content-Type: {normalized_content_type}")


def _save_pdf_chunks(chunks: Iterable[bytes], output_file_path: Path) -> int:
    total_size = 0
    header_sample = b""

    with output_file_path.open("wb") as output_file:
        for chunk in chunks:
            if not chunk:
                continue

            if len(header_sample) < 8:
                bytes_needed = 8 - len(header_sample)
                header_sample += chunk[:bytes_needed]

            output_file.write(chunk)
            total_size += len(chunk)

    if total_size == 0:
        raise ValueError("Downloaded response was empty")

    if not header_sample.lstrip().startswith(b"%PDF"):
        raise ValueError("Downloaded file does not appear to be a valid PDF")

    return total_size
