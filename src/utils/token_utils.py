from functools import lru_cache
from typing import Any
from transformers import AutoTokenizer  # type: ignore[import-untyped]

from src.config import settings


@lru_cache(maxsize=1)
def _get_hf_tokenizer() -> Any:
    """Lazily create and cache a tokenizer for approximate token counting."""

    try:
        tokenizer = AutoTokenizer.from_pretrained(settings.cleaning_tokenizer_name)
        tokenizer.model_max_length = 10_000_000
        return tokenizer
    except Exception:
        return None


def estimate_token_count(text: str) -> int:
    """Estimate token count using a Hugging Face tokenizer, with a safe fallback."""

    sample = str(text or "")
    if not sample.strip():
        return 0

    tokenizer = _get_hf_tokenizer()
    if tokenizer is None:
        return len(sample.split())

    try:
        token_ids = tokenizer.encode(sample, add_special_tokens=False)
        return len(token_ids)
    except Exception:
        return len(sample.split())
