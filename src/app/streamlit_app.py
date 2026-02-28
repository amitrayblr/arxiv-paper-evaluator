import json
from pathlib import Path

import streamlit as st

from src.object_types import IngestionResult
from src.services import IngestionService


@st.cache_resource
def _get_ingestion_service() -> IngestionService:
    return IngestionService()


def _render_ingestion_result(result: IngestionResult) -> None:
    st.subheader("Ingestion Result")

    status_text = "Cache Hit" if result.cache_hit else "Downloaded"
    col_article, col_status, col_size = st.columns(3)
    col_article.metric("Article ID", result.article_id)
    col_status.metric("Status", status_text)
    col_size.metric("PDF Size", f"{result.pdf_size_bytes} bytes")

    st.write(f"Validated URL: `{result.validated_url}`")
    st.write(f"PDF URL: `{result.pdf_url}`")

    with st.expander("Artifact Paths", expanded=False):
        st.write(f"Article directory: `{result.article_dir}`")
        st.write(f"PDF path: `{result.pdf_path}`")
        st.write(f"Metadata path: `{result.metadata_path}`")
        st.write(f"Ingestion log path: `{result.ingestion_log_path}`")

    metadata_path = Path(result.metadata_path)
    if metadata_path.exists():
        try:
            metadata_payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            with st.expander("Metadata", expanded=False):
                st.json(metadata_payload)
        except (OSError, json.JSONDecodeError):
            st.warning("Could not parse metadata.json")


def main() -> None:
    st.set_page_config(page_title="ArXiv Ingestion", page_icon="📄", layout="wide")

    st.title("ArXiv Ingestion")
    st.caption("Phase 1: URL -> metadata + PDF artifacts")

    raw_url = st.text_input(
        "ArXiv URL",
        placeholder="https://arxiv.org/abs/2502.01298v1",
    )

    if st.button("Run Ingestion", type="primary", use_container_width=True):
        try:
            result = _get_ingestion_service().ingest_from_url(raw_url)
            st.session_state["ingestion_result"] = result.to_dict()
        except (ValueError, LookupError, RuntimeError) as error:
            st.session_state.pop("ingestion_result", None)
            st.error(str(error))

    raw_result = st.session_state.get("ingestion_result")
    if isinstance(raw_result, dict):
        try:
            result = IngestionResult(**raw_result)
            _render_ingestion_result(result)
        except TypeError:
            st.warning("Could not read ingestion result from session state")


if __name__ == "__main__":
    main()
