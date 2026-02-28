from dataclasses import dataclass


@dataclass
class ArxivPaperMetadata:
    """Normalized metadata returned by the arXiv client."""

    article_id: str
    title: str
    abstract: str
    authors: list[str]
    categories: list[str]
    primary_category: str | None
    published: str | None
    updated: str | None
    pdf_url: str | None
    entry_id: str | None
    doi: str | None
    journal_ref: str | None
    comment: str | None
