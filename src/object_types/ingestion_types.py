from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class IngestionResult:
    """Result payload for a single ingestion run."""

    input_url: str
    validated_url: str
    article_id: str
    article_dir: str
    metadata_path: str
    pdf_path: str
    ingestion_log_path: str
    pdf_url: str
    cache_hit: bool
    downloaded_pdf: bool
    pdf_size_bytes: int
    timestamp_utc: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
