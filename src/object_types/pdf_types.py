from dataclasses import dataclass


@dataclass
class PdfDownloadResult:
    """Details about a completed PDF download."""

    url: str
    output_path: str
    size_bytes: int
    content_type: str | None
