from pathlib import Path

from docling.chunking import HierarchicalChunker
from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.document import ConversionResult
from docling.datamodel.pipeline_options import LayoutOptions, PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.utils.model_downloader import download_models
from docling_core.types.doc import DoclingDocument
from docling_core.types.doc.document import DocItem

from src.config import settings
from src.object_types import ExtractedChunk, ExtractedDocument


def get_docling_artifacts_dir() -> Path:
    artifacts_dir = Path(settings.docling_artifacts_path).expanduser()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir


def prefetch_docling_models(force: bool = False, progress: bool = True) -> Path:
    """Download required Docling models into the configured local artifacts directory."""

    artifacts_dir = get_docling_artifacts_dir()

    download_models(
        output_dir=artifacts_dir,
        force=force,
        progress=progress,
        with_layout=True,
        with_tableformer=True,
        with_code_formula=True,
        with_picture_classifier=True,
        with_rapidocr=True,
    )

    return artifacts_dir


def _has_required_layout_artifacts(artifacts_dir: Path) -> bool:
    layout_folder = artifacts_dir / LayoutOptions().model_spec.model_repo_folder
    required_files = [
        layout_folder / "model.safetensors",
        layout_folder / "config.json",
        layout_folder / "preprocessor_config.json",
    ]
    return all(path.is_file() for path in required_files)


class DoclingClient:
    """Convert PDF files into text and structured chunks using Docling."""

    def __init__(self) -> None:
        self._converter: DocumentConverter | None = None
        self._chunker: HierarchicalChunker | None = None

    def extract_pdf(self, pdf_path: str | Path) -> ExtractedDocument:
        source_path = Path(pdf_path)
        if not source_path.exists():
            raise ValueError(f"PDF file not found: {source_path}")

        conversion_result = self._convert_pdf(source_path)
        if conversion_result.status in {ConversionStatus.FAILURE, ConversionStatus.SKIPPED}:
            message = self._build_failure_message(conversion_result.errors)
            raise RuntimeError(f"Docling extraction failed: {message}")

        extracted_document = conversion_result.document
        extracted_text = extracted_document.export_to_text()
        extracted_chunks = self._build_chunks(extracted_document)
        return ExtractedDocument(
            text=extracted_text,
            page_count=len(conversion_result.pages),
            chunks=extracted_chunks,
        )

    def _convert_pdf(self, source_path: Path) -> ConversionResult:
        try:
            return self._get_converter().convert(source_path)
        except Exception as error:  # pragma: no cover - network/model setup dependent
            error_message = str(error).strip() or "unknown error"
            raise RuntimeError(
                "Docling conversion failed. Ensure Docling model artifacts are available in "
                f"'{settings.docling_artifacts_path}'. Details: {error_message}"
            ) from error

    def _ensure_models_available(self) -> None:
        artifacts_dir = get_docling_artifacts_dir()
        if _has_required_layout_artifacts(artifacts_dir):
            return

        try:
            prefetch_docling_models(force=False, progress=True)
        except Exception as error:
            error_message = str(error).strip() or "unknown error"
            raise RuntimeError(
                "Docling model auto-download failed. "
                "Run prefetch_docling_models() manually. "
                f"Details: {error_message}"
            ) from error

    def _get_converter(self) -> DocumentConverter:
        if self._converter is None:
            self._ensure_models_available()

            pdf_pipeline = PdfPipelineOptions(
                do_ocr=False,
                do_table_structure=False,
                force_backend_text=True,
                enable_remote_services=False,
            )
            pdf_pipeline.artifacts_path = str(get_docling_artifacts_dir())

            pdf_option = PdfFormatOption(pipeline_options=pdf_pipeline)
            self._converter = DocumentConverter(format_options={InputFormat.PDF: pdf_option})

        return self._converter

    def _get_chunker(self) -> HierarchicalChunker:
        if self._chunker is None:
            self._chunker = HierarchicalChunker(
                delim="\n\n",
                merge_list_items=True,
                always_emit_headings=True,
            )

        return self._chunker

    def _build_chunks(self, extracted_document: DoclingDocument) -> list[ExtractedChunk]:
        chunks: list[ExtractedChunk] = []

        for index, raw_chunk in enumerate(self._get_chunker().chunk(extracted_document), start=1):
            chunk_text = raw_chunk.text.strip()
            if not chunk_text:
                continue

            metadata = raw_chunk.meta
            page_numbers = self._extract_page_numbers(getattr(metadata, "doc_items", []))
            headings = self._normalize_string_list(getattr(metadata, "headings", []))
            captions = self._normalize_string_list(getattr(metadata, "captions", []))

            chunks.append(
                ExtractedChunk(
                    chunk_id=index,
                    text=chunk_text,
                    char_count=len(chunk_text),
                    page_numbers=page_numbers,
                    headings=headings,
                    captions=captions,
                )
            )

        return chunks

    def _extract_page_numbers(self, doc_items: object) -> list[int]:
        if not isinstance(doc_items, list):
            return []

        pages: set[int] = set()
        for item in doc_items:
            if not isinstance(item, DocItem):
                continue

            for provenance in item.prov:
                page_no = provenance.page_no
                if isinstance(page_no, int) and page_no > 0:
                    pages.add(page_no)

        return sorted(pages)

    def _normalize_string_list(self, values: object) -> list[str]:
        if not isinstance(values, list):
            return []

        normalized_values: list[str] = []
        for value in values:
            if not isinstance(value, str):
                continue

            text = value.strip()
            if text:
                normalized_values.append(text)

        return normalized_values

    def _build_failure_message(self, errors: object) -> str:
        if not isinstance(errors, list) or not errors:
            return "unknown conversion failure"

        messages: list[str] = []
        for error in errors:
            text = str(error).strip()
            if text:
                messages.append(text)

        if not messages:
            return "unknown conversion failure"

        return "; ".join(messages)
