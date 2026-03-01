import json
from pathlib import Path
from typing import Any

import streamlit as st

from src.object_types import CleaningResult, ExtractionResult, IngestionResult
from src.services import CleaningService, ExtractionService, IngestionService


@st.cache_resource
def _get_ingestion_service() -> IngestionService:
    return IngestionService()


@st.cache_resource
def _get_extraction_service() -> ExtractionService:
    return ExtractionService()


@st.cache_resource
def _get_cleaning_service() -> CleaningService:
    return CleaningService()


def _clear_state_keys(*keys: str) -> None:
    for key in keys:
        st.session_state.pop(key, None)


def _save_result(key: str, result: Any) -> None:
    st.session_state[key] = result.to_dict()


def _read_result_payload(key: str) -> dict[str, Any] | None:
    payload = st.session_state.get(key)
    if isinstance(payload, dict):
        return payload
    return None


def _read_ingestion_result() -> IngestionResult | None:
    payload = _read_result_payload("ingestion_result")
    if payload is None:
        return None

    try:
        return IngestionResult(**payload)
    except TypeError:
        st.warning("Could not read ingestion result from session state")
        _clear_state_keys("ingestion_result")
        return None


def _read_extraction_result() -> ExtractionResult | None:
    payload = _read_result_payload("extraction_result")
    if payload is None:
        return None

    try:
        return ExtractionResult(**payload)
    except TypeError:
        st.warning("Could not read extraction result from session state")
        _clear_state_keys("extraction_result")
        return None


def _read_cleaning_result() -> CleaningResult | None:
    payload = _read_result_payload("cleaning_result")
    if payload is None:
        return None

    try:
        return CleaningResult(**payload)
    except TypeError:
        st.warning("Could not read cleaning result from session state")
        _clear_state_keys("cleaning_result")
        return None


def _render_ingestion_result(result: IngestionResult) -> None:
    st.subheader("Ingestion Result")

    status_text = "Cache Hit" if result.cache_hit else "Downloaded"
    col_article, col_status, col_size = st.columns(3)
    col_article.metric("Article ID", result.article_id)
    col_status.metric("Status", status_text)
    col_size.metric("PDF Size", f"{result.pdf_size_bytes} bytes")


def _render_extraction_result(result: ExtractionResult) -> None:
    st.subheader("Extraction + Chunking Result")

    status_text = "Cache Hit" if result.cache_hit else "Extracted"
    col_status, col_pages, col_chunks, col_chars = st.columns(4)
    col_status.metric("Status", status_text)
    col_pages.metric("Pages", str(result.page_count))
    col_chunks.metric("Chunks", str(result.chunk_count))
    col_chars.metric("Characters", str(result.text_char_count))


def _render_cleaning_result(result: CleaningResult) -> None:
    st.subheader("Cleaning + Sectioning Result")

    status_text = "Cache Hit" if result.cache_hit else "Processed"
    col_status, col_sections, col_analysis_chunks, col_chars = st.columns(4)
    col_status.metric("Status", status_text)
    col_sections.metric("Sections", str(result.section_count))
    col_analysis_chunks.metric("Analysis Chunks", str(result.analysis_chunk_count))
    col_chars.metric("Cleaned Characters", str(result.cleaned_char_count))

    st.write(f"Max tokens per analysis chunk: `{result.max_tokens_per_chunk}`")
    st.write(f"Chunk overlap tokens: `{result.overlap_tokens}`")

    sections_path = Path(result.sections_path)
    if not sections_path.exists():
        return

    try:
        payload = json.loads(sections_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        st.warning("Could not parse sections.json")
        return

    sections = payload.get("sections")
    if isinstance(sections, list) and sections:
        with st.expander("Section Preview", expanded=False):
            st.json(sections[:3])


def _run_ingestion(raw_url: str) -> None:
    try:
        ingestion_result = _get_ingestion_service().ingest_from_url(raw_url)
    except (ValueError, LookupError, RuntimeError) as error:
        _clear_state_keys("ingestion_result", "extraction_result", "cleaning_result")
        st.error(str(error))
        return

    _save_result("ingestion_result", ingestion_result)
    _clear_state_keys("extraction_result", "cleaning_result")


def _run_extraction(article_id: str) -> None:
    try:
        extraction_result = _get_extraction_service().extract_article(article_id)
    except (ValueError, RuntimeError) as error:
        _clear_state_keys("extraction_result", "cleaning_result")
        st.error(str(error))
        return

    _save_result("extraction_result", extraction_result)
    _clear_state_keys("cleaning_result")


def _run_cleaning(article_id: str) -> None:
    try:
        cleaning_result = _get_cleaning_service().clean_article(article_id)
    except ValueError as error:
        _clear_state_keys("cleaning_result")
        st.error(str(error))
        return

    _save_result("cleaning_result", cleaning_result)


def main() -> None:
    st.set_page_config(page_title="ArXiv Ingestion + Extraction + Cleaning", page_icon="📄", layout="wide")

    st.title("ArXiv Ingestion + Extraction + Cleaning")
    st.caption("Phase 1-3: ingestion, extraction/chunking, cleaning/sectioning")

    raw_url = st.text_input("ArXiv URL")

    if st.button("Run Ingestion", type="primary", use_container_width=True):
        _run_ingestion(raw_url)

    ingestion_result = _read_ingestion_result()
    if ingestion_result is not None:
        _render_ingestion_result(ingestion_result)

        if st.button("Run Extraction + Chunking", use_container_width=True):
            _run_extraction(ingestion_result.article_id)

    extraction_result = _read_extraction_result()
    if extraction_result is not None:
        _render_extraction_result(extraction_result)

        if st.button("Run Cleaning + Sectioning", use_container_width=True):
            _run_cleaning(extraction_result.article_id)

    cleaning_result = _read_cleaning_result()
    if cleaning_result is not None:
        _render_cleaning_result(cleaning_result)


if __name__ == "__main__":
    main()
