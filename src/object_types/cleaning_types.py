from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class CleaningChunkRecord:
    """Normalized representation of an extraction chunk for cleaning/sectioning."""

    chunk_id: int
    text: str
    headings: list[str]
    page_numbers: list[int]


@dataclass
class SectionHeader:
    """Internal section heading descriptor used during section assembly."""

    title: str
    section_type: str
    level: int
    heading_path: list[str]


@dataclass
class CleanSection:
    section_id: int
    title: str
    section_type: str
    section_level: int
    heading_path: list[str]
    text: str
    char_count: int
    estimated_tokens: int
    source_chunk_ids: list[int]
    page_numbers: list[int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AnalysisChunk:
    analysis_chunk_id: int
    section_id: int
    section_title: str
    section_type: str
    section_level: int
    heading_path: list[str]
    text: str
    char_count: int
    estimated_tokens: int
    page_numbers: list[int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CleaningResult:
    article_id: str
    article_dir: str
    extracted_text_path: str
    cleaned_text_path: str
    sections_path: str
    analysis_chunks_path: str
    cleaning_log_path: str
    cache_hit: bool
    section_count: int
    analysis_chunk_count: int
    cleaned_char_count: int
    max_tokens_per_chunk: int
    overlap_tokens: int
    timestamp_utc: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
