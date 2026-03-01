from pathlib import Path

from src.config import settings
from src.object_types import (
    AnalysisChunk,
    CleaningChunkRecord,
    CleaningResult,
    CleanSection,
    SectionHeader,
)
from src.utils import (
    classify_section_type,
    coerce_int,
    deduplicate_consecutive_strings,
    estimate_token_count,
    infer_heading_level,
    is_boilerplate_candidate,
    is_non_empty_file,
    is_page_number_line,
    looks_like_heading,
    normalize_document_text,
    normalize_int_list,
    normalize_string_list,
    read_json_object,
    split_paragraphs,
    split_sentences,
    utc_now_iso,
    validate_article_id,
    write_json_object,
)


def _read_cached_cleaning_result(log_path: Path) -> CleaningResult | None:
    """Return a cached cleaning result when the cleaning log is valid."""

    if not is_non_empty_file(log_path):
        return None

    try:
        payload = read_json_object(log_path)
        return CleaningResult(**payload)
    except (OSError, TypeError, ValueError):
        return None


class CleaningService:
    """Clean extracted text, build sections, and produce analysis-ready chunks."""

    def clean_article(self, article_id: str) -> CleaningResult:
        normalized_article_id = validate_article_id(article_id)

        article_dir = Path(settings.data_articles_dir) / normalized_article_id
        extracted_text_path = article_dir / "extracted_text.txt"
        extracted_chunks_path = article_dir / "chunks.json"
        cleaned_text_path = article_dir / "cleaned_text.txt"
        sections_path = article_dir / "sections.json"
        analysis_chunks_path = article_dir / "analysis_chunks.json"
        cleaning_log_path = article_dir / "cleaning.json"

        cached_result = _read_cached_cleaning_result(cleaning_log_path)
        if (
            cached_result is not None
            and is_non_empty_file(cleaned_text_path)
            and is_non_empty_file(sections_path)
            and is_non_empty_file(analysis_chunks_path)
        ):
            cached_result.cache_hit = True
            return cached_result

        if not is_non_empty_file(extracted_text_path):
            raise ValueError(
                f"Missing extracted text for article '{normalized_article_id}'. Run extraction first."
            )

        raw_text = extracted_text_path.read_text(encoding="utf-8")
        chunk_records = self._read_chunk_records(extracted_chunks_path)

        cleaned_chunk_records = self._clean_chunk_records(chunk_records)
        cleaned_text = self._build_cleaned_text(cleaned_chunk_records, raw_text)

        sections = self._build_sections(cleaned_chunk_records, cleaned_text)
        analysis_chunks = self._build_analysis_chunks(sections)
        cleaned_text_path.write_text(cleaned_text, encoding="utf-8")
        write_json_object(
            sections_path,
            {
                "article_id": normalized_article_id,
                "sections": [section.to_dict() for section in sections],
            },
        )
        write_json_object(
            analysis_chunks_path,
            {
                "article_id": normalized_article_id,
                "max_tokens_per_chunk": settings.cleaning_max_tokens_per_chunk,
                "overlap_tokens": settings.cleaning_chunk_overlap_tokens,
                "chunks": [chunk.to_dict() for chunk in analysis_chunks],
            },
        )

        result = CleaningResult(
            article_id=normalized_article_id,
            article_dir=str(article_dir),
            extracted_text_path=str(extracted_text_path),
            cleaned_text_path=str(cleaned_text_path),
            sections_path=str(sections_path),
            analysis_chunks_path=str(analysis_chunks_path),
            cleaning_log_path=str(cleaning_log_path),
            cache_hit=False,
            section_count=len(sections),
            analysis_chunk_count=len(analysis_chunks),
            cleaned_char_count=len(cleaned_text),
            max_tokens_per_chunk=settings.cleaning_max_tokens_per_chunk,
            overlap_tokens=settings.cleaning_chunk_overlap_tokens,
            timestamp_utc=utc_now_iso(),
        )

        write_json_object(cleaning_log_path, result.to_dict())
        return result

    def _read_chunk_records(self, chunks_path: Path) -> list[CleaningChunkRecord]:
        """Read and normalize extraction chunks from disk."""

        if not is_non_empty_file(chunks_path):
            return []

        try:
            payload = read_json_object(chunks_path)
        except (OSError, ValueError):
            return []

        raw_chunks = payload.get("chunks")
        if not isinstance(raw_chunks, list):
            return []

        chunk_records: list[CleaningChunkRecord] = []
        for raw_chunk in raw_chunks:
            if not isinstance(raw_chunk, dict):
                continue

            chunk_text = normalize_document_text(str(raw_chunk.get("text", "")))
            if not chunk_text:
                continue

            chunk_records.append(
                CleaningChunkRecord(
                    chunk_id=coerce_int(raw_chunk.get("chunk_id")),
                    text=chunk_text,
                    headings=normalize_string_list(raw_chunk.get("headings")),
                    page_numbers=normalize_int_list(raw_chunk.get("page_numbers")),
                )
            )

        return chunk_records

    def _clean_chunk_records(self, chunks: list[CleaningChunkRecord]) -> list[CleaningChunkRecord]:
        """Drop repetitive boilerplate and normalize chunk text for sectioning."""

        if not chunks:
            return []

        boilerplate_paragraphs = self._detect_boilerplate_paragraphs(chunks)
        cleaned_chunks: list[CleaningChunkRecord] = []
        previous_chunk_text = ""

        for chunk in chunks:
            cleaned_paragraphs: list[str] = []
            for paragraph in split_paragraphs(chunk.text):
                normalized_paragraph = normalize_document_text(paragraph)
                if not normalized_paragraph:
                    continue
                if normalized_paragraph in boilerplate_paragraphs:
                    continue
                if is_page_number_line(normalized_paragraph):
                    continue
                cleaned_paragraphs.append(normalized_paragraph)

            cleaned_paragraphs = deduplicate_consecutive_strings(cleaned_paragraphs)
            cleaned_chunk_text = normalize_document_text("\n\n".join(cleaned_paragraphs))

            if not cleaned_chunk_text:
                continue
            if cleaned_chunk_text == previous_chunk_text:
                continue

            previous_chunk_text = cleaned_chunk_text
            cleaned_chunks.append(
                CleaningChunkRecord(
                    chunk_id=chunk.chunk_id,
                    text=cleaned_chunk_text,
                    headings=chunk.headings,
                    page_numbers=chunk.page_numbers,
                )
            )

        return cleaned_chunks

    def _detect_boilerplate_paragraphs(self, chunks: list[CleaningChunkRecord]) -> set[str]:
        """Detect short repeating paragraphs likely to be header/footer boilerplate."""

        paragraph_pages: dict[str, set[int]] = {}
        highest_page_number = 0

        for chunk in chunks:
            pages = set(chunk.page_numbers)
            if pages:
                highest_page_number = max(highest_page_number, max(pages))

            for paragraph in split_paragraphs(chunk.text):
                normalized_paragraph = normalize_document_text(paragraph)
                if not is_boilerplate_candidate(normalized_paragraph):
                    continue

                if normalized_paragraph not in paragraph_pages:
                    paragraph_pages[normalized_paragraph] = set()

                if pages:
                    paragraph_pages[normalized_paragraph].update(pages)
                else:
                    paragraph_pages[normalized_paragraph].add(0)

        page_threshold = 3
        if highest_page_number > 0:
            page_threshold = max(3, int(highest_page_number * 0.5))

        boilerplate: set[str] = set()
        for paragraph, pages in paragraph_pages.items():
            if len(pages) >= page_threshold:
                boilerplate.add(paragraph)

        return boilerplate

    def _build_cleaned_text(self, chunks: list[CleaningChunkRecord], raw_text: str) -> str:
        """Build full cleaned text from cleaned chunks, or fallback to cleaned raw text."""

        if chunks:
            return normalize_document_text("\n\n".join(chunk.text for chunk in chunks))

        cleaned_raw_text = normalize_document_text(raw_text)
        cleaned_paragraphs = [
            paragraph
            for paragraph in split_paragraphs(cleaned_raw_text)
            if not is_page_number_line(paragraph)
        ]
        cleaned_paragraphs = deduplicate_consecutive_strings(cleaned_paragraphs)
        return normalize_document_text("\n\n".join(cleaned_paragraphs))

    def _build_sections(
        self,
        cleaned_chunks: list[CleaningChunkRecord],
        cleaned_text: str,
    ) -> list[CleanSection]:
        """Build sections from chunk metadata when available, otherwise from text headings."""

        if cleaned_chunks:
            sections = self._build_sections_from_chunk_records(cleaned_chunks)
            if sections:
                return self._apply_section_hierarchy(sections)

        return self._apply_section_hierarchy(self._build_sections_from_text(cleaned_text))

    def _build_sections_from_chunk_records(
        self,
        chunks: list[CleaningChunkRecord],
    ) -> list[CleanSection]:
        """Assemble sections by grouping consecutive chunks under the same heading."""

        if not chunks:
            return []

        sections: list[CleanSection] = []
        current_header: SectionHeader | None = None
        current_text_parts: list[str] = []
        current_chunk_ids: list[int] = []
        current_page_numbers: set[int] = set()

        for chunk in chunks:
            header = self._header_from_chunk_record(chunk)

            if current_header is None:
                current_header = header

            if current_header != header:
                self._append_section(
                    sections=sections,
                    header=current_header,
                    text_parts=current_text_parts,
                    chunk_ids=current_chunk_ids,
                    page_numbers=sorted(current_page_numbers),
                )
                current_header = header
                current_text_parts = []
                current_chunk_ids = []
                current_page_numbers = set()

            current_text_parts.append(chunk.text)
            current_chunk_ids.append(chunk.chunk_id)
            current_page_numbers.update(chunk.page_numbers)

        if current_header is not None:
            self._append_section(
                sections=sections,
                header=current_header,
                text_parts=current_text_parts,
                chunk_ids=current_chunk_ids,
                page_numbers=sorted(current_page_numbers),
            )

        return sections

    def _build_sections_from_text(self, cleaned_text: str) -> list[CleanSection]:
        """Build sections by detecting heading-like paragraphs in cleaned text."""

        if not cleaned_text.strip():
            return []

        sections: list[CleanSection] = []
        current_header = self._header_from_title("Document")
        current_paragraphs: list[str] = []

        for paragraph in split_paragraphs(cleaned_text):
            if looks_like_heading(paragraph):
                self._append_section(
                    sections=sections,
                    header=current_header,
                    text_parts=current_paragraphs,
                    chunk_ids=[],
                    page_numbers=[],
                )
                current_header = self._header_from_title(paragraph)
                current_paragraphs = []
                continue

            current_paragraphs.append(paragraph)

        self._append_section(
            sections=sections,
            header=current_header,
            text_parts=current_paragraphs,
            chunk_ids=[],
            page_numbers=[],
        )

        if sections:
            return sections

        # If no heading boundaries are detected, keep the full document as one section.
        section_text = normalize_document_text(cleaned_text)
        return [
            CleanSection(
                section_id=1,
                title="Document",
                section_type="body",
                section_level=1,
                heading_path=["Document"],
                text=section_text,
                char_count=len(section_text),
                estimated_tokens=estimate_token_count(section_text),
                source_chunk_ids=[],
                page_numbers=[],
            )
        ]

    def _header_from_chunk_record(self, chunk: CleaningChunkRecord) -> SectionHeader:
        """Build a section header from chunk heading metadata."""

        if chunk.headings:
            heading_path: list[str] = []
            for heading in chunk.headings:
                normalized_heading = normalize_document_text(heading)
                if normalized_heading:
                    heading_path.append(normalized_heading)
            if heading_path:
                title = heading_path[-1]
                level = max(len(heading_path), infer_heading_level(title))
                return SectionHeader(
                    title=title,
                    section_type=classify_section_type(title),
                    level=level,
                    heading_path=heading_path,
                )

        return self._header_from_title("Document")

    def _header_from_title(self, title: str) -> SectionHeader:
        """Build a normalized section header from heading text."""

        normalized_title = normalize_document_text(title) or "Untitled Section"
        section_type = classify_section_type(normalized_title)

        if section_type in {"references", "appendix"}:
            level = 1
        else:
            level = max(1, infer_heading_level(normalized_title))

        return SectionHeader(
            title=normalized_title,
            section_type=section_type,
            level=level,
            heading_path=[normalized_title],
        )

    def _append_section(
        self,
        sections: list[CleanSection],
        header: SectionHeader,
        text_parts: list[str],
        chunk_ids: list[int],
        page_numbers: list[int],
    ) -> None:
        """Append a non-empty section assembled from text parts."""

        section_text = normalize_document_text("\n\n".join(text_parts))
        if not section_text:
            return

        sections.append(
            CleanSection(
                section_id=len(sections) + 1,
                title=header.title,
                section_type=header.section_type,
                section_level=header.level,
                heading_path=list(header.heading_path),
                text=section_text,
                char_count=len(section_text),
                estimated_tokens=estimate_token_count(section_text),
                source_chunk_ids=sorted(set(chunk_ids)),
                page_numbers=sorted(set(page_numbers)),
            )
        )

    def _apply_section_hierarchy(self, sections: list[CleanSection]) -> list[CleanSection]:
        """Normalize section hierarchy paths and levels across all sections."""

        if not sections:
            return []

        normalized_sections: list[CleanSection] = []
        active_path: list[str] = []

        for index, section in enumerate(sections, start=1):
            if section.section_type in {"references", "appendix"}:
                path = [section.title]
                level = 1
                active_path = [section.title]
            elif section.heading_path and section.heading_path != ["Document"]:
                path = list(section.heading_path)
                level = len(path)
                active_path = list(path)
            else:
                level = max(1, section.section_level)
                while len(active_path) >= level:
                    active_path.pop()
                active_path.append(section.title)
                path = list(active_path)

            normalized_sections.append(
                CleanSection(
                    section_id=index,
                    title=section.title,
                    section_type=section.section_type,
                    section_level=level,
                    heading_path=path,
                    text=section.text,
                    char_count=section.char_count,
                    estimated_tokens=section.estimated_tokens,
                    source_chunk_ids=section.source_chunk_ids,
                    page_numbers=section.page_numbers,
                )
            )

        return normalized_sections

    def _build_analysis_chunks(self, sections: list[CleanSection]) -> list[AnalysisChunk]:
        """Create token-aware analysis chunks from sections with overlap support."""

        max_tokens = max(256, int(settings.cleaning_max_tokens_per_chunk))
        overlap_tokens = max(0, int(settings.cleaning_chunk_overlap_tokens))
        overlap_tokens = min(overlap_tokens, max_tokens // 3)

        chunks: list[AnalysisChunk] = []
        next_chunk_id = 1

        for section in sections:
            units = self._build_section_units(section)
            if not units:
                continue

            current_parts: list[str] = []
            current_tokens = 0

            for unit in units:
                split_units = self._split_oversized_unit(unit, max_tokens)

                for split_unit in split_units:
                    split_tokens = estimate_token_count(split_unit)

                    if current_parts and current_tokens + split_tokens > max_tokens:
                        next_chunk_id = self._append_analysis_chunk(
                            chunks=chunks,
                            chunk_id=next_chunk_id,
                            section=section,
                            text_parts=current_parts,
                        )

                        chunk_text = normalize_document_text(" ".join(current_parts))
                        overlap_text = self._overlap_tail(chunk_text, overlap_tokens)

                        if overlap_text:
                            current_parts = [overlap_text]
                            current_tokens = estimate_token_count(overlap_text)
                        else:
                            current_parts = []
                            current_tokens = 0

                    current_parts.append(split_unit)
                    current_tokens += split_tokens

            if current_parts:
                next_chunk_id = self._append_analysis_chunk(
                    chunks=chunks,
                    chunk_id=next_chunk_id,
                    section=section,
                    text_parts=current_parts,
                )

        return self._deduplicate_analysis_chunks(chunks)

    def _build_section_units(self, section: CleanSection) -> list[str]:
        """Build deduplicated chunking units for a section."""

        if section.section_type == "references":
            raw_units = split_paragraphs(section.text)
        else:
            raw_units = split_sentences(section.text)

        normalized_units: list[str] = []
        for unit in raw_units:
            normalized_unit = normalize_document_text(unit)
            if normalized_unit:
                normalized_units.append(normalized_unit)

        units = deduplicate_consecutive_strings(normalized_units)
        if units:
            return units

        fallback_text = normalize_document_text(section.text)
        if fallback_text:
            return [fallback_text]

        return []

    def _split_oversized_unit(self, unit_text: str, max_tokens: int) -> list[str]:
        """Split a unit only when it exceeds the token limit."""

        normalized_unit = normalize_document_text(unit_text)
        if not normalized_unit:
            return []

        if estimate_token_count(normalized_unit) <= max_tokens:
            return [normalized_unit]

        return self._split_long_text_by_tokens(normalized_unit, max_tokens)

    def _split_long_text_by_tokens(self, text: str, max_tokens: int) -> list[str]:
        """Split long text into sub-units by word accumulation under token budget."""

        if max_tokens <= 0:
            return [text]

        words = text.split()
        if not words:
            return []

        parts: list[str] = []
        current_words: list[str] = []

        for word in words:
            tentative_words = current_words + [word]
            tentative_text = " ".join(tentative_words)

            if current_words and estimate_token_count(tentative_text) > max_tokens:
                parts.append(" ".join(current_words))
                current_words = [word]
            else:
                current_words = tentative_words

        if current_words:
            parts.append(" ".join(current_words))

        return [part for part in parts if part.strip()]

    def _overlap_tail(self, text: str, overlap_tokens: int) -> str:
        """Return trailing overlap text based on token-like word count."""

        if overlap_tokens <= 0:
            return ""

        words = text.split()
        if not words:
            return ""

        if len(words) <= overlap_tokens:
            return " ".join(words)

        return " ".join(words[-overlap_tokens:])

    def _append_analysis_chunk(
        self,
        chunks: list[AnalysisChunk],
        chunk_id: int,
        section: CleanSection,
        text_parts: list[str],
    ) -> int:
        """Append a non-empty analysis chunk and return the next chunk id."""

        chunk_text = normalize_document_text(" ".join(text_parts))
        if not chunk_text:
            return chunk_id

        chunks.append(
            AnalysisChunk(
                analysis_chunk_id=chunk_id,
                section_id=section.section_id,
                section_title=section.title,
                section_type=section.section_type,
                section_level=section.section_level,
                heading_path=list(section.heading_path),
                text=chunk_text,
                char_count=len(chunk_text),
                estimated_tokens=estimate_token_count(chunk_text),
                page_numbers=section.page_numbers,
            )
        )
        return chunk_id + 1

    def _deduplicate_analysis_chunks(self, chunks: list[AnalysisChunk]) -> list[AnalysisChunk]:
        """Drop duplicate chunk text and resequence chunk ids."""

        deduplicated: list[AnalysisChunk] = []
        seen_texts: set[str] = set()

        for chunk in chunks:
            normalized_text = normalize_document_text(chunk.text)
            if not normalized_text:
                continue
            if normalized_text in seen_texts:
                continue

            seen_texts.add(normalized_text)
            deduplicated.append(
                AnalysisChunk(
                    analysis_chunk_id=0,
                    section_id=chunk.section_id,
                    section_title=chunk.section_title,
                    section_type=chunk.section_type,
                    section_level=chunk.section_level,
                    heading_path=chunk.heading_path,
                    text=normalized_text,
                    char_count=len(normalized_text),
                    estimated_tokens=estimate_token_count(normalized_text),
                    page_numbers=chunk.page_numbers,
                )
            )

        for index, chunk in enumerate(deduplicated, start=1):
            chunk.analysis_chunk_id = index

        return deduplicated
