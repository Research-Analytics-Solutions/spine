"""Embedders — pluggable text->vector backends implementing core ``Embedder``.

``HashEmbedder`` is dependency-free and offline (a good default and test double);
``OpenAIEmbedder`` calls a real embedding model. Any object with
``async def embed(text) -> list[float]`` works, so users can bring their own
(sentence-transformers, Cohere, local models, …).
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

_WORD = re.compile(r"\w+")


def _features(text: str) -> list[str]:
    text = text.lower()
    words = _WORD.findall(text)
    trigrams = [text[i : i + 3] for i in range(max(0, len(text) - 2))]
    return words + trigrams


class HashEmbedder:
    """Deterministic, offline hashed bag-of-features embedding (L2-normalized).

    Good for tests and small/offline deployments; not as expressive as a learned
    model. Swap for ``OpenAIEmbedder`` (or your own) in production.
    """

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    async def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for feature in _features(text):
            digest = hashlib.md5(feature.encode()).hexdigest()  # noqa: S324 - non-crypto
            vec[int(digest, 16) % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm else vec


class OpenAIEmbedder:
    """Embeds via the OpenAI embeddings API (lazy client; injectable for tests)."""

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        *,
        client: Any = None,
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self._client = client
        self._api_key = api_key

    def _ensure_client(self) -> Any:
        if self._client is None:
            import openai

            self._client = openai.AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def embed(self, text: str) -> list[float]:
        response = await self._ensure_client().embeddings.create(model=self.model, input=text)
        return list(response.data[0].embedding)
