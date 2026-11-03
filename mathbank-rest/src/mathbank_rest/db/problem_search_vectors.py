"""Problem search over S3 Vectors + mb-content (requirement 71 WP2; requirement 70 C6 "problem search is semantic with a
canonical_code key lookup first").

Used only when ``vector_store.uses_s3_vectors()``; the legacy pgvector/FTS SQL in ``vector_search`` / ``hybrid_search`` is
untouched otherwise. No Postgres: candidates come from the ``problem`` index, every hit is re-checked against its ``PROBLEM#``
item in ``mb-content`` (published, and the hit's vector is one of the item's *current* vectors) and results are hydrated from
that item (the statement is fetched from S3 only for the rows actually returned).

Search is **vector-only** (+ graph in ``hybrid_search``): lexical/full-text ranking lived in Postgres and is removed with it
(requirement 70 section 2d), so ``lexical_rank`` is always ``None`` here.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

from mathbank_rest import content_lookup, embeddings
from mathbank_rest.models.ddb.content import ContentProblem
from mathbank_rest.vector_catalog import Family
from mathbank_rest.vector_store import MAX_TOP_K, get_vector_store, vf

CODE_RE = re.compile(r"^[A-Za-z0-9]+(?:[_.\-][A-Za-z0-9]+){1,}$")      # IMO_2020_P1, PRASOLOV_PGV1_CH01_P005 - never a sentence


class ProblemFilters(BaseModel):
    model_config = ConfigDict(frozen=True)

    competition: str | None = None
    year_min: int | None = None
    year_max: int | None = None

    def vector_filter(self) -> dict | None:
        parts = [vf.eq("competition", self.competition) if self.competition else None,
                 vf.gte("year", self.year_min) if self.year_min is not None else None,
                 vf.lte("year", self.year_max) if self.year_max is not None else None]
        return vf.and_(*parts)

    def accepts(self, p: ContentProblem) -> bool:
        """The same filters applied to the authoritative item (the vector metadata is only the pre-filter)."""
        if self.competition and p.competition.external_code != self.competition:
            return False
        if self.year_min is not None and (p.year is None or p.year < self.year_min):
            return False
        return not (self.year_max is not None and (p.year is None or p.year > self.year_max))


class ProblemCandidate(BaseModel):
    canonical_code: str
    similarity: float
    semantic_rank: int
    exact_code_match: bool = False


class ProblemRow(BaseModel):
    """One search result row; the field names are the legacy SQL result's (``rrf_score`` is the vector similarity here)."""

    canonical_code: str
    problem_number: int
    statement_text: str | None
    source_url: str | None
    competition: str
    competition_code: str
    year: int | None
    paper_code: str
    rrf_score: float
    semantic_rank: int | None
    lexical_rank: int | None = None


def looks_like_code(query: str) -> bool:
    q = query.strip()
    return " " not in q and bool(CODE_RE.match(q)) and any(c.isdigit() for c in q)


def semantic_candidates(query: str, filters: ProblemFilters, *, candidates: int = MAX_TOP_K,
                        query_vector: list[float] | None = None) -> tuple[list[ProblemCandidate], dict[str, ContentProblem]]:
    """Ranked, eligible, de-duplicated problems for a query: an exact canonical_code match first, then the nearest vectors.

    Returns the candidates and the hydrated ``mb-content`` items they came from (so callers do not re-read them)."""
    candidates = max(1, min(candidates, MAX_TOP_K))
    ranked: list[tuple[str, float, bool]] = []
    items: dict[str, ContentProblem] = {}
    if looks_like_code(query):
        for variant in dict.fromkeys([query.strip(), query.strip().upper()]):
            found = content_lookup.problems_by_code([variant]).get(variant)
            if found is not None and content_lookup.is_published(found) and filters.accepts(found):
                ranked.append((found.canonical_code, 1.0, True))
                items[found.canonical_code] = found
                break
    vector = query_vector if query_vector is not None else embeddings.embed_text(query)
    hits = get_vector_store().query(Family.PROBLEM, vector, top_k=candidates, filter=filters.vector_filter())
    codes = [h.metadata.get("canonical_code") for h in hits if h.metadata.get("canonical_code")]
    items.update(content_lookup.problems_by_code(c for c in codes if c not in items))
    seen = {code for code, _, _ in ranked}
    for h in hits:                                              # hits arrive best-first; keep each problem's best chunk
        code = h.metadata.get("canonical_code")
        if not code or code in seen:
            continue
        item = items.get(code)
        if item is None or not content_lookup.hit_is_current(item, h.key) or not filters.accepts(item):
            continue                                            # withdrawn, re-embedded (stale vector) or filtered out
        seen.add(code)
        ranked.append((code, h.similarity, False))
    return ([ProblemCandidate(canonical_code=c, similarity=s, semantic_rank=i, exact_code_match=e)
             for i, (c, s, e) in enumerate(ranked, 1)], items)


def hydrate(codes: list[str], items: dict[str, ContentProblem], scores: dict[str, dict], *, with_statement: bool = True) -> list[ProblemRow]:
    """Result rows for ``codes`` (in order) from the mb-content items; ``scores[code]`` supplies rrf_score/semantic_rank."""
    missing = [c for c in codes if c not in items]
    if missing:
        items = {**items, **content_lookup.problems_by_code(missing)}
    rows = []
    for code in codes:
        p = items.get(code)
        if p is None or not content_lookup.is_published(p):
            continue
        s = scores.get(code, {})
        rows.append(ProblemRow(
            canonical_code=p.canonical_code, problem_number=p.problem_number,
            statement_text=p.resolve("statement_text") if with_statement else None, source_url=p.source_url,
            competition=p.competition.name, competition_code=p.competition.external_code, year=p.year, paper_code=p.paper_code,
            rrf_score=float(s.get("rrf_score", 0.0)), semantic_rank=s.get("semantic_rank"), lexical_rank=s.get("lexical_rank")))
    return rows


def order_rows(rows: list[ProblemRow], order_by: str) -> list[ProblemRow]:
    rows = sorted(rows, key=lambda r: (-r.rrf_score, r.canonical_code))
    if order_by == "year_desc":
        rows.sort(key=lambda r: -(r.year or 0))
    elif order_by == "year_asc":
        rows.sort(key=lambda r: r.year if r.year is not None else 9999)
    return rows


def search_problems(query: str, *, competition: str | None = None, year_min: int | None = None, year_max: int | None = None,
                    semantic: bool = True, order_by: str = "relevance", limit: int = 25) -> list[dict]:
    """Drop-in for ``vector_search.search_problems`` rows when S3 Vectors is on (semantic only; ``lexical`` is not applied)."""
    if not semantic:
        return []
    filters = ProblemFilters(competition=competition, year_min=year_min, year_max=year_max)
    cands, items = semantic_candidates(query, filters, candidates=min(max(limit * 4, 40), MAX_TOP_K))
    scores = {c.canonical_code: {"rrf_score": c.similarity, "semantic_rank": c.semantic_rank} for c in cands}
    top = order_rows(hydrate([c.canonical_code for c in cands], items, scores, with_statement=False), order_by)[:limit]
    return [r.model_dump() for r in hydrate([r.canonical_code for r in top], items, scores)]
