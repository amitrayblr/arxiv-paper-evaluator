from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    data_articles_dir: str = "data/articles"

    arxiv_client_page_size: int = 1
    arxiv_client_delay_seconds: float = 3.0
    arxiv_client_num_retries: int = 3

    pdf_connect_timeout_seconds: float = 10.0
    pdf_read_timeout_seconds: float = 60.0
    pdf_chunk_size: int = 8192
    pdf_user_agent: str = "arxiv-paper-evaluator/0.1"

    docling_artifacts_path: str = "data/docling-artifacts"

    cleaning_tokenizer_name: str = "bert-base-uncased"
    cleaning_max_tokens_per_chunk: int = 3000
    cleaning_chunk_overlap_tokens: int = 200

    @property
    def pdf_timeout(self) -> tuple[float, float]:
        return (self.pdf_connect_timeout_seconds, self.pdf_read_timeout_seconds)


settings = Settings()
