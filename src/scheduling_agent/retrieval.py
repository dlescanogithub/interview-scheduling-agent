"""Local BM25 over the synthetic FAQ. No embeddings and no network.

Labels for the query set were written together with the documents. Hit@k on
that set measures this retriever, not a general search system.
"""

from __future__ import annotations

import math
import random
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = {
    "a",
    "al",
    "algo",
    "como",
    "con",
    "de",
    "del",
    "el",
    "en",
    "es",
    "esa",
    "ese",
    "esta",
    "este",
    "for",
    "how",
    "la",
    "las",
    "lo",
    "los",
    "me",
    "mi",
    "my",
    "of",
    "para",
    "por",
    "que",
    "se",
    "si",
    "the",
    "to",
    "un",
    "una",
    "what",
    "y",
}


def fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in normalized if not unicodedata.combining(char))
    return stripped.casefold()


def tokenize(text: str) -> list[str]:
    return [
        token
        for token in _TOKEN.findall(fold(text))
        if token not in _STOP and len(token) > 1
    ]


@dataclass(frozen=True)
class Document:
    id: str
    lang: str
    title: str
    body: str
    trust: str = "normal"

    @property
    def text(self) -> str:
        return f"{self.title}\n{self.body}"


@dataclass(frozen=True)
class Hit:
    doc_id: str
    title: str
    score: float
    excerpt: str
    trust: str


def load_documents(directory: Path) -> list[Document]:
    documents: list[Document] = []
    for path in sorted(directory.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        header, _, body = raw.partition("\n\n")
        meta: dict[str, str] = {}
        for line in header.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
        documents.append(
            Document(
                id=meta["id"],
                lang=meta.get("lang", "es"),
                title=meta.get("title", meta["id"]),
                body=body.strip(),
                trust=meta.get("trust", "normal"),
            )
        )
    return documents


class BM25:
    """Okapi BM25 with the usual k1=1.5 and b=0.75."""

    def __init__(
        self, documents: list[Document], *, k1: float = 1.5, b: float = 0.75
    ) -> None:
        self.documents = documents
        self.k1 = k1
        self.b = b
        self._tokens = [tokenize(doc.text) for doc in documents]
        self._lengths = [len(tokens) for tokens in self._tokens]
        self._avgdl = (
            (sum(self._lengths) / len(self._lengths)) if self._lengths else 1.0
        )
        self._df: dict[str, int] = {}
        self._tf: list[dict[str, int]] = []
        for tokens in self._tokens:
            counts: dict[str, int] = {}
            for token in tokens:
                counts[token] = counts.get(token, 0) + 1
            self._tf.append(counts)
            for token in counts:
                self._df[token] = self._df.get(token, 0) + 1
        self._n = len(documents)

    def score(self, query: str) -> list[tuple[Document, float]]:
        tokens = tokenize(query)
        scored: list[tuple[Document, float]] = []
        for index, document in enumerate(self.documents):
            total = 0.0
            dl = self._lengths[index]
            for token in tokens:
                tf = self._tf[index].get(token, 0)
                if tf == 0:
                    continue
                df = self._df.get(token, 0)
                idf = math.log(1.0 + (self._n - df + 0.5) / (df + 0.5))
                denom = tf + self.k1 * (1.0 - self.b + self.b * dl / self._avgdl)
                total += idf * (tf * (self.k1 + 1.0)) / denom
            scored.append((document, total))
        scored.sort(key=lambda item: (-item[1], item[0].id))
        return scored

    def search(self, query: str, k: int = 3) -> list[Hit]:
        hits: list[Hit] = []
        for document, value in self.score(query)[:k]:
            if value <= 0:
                continue
            excerpt = document.body.replace("\n", " ").strip()
            if len(excerpt) > 240:
                excerpt = excerpt[:237] + "..."
            hits.append(
                Hit(
                    doc_id=document.id,
                    title=document.title,
                    score=round(value, 4),
                    excerpt=excerpt,
                    trust=document.trust,
                )
            )
        return hits


def hit_at_k(ranked_ids: list[str], relevant: set[str], k: int) -> bool:
    return any(doc_id in relevant for doc_id in ranked_ids[:k])


def bootstrap_mean(
    flags: list[bool], *, seed: int = 0, reps: int = 1000
) -> tuple[float, float, float]:
    """Point estimate and a 95% bootstrap interval over this fixed item list.

    Resampling the same labelled queries does not create a new population.
    It only shows how much the rate moves if these items are reweighted.
    """
    if not flags:
        return 0.0, 0.0, 0.0
    rng = random.Random(seed)
    point = sum(flags) / len(flags)
    samples: list[float] = []
    for _ in range(reps):
        draw = [flags[rng.randrange(len(flags))] for _ in range(len(flags))]
        samples.append(sum(draw) / len(draw))
    samples.sort()
    low_index = int(0.025 * reps)
    high_index = max(low_index, int(0.975 * reps) - 1)
    return point, samples[low_index], samples[high_index]
