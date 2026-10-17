"""Local BM25 over the synthetic FAQ. Labels were written with the corpus."""

from __future__ import annotations

from pathlib import Path

import yaml
from tests.support import FAQ, ROOT

from scheduling_agent.retrieval import BM25, bootstrap_mean, hit_at_k, load_documents


def test_labelled_queries_hit_and_nonsense_stays_below_threshold() -> None:
    documents = load_documents(FAQ)
    assert len(documents) == 25
    poison = next(doc for doc in documents if doc.id == "faq-poison-injection")
    assert "ignore the rules" in poison.body
    assert poison.trust == "untrusted"
    engine = BM25(documents)
    query_path = ROOT / "data" / "faq" / "queries.yaml"
    rows = yaml.safe_load(query_path.read_text(encoding="utf-8"))
    assert len(rows) == 30
    flags_1: list[bool] = []
    flags_3: list[bool] = []
    for row in rows:
        ranked = [doc.id for doc, _score in engine.score(row["text"])]
        relevant = set(row["relevant"])
        flags_1.append(hit_at_k(ranked, relevant, 1))
        flags_3.append(hit_at_k(ranked, relevant, 3))
    assert sum(flags_1) == 30
    assert sum(flags_3) == 30
    point, low, high = bootstrap_mean(flags_1, seed=0, reps=1000)
    assert point == 1.0
    assert low == 1.0 and high == 1.0
    nonsense = engine.search("zzzzqqqq xylophone quarry", k=3)
    assert nonsense == [] or nonsense[0].score < 1.0


def test_empty_index_and_bootstrap_edges() -> None:
    assert BM25([]).search("hola") == []
    assert bootstrap_mean([]) == (0.0, 0.0, 0.0)
    point, low, high = bootstrap_mean([True, False], seed=1, reps=50)
    assert 0.0 <= low <= point <= high <= 1.0
    assert hit_at_k(["faq-a"], {"faq-b"}, 1) is False


def test_load_documents_reads_frontmatter(tmp_path: Path) -> None:
    (tmp_path / "note.md").write_text(
        "id: faq-note\nlang: en\n\nBody about subtitulos and husos.\n",
        encoding="utf-8",
    )
    docs = load_documents(tmp_path)
    assert docs[0].id == "faq-note"
    assert docs[0].lang == "en"
    assert "subtitulos" in docs[0].text
