"""Local exact-vector retrieval with a replaceable embedding provider."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class EmbeddingProvider(Protocol):
    provider_id: str
    version: str

    def encode(self, texts: list[str]): ...


@dataclass
class HashingEmbeddingProvider:
    """Offline, deterministic baseline using word and character feature hashing.

    This is intentionally described as a related-language baseline, not a deep
    semantic model. A locally installed sentence-transformer can implement the
    same protocol without changing vault or search contracts.
    """

    dimensions: int = 4096
    provider_id = "sklearn-hashing-word-char"
    version = "1.0.0"

    def encode(self, texts: list[str]):
        from scipy.sparse import hstack
        from sklearn.feature_extraction.text import HashingVectorizer
        from sklearn.preprocessing import normalize

        word = HashingVectorizer(
            n_features=self.dimensions,
            alternate_sign=False,
            norm=None,
            ngram_range=(1, 2),
            stop_words="english",
        ).transform(texts)
        char = HashingVectorizer(
            analyzer="char_wb",
            n_features=self.dimensions,
            alternate_sign=False,
            norm=None,
            ngram_range=(3, 5),
        ).transform(texts)
        return normalize(hstack([word, char]), copy=False)


def exact_similarity(query: str, segments: list[dict], provider: EmbeddingProvider | None = None) -> list[tuple[str, float]]:
    if not query.strip() or not segments:
        return []
    provider = provider or HashingEmbeddingProvider()
    matrix = provider.encode([query, *[segment["text"] for segment in segments]])
    scores = (matrix[1:] @ matrix[0].T).toarray().ravel()
    return sorted(
        [(segment["id"], float(score)) for segment, score in zip(segments, scores, strict=True)],
        key=lambda item: item[1],
        reverse=True,
    )
