from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ExtractedChunk:
    chunk_id: int
    text: str
    char_count: int
    page_numbers: list[int]
    headings: list[str]
    captions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExtractedDocument:
    text: str
    page_count: int
    chunks: list[ExtractedChunk]


@dataclass
class ExtractionResult:
    article_id: str
    article_dir: str
    source_pdf_path: str
    extracted_text_path: str
    chunks_path: str
    extraction_log_path: str
    cache_hit: bool
    chunk_count: int
    page_count: int
    text_char_count: int
    timestamp_utc: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
