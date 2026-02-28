import arxiv

from src.config import settings
from src.object_types import ArxivPaperMetadata
from src.utils import clean_text, to_iso


class ArxivClient:
    """Thin wrapper around the `arxiv` package for metadata retrieval."""

    def __init__(
        self,
        page_size: int | None = None,
        delay_seconds: float | None = None,
        num_retries: int | None = None,
    ) -> None:
        self._page_size = page_size if page_size is not None else settings.arxiv_client_page_size
        self._delay_seconds = delay_seconds if delay_seconds is not None else settings.arxiv_client_delay_seconds
        self._num_retries = num_retries if num_retries is not None else settings.arxiv_client_num_retries
        self._client: arxiv.Client | None = None

    def fetch_metadata(self, article_id: str) -> ArxivPaperMetadata:
        """Fetch and normalize metadata for a single exact article ID."""

        normalized_article_id = article_id.strip()
        article = self._fetch_article_by_id(normalized_article_id)
        if article is None:
            raise LookupError(f"No arXiv metadata found for article ID: {normalized_article_id}")

        return self._build_metadata_from_article(article_id=normalized_article_id, article=article)

    def _get_client(self) -> arxiv.Client:
        if self._client is None:
            self._client = arxiv.Client(
                page_size=self._page_size,
                delay_seconds=self._delay_seconds,
                num_retries=self._num_retries,
            )
        return self._client

    def _fetch_article_by_id(self, article_id: str) -> arxiv.Result | None:
        search = arxiv.Search(id_list=[article_id], max_results=1)
        client = self._get_client()
        results = list(client.results(search))
        if not results:
            return None
        return results[0]

    def _build_metadata_from_article(self, article_id: str, article: arxiv.Result) -> ArxivPaperMetadata:
        authors: list[str] = []
        for author in article.authors or []:
            author_name = getattr(author, "name", None)
            if author_name:
                authors.append(str(author_name).strip())

        return ArxivPaperMetadata(
            article_id=article_id,
            title=clean_text(article.title),
            abstract=clean_text(article.summary),
            authors=authors,
            categories=list(article.categories or []),
            primary_category=article.primary_category,
            published=to_iso(article.published),
            updated=to_iso(article.updated),
            pdf_url=article.pdf_url,
            entry_id=article.entry_id,
            doi=article.doi,
            journal_ref=article.journal_ref,
            comment=article.comment,
        )
