"""Content store, catalog area (requirement 71 WP4; requirement 70 C6 access patterns A1-A13).

``CatalogPostgres`` delegates to today's SQL modules, looking each function up at call time so existing tests that
monkeypatch ``db.queries`` keep working and behaviour is unchanged. ``CatalogDynamoDB`` serves the same dict shapes from
``mb-content`` (typed models only, Query/GetItem/BatchGetItem only, never a scan, never PostgreSQL).

Known, deliberate differences of the DynamoDB backend (the projection is the contract, see doc 70 C6 sections 1a/3):

* only ``ACTIVE`` problems are projected, so withdrawn problems are absent (the SQL had no status filter);
* tag roles are normalised upper-case (KNP-S02); technique rows are one per (problem, technique);
* concept relations exclude REJECTED rows; coverage counts come from the publisher-maintained STATS item;
* ``official_answer`` / ``solutions`` are served only while ``CONTENT_PUBLIC_ANSWERS`` is true (doc 70 6c), else ``None`` / ``[]``.
"""
from __future__ import annotations

import hashlib
import heapq
import itertools
from collections.abc import Iterable, Iterator
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from mathbank_rest.config import settings
from mathbank_rest.models.ddb.content import (
    ContentCatalogptr,
    ContentCompetition,
    ContentConcept,
    ContentImage,
    ContentProblem,
    ContentProblemKey,
    ContentPtag,
    ContentSolution,
    ContentStats,
    ContentTechnique,
)
from mathbank_rest.models.docs.content import CatalogConcept, CatalogTechnique
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores.content.snapshots import snapshots
from mathbank_rest.stores.errors import StoreUnavailable

PAGE = 200
CATALOG_COMPETITIONS = "CATALOG#COMPETITION"
_MAX_YEAR = 9999


# ------------------------------------------------------------------------------------------------ postgres

def _queries():
    from mathbank_rest.db import queries

    return queries


class CatalogPostgres:
    """Postgres backend: delegates to the existing SQL modules (behaviour unchanged)."""

    def list_competitions(self) -> list[dict]:
        return _queries().list_competitions()

    def list_problems(self, *, competition: str | None = None, year_min: int | None = None, year_max: int | None = None,
                      concept: str | None = None, technique: str | None = None, limit: int = 25, offset: int = 0) -> list[dict]:
        return _queries().list_problems(competition=competition, year_min=year_min, year_max=year_max, concept=concept,
                                        technique=technique, limit=limit, offset=offset)

    def get_problem_by_code(self, code: str) -> dict | None:
        return _queries().get_problem_by_code(code)

    def get_problem_by_id(self, problem_id: UUID | str) -> dict | None:
        from sqlalchemy import text

        from mathbank_rest.db.postgres import engine

        with engine.connect() as conn:
            code = conn.execute(text("SELECT canonical_code FROM core.problem WHERE problem_id = :id"),
                                {"id": str(problem_id)}).scalar()
        return None if code is None else _queries().get_problem_by_code(code)

    def get_problems_by_codes(self, codes: Iterable[str]) -> list[dict]:
        """Learner-safe problem dicts (no ``official_answer``/``solutions``) in the order of ``codes``; unknown codes are skipped."""
        out = []
        for code in dict.fromkeys(codes):
            row = _queries().get_problem_by_code(code)
            if row is not None:
                out.append({k: v for k, v in row.items() if k not in ("official_answer", "solutions")})
        return out

    def list_concepts(self, *, domain: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
        return _queries().list_concepts(domain=domain, limit=limit, offset=offset)

    def get_concept_problems(self, slug: str, *, limit: int = 25, offset: int = 0) -> list[dict]:
        return _queries().get_concept_problems(slug, limit=limit, offset=offset)

    def get_concept_neighbors(self, slug: str) -> list[dict]:
        return _queries().get_concept_neighbors(slug)

    def list_techniques(self, *, q: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
        return _queries().list_techniques(q=q, limit=limit, offset=offset)

    def get_technique_problems(self, slug: str, *, limit: int = 25, offset: int = 0) -> list[dict]:
        return _queries().get_technique_problems(slug, limit=limit, offset=offset)

    def get_corpus_coverage(self) -> list[dict]:
        return _queries().corpus_coverage()

    def get_problem_tags(self, *, problem_id: UUID | str | None = None, code: str | None = None) -> dict:
        """``{"concept_ids": [...], "technique_ids": [...]}`` of the non-rejected tags, by problem id or canonical code."""
        from mathbank_rest.db import learner

        if problem_id is None:
            if code is None:
                raise ValueError("problem_id or code is required")
            problem_id = learner.get_problem_id_by_code(code)
            if problem_id is None:
                return {"concept_ids": [], "technique_ids": []}
        return learner.get_concepts_and_techniques_for_problem(problem_id)

    def list_problem_diagrams(self, code: str, *, engine: Any = None) -> list[dict]:
        """Student-safe statement diagrams of a problem. ``engine`` (Postgres only) lets a router pass its connection source."""
        from mathbank_rest.db import problem_images
        from mathbank_rest.db.postgres import engine as default_engine

        with (engine or default_engine).connect() as conn:
            return problem_images.list_images(conn, code)

    def get_student_image(self, image_id: UUID | str, *, engine: Any = None) -> dict | None:
        """``{"local_path": ...}`` for a student-visible image, ``None`` when missing or hidden."""
        from sqlalchemy import text

        from mathbank_rest.db.postgres import engine as default_engine
        from mathbank_rest.db.problem_images import STUDENT_IMAGE_FILTER

        with (engine or default_engine).connect() as conn:
            path = conn.execute(text(f"SELECT i.local_path FROM core.problem_image i "
                                     f"WHERE i.problem_image_id = :i AND {STUDENT_IMAGE_FILTER}"),
                                {"i": str(image_id)}).scalar()
        return {"local_path": path} if path else None


# ------------------------------------------------------------------------------------------------ dynamodb helpers

def _pk(code: str) -> str:
    return f"PROBLEM#{code}"


def _dicts(rows: Iterable[Any] | None) -> list[dict]:
    return [r.model_dump(mode="json", by_alias=True) if isinstance(r, BaseModel) else dict(r) for r in rows or []]


def _pages(model: Any, pk: str, **kw: Any) -> Iterator[Any]:
    """Every item of one key-condition query, page by page (lazy: a caller that stops early stops reading)."""
    token = None
    kw.setdefault("limit", PAGE)
    while True:
        page = typed.query(model, pk, next_token=token, **kw)
        yield from page.items
        token = page.next_token
        if token is None:
            return


def _window(items: Iterable[Any], limit: int, offset: int) -> list[Any]:
    return list(itertools.islice(items, offset, offset + limit)) if limit > 0 else []


def _page_size(limit: int, offset: int) -> int:
    return max(1, min(PAGE, limit + offset))


def _year_bounds(year_min: int | None, year_max: int | None) -> tuple[str, str] | None:
    """Sort-key range over ``<year:04d>...`` for the year filter; ``None`` = unbounded."""
    if year_min is None and year_max is None:
        return None
    lo = min(max(year_min, 0), _MAX_YEAR) if year_min is not None else 0
    hi = min(year_max, _MAX_YEAR) if year_max is not None else _MAX_YEAR
    return f"{lo:04d}", f"{hi:04d}#~"


def _empty_year_range(year_min: int | None, year_max: int | None) -> bool:
    return (year_min is not None and year_max is not None and year_min > year_max) or (year_max is not None and year_max < 0) \
        or (year_min is not None and year_min > _MAX_YEAR)


def _diagrams(code: str, item: ContentProblem) -> list[dict]:
    out = []
    for image in sorted(item.images, key=lambda i: (i.ordinal, str(i.problem_image_id))):
        iid, version = str(image.problem_image_id), image.version_
        alt = f"{code} - source problem diagram {image.ordinal}"
        out.append({"problem_image_id": iid, "ordinal": image.ordinal, "source": image.source, "version": version,
                    "url": f"/v1/problem-images/{iid}?v={version}", "alt": alt,
                    "markdown": f"![{alt}](/api/rest/solve/images/{iid}?v={version})"})
    return out


def _tag_row(tag: ContentPtag) -> dict:
    return {"canonical_code": tag.problem_code, "problem_number": tag.problem_number, "competition": tag.competition_name,
            "year": tag.year, "role": tag.role, "confidence": tag.confidence}


# Process-wide cache of the validated catalogue snapshots: an object key is immutable (it carries the sha256), so a
# pointer that still names the same key means the parsed document and its indexes are still current.
_CATALOGUES: dict[str, tuple[str, Any, dict]] = {}


def _catalogue(kind: str, model: Any) -> tuple[Any, dict]:
    ptr = typed.get(ContentCatalogptr, f"CATALOG#{kind.upper()}", "SNAPSHOT", consistent=False)
    if ptr is None:
        raise StoreUnavailable(f"catalogue snapshot {kind!r} is not published", kind=kind)
    hit = _CATALOGUES.get(kind)
    if hit is None or hit[0] != ptr.s3_key:
        doc = snapshots.get_model(ptr.s3_key, model)
        index = {"slug": {i.slug: i for i in doc.items}, "id": {str(getattr(i, f"{kind}_id")): i for i in doc.items}}
        hit = _CATALOGUES[kind] = (ptr.s3_key, doc, index)
    return hit[1], hit[2]


def _closure(slug: str) -> list[str]:
    """Concept ids of ``slug`` and everything below it through HAS_SUBCONCEPT (breadth first, cycle safe)."""
    _, index = _catalogue("concept", CatalogConcept)
    start = index["slug"].get(slug)
    if start is None:
        return []
    seen, queue = [str(start.concept_id)], [start]
    while queue:
        for rel in queue.pop(0).relations_out:
            child = index["id"].get(rel.get("concept_id", ""))
            if rel.get("relation_type") == "HAS_SUBCONCEPT" and child is not None and str(child.concept_id) not in seen:
                seen.append(str(child.concept_id))
                queue.append(child)
    return seen


def _contains(needle: str, *values: Any) -> bool:
    n = needle.casefold()
    return any(isinstance(v, str) and n in v.casefold() for v in values)


# ------------------------------------------------------------------------------------------------ dynamodb

class CatalogDynamoDB:
    """DynamoDB backend over mb-content (typed models, stores.typed). Eventually consistent reads throughout (doc 70 C6 A1-A13)."""

    # -- A1 ---------------------------------------------------------------------------------------------------------

    @staticmethod
    def _competitions() -> list[ContentCompetition]:
        items = list(_pages(ContentCompetition, CATALOG_COMPETITIONS, consistent=False))
        return sorted(items, key=lambda c: c.name)

    def list_competitions(self) -> list[dict]:
        return [{"competition_id": str(c.competition_id), "external_code": c.external_code, "name": c.name, "level": c.level}
                for c in self._competitions()]

    # -- problem assembly -------------------------------------------------------------------------------------------

    @staticmethod
    def _keys(codes: list[str]) -> dict[str, ContentProblemKey]:
        if not codes or not settings.content_public_answers:
            return {}
        keys = typed.batch_get(ContentProblemKey, [(_pk(c), "KEY#ANSWER") for c in codes], consistent=False)
        return {k.PK.removeprefix("PROBLEM#"): k for k in keys}

    @staticmethod
    def _answer(key: ContentProblemKey | None) -> str | None:
        return None if key is None else key.resolve("official_answer")

    def _summary(self, item: ContentProblem, key: ContentProblemKey | None = None) -> dict:
        """The Postgres ``get_problem_by_code`` dict without ``solutions``."""
        code = item.canonical_code
        return {
            "canonical_code": code, "problem_number": item.problem_number, "statement_text": item.resolve("statement_text"),
            "official_answer": self._answer(key), "source_url": item.source_url, "difficulty_band": item.difficulty_band,
            "classification_status": item.classification_status, "paper_code": item.paper_code, "year": item.year,
            "competition": item.competition.name,
            "concepts": [{k: c[k] for k in ("slug", "name", "role", "confidence")} for c in _dicts(item.resolve("concepts"))],
            "techniques": [{k: t[k] for k in ("slug", "name", "role", "confidence")} for t in _dicts(item.resolve("techniques"))],
            "diagrams": _diagrams(code, item),
        }

    def _detail(self, item: ContentProblem) -> dict:
        code = item.canonical_code
        key, solutions = None, []
        if settings.content_public_answers:
            for row in _pages("content", _pk(code), models=[ContentProblemKey, ContentSolution], sk_begins="KEY#", consistent=False):
                if isinstance(row, ContentProblemKey):
                    key = row
                else:
                    solutions.append({"solution_kind": row.solution_kind, "revision": row.revision,
                                      "body_markdown": row.resolve("body_markdown"), "verification_status": row.verification_status})
        base = self._summary(item, key)
        diagrams = base.pop("diagrams")
        return {**base, "solutions": solutions, "diagrams": diagrams}

    @staticmethod
    def _visible(item: ContentProblem | None) -> bool:
        return item is not None and item.visibility == "ACTIVE"

    # -- A2 / A3 / A4 -----------------------------------------------------------------------------------------------

    def get_problem_by_code(self, code: str) -> dict | None:
        item = typed.get(ContentProblem, _pk(code), "META", consistent=False)
        return self._detail(item) if self._visible(item) else None

    def get_problem_by_id(self, problem_id: UUID | str) -> dict | None:
        page = typed.query(ContentProblem, f"PID#{problem_id}", index="GSI1", limit=1)
        item = page.items[0] if page.items else None
        return self._detail(item) if self._visible(item) else None

    def get_problems_by_codes(self, codes: Iterable[str]) -> list[dict]:
        """Learner-safe problem dicts (no ``official_answer``/``solutions``) in the order of ``codes``; unknown codes are skipped."""
        wanted = list(dict.fromkeys(codes))
        found = {i.canonical_code: i for i in typed.batch_get(ContentProblem, [(_pk(c), "META") for c in wanted], consistent=False)}
        out = []
        for code in wanted:
            if self._visible(found.get(code)):
                row = self._summary(found[code])
                row.pop("official_answer")
                out.append(row)
        return out

    def list_problem_diagrams(self, code: str, *, engine: Any = None) -> list[dict]:
        item = typed.get(ContentProblem, _pk(code), "META", consistent=False)
        return _diagrams(code, item) if self._visible(item) else []

    # -- A5 ---------------------------------------------------------------------------------------------------------

    def _list_row(self, item: ContentProblem, key: ContentProblemKey | None) -> dict:
        return {"canonical_code": item.canonical_code, "problem_number": item.problem_number,
                "official_answer": self._answer(key), "source_url": item.source_url, "paper_code": item.paper_code,
                "year": item.year, "competition": item.competition.name}

    def _rows(self, items: list[ContentProblem]) -> list[dict]:
        keys = self._keys([i.canonical_code for i in items])
        return [self._list_row(i, keys.get(i.canonical_code)) for i in items]

    def _by_competition(self, competition: str | None, year_min: int | None, year_max: int | None, size: int) -> Iterator[ContentProblem]:
        """Problems ordered by competition name, year, paper code, problem number (GSI2 ``PLIST#<code>`` ranges)."""
        kw: dict[str, Any] = {"index": "GSI2", "limit": size}
        bounds = _year_bounds(year_min, year_max)
        if bounds is not None:
            kw["sk_between"] = bounds
        for comp in self._competitions():
            if competition is not None and comp.external_code != competition:
                continue
            for item in _pages(ContentProblem, f"PLIST#{comp.external_code}", **kw):
                if self._visible(item):
                    yield item

    @staticmethod
    def _tagged(pk: str, year_min: int | None, year_max: int | None) -> dict[str, ContentPtag]:
        kw: dict[str, Any] = {"index": "GSI1"}
        bounds = _year_bounds(year_min, year_max)
        if bounds is not None:
            kw["sk_between"] = bounds
        return {t.problem_code: t for t in _pages(ContentPtag, pk, **kw) if t.review_status != "REJECTED"}

    def _by_tags(self, competition: str | None, year_min: int | None, year_max: int | None, concept: str | None,
                 technique: str | None, limit: int, offset: int) -> list[ContentProblem]:
        """Concept/technique filters (exact slug, as the SQL): PTAG sets from GSI1, intersected, ordered like the SQL."""
        sets: list[dict[str, ContentPtag]] = []
        for kind, model, slug in (("CONCEPT", ContentConcept, concept), ("TECHNIQUE", ContentTechnique, technique)):
            if not slug:
                continue
            entity = self._by_slug(kind, model, slug)
            if entity is None:
                return []
            sets.append(self._tagged(f"{kind}#{getattr(entity, kind.lower() + '_id')}", year_min, year_max))
        tags = {c: t for c, t in sets[0].items() if all(c in s for s in sets[1:])}
        if competition:
            comp = next((c for c in self._competitions() if c.external_code == competition), None)
            if comp is None:
                return []
            tags = {c: t for c, t in tags.items() if t.competition_name == comp.name}
        groups: dict[tuple, list[str]] = {}
        for code, tag in tags.items():
            groups.setdefault((tag.competition_name, tag.year is None, tag.year or 0), []).append(code)
        out: list[ContentProblem] = []
        skip, want = offset, limit
        for gkey in sorted(groups):
            codes = groups[gkey]
            if skip >= len(codes):
                skip -= len(codes)
                continue
            found = typed.batch_get(ContentProblem, [(_pk(c), "META") for c in codes], consistent=False)
            ordered = sorted((i for i in found if self._visible(i)), key=lambda i: (i.paper_code, i.problem_number, i.canonical_code))
            take = ordered[skip:skip + want]
            skip = 0
            out += take
            want -= len(take)
            if want <= 0:
                break
        return out

    def list_problems(self, *, competition: str | None = None, year_min: int | None = None, year_max: int | None = None,
                      concept: str | None = None, technique: str | None = None, limit: int = 25, offset: int = 0) -> list[dict]:
        if limit <= 0 or _empty_year_range(year_min, year_max):
            return []
        if concept or technique:
            return self._rows(self._by_tags(competition, year_min, year_max, concept, technique, limit, offset))
        stream = self._by_competition(competition, year_min, year_max, _page_size(limit, offset))
        return self._rows(_window(stream, limit, offset))

    # -- A6 / A7 ----------------------------------------------------------------------------------------------------

    def get_concept_problems(self, slug: str, *, limit: int = 25, offset: int = 0) -> list[dict]:
        """Problems tagged with the concept or any HAS_SUBCONCEPT descendant, one row per problem (PRIMARY, then highest
        confidence wins), ordered by year, problem number, code: a k-way merge of the per-concept GSI1 streams."""
        ids = _closure(slug)
        if not ids or limit <= 0:
            return []
        size = _page_size(limit, offset)
        streams = [_pages(ContentPtag, f"CONCEPT#{cid}", index="GSI1", limit=size) for cid in ids]
        merged = heapq.merge(*streams, key=lambda t: t.GSI1SK)
        best: Iterator[ContentPtag] = (
            min(group, key=lambda t: (t.role.upper() != "PRIMARY", -t.confidence))
            for _, group in itertools.groupby((t for t in merged if t.review_status != "REJECTED"), key=lambda t: t.GSI1SK))
        return [{**_tag_row(t), "matched_concept_slug": t.slug} for t in _window(best, limit, offset)]

    def get_technique_problems(self, slug: str, *, limit: int = 25, offset: int = 0) -> list[dict]:
        tech = self._by_slug("TECHNIQUE", ContentTechnique, slug)
        if tech is None or limit <= 0:
            return []
        tags = (t for t in _pages(ContentPtag, f"TECHNIQUE#{tech.technique_id}", index="GSI1", limit=_page_size(limit, offset))
                if t.review_status != "REJECTED")
        return [_tag_row(t) for t in _window(tags, limit, offset)]

    # -- A8 / A9 / A10 ----------------------------------------------------------------------------------------------

    @staticmethod
    def _by_slug(kind: str, model: Any, slug: str) -> Any:
        page = typed.query(model, f"SLUG#{kind}#{slug}", index="GSI1", limit=1)
        return page.items[0] if page.items else None

    def list_concepts(self, *, domain: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
        doc, _ = _catalogue("concept", CatalogConcept)
        rows = [c for c in doc.items if not domain or _contains(domain, c.name, *c.aliases)]
        rows.sort(key=lambda c: (c.level is None, c.level or 0, c.name.casefold(), c.name, c.slug))
        return [{"slug": c.slug, "name": c.name, "level": c.level, "description": c.description} for c in _window(rows, limit, offset)]

    def list_techniques(self, *, q: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
        doc, _ = _catalogue("technique", CatalogTechnique)
        rows = [t for t in doc.items if not q or _contains(q, t.name, t.slug, *t.aliases)]
        rows.sort(key=lambda t: (t.name.casefold(), t.name, t.slug))
        return [{"slug": t.slug, "name": t.name, "description": t.description} for t in _window(rows, limit, offset)]

    def get_concept_neighbors(self, slug: str) -> list[dict]:
        concept = self._by_slug("CONCEPT", ContentConcept, slug)
        if concept is None:
            return []
        out = []
        for direction, attr in (("outgoing", "relations_out"), ("incoming", "relations_in")):
            for rel in _dicts(concept.resolve(attr)):
                out.append({"slug": rel["slug"], "name": rel["name"], "relation_type": rel["relation_type"],
                            "strength": rel["strength"], "direction": direction})
        return out

    # -- A11 / A12 / A13 --------------------------------------------------------------------------------------------

    def get_problem_tags(self, *, problem_id: UUID | str | None = None, code: str | None = None) -> dict:
        """``{"concept_ids": [...], "technique_ids": [...]}`` of the non-rejected tags (``Query PROBLEM#code, TAG#``)."""
        if code is None:
            if problem_id is None:
                raise ValueError("problem_id or code is required")
            page = typed.query(ContentProblem, f"PID#{problem_id}", index="GSI1", limit=1)
            if not page.items:
                return {"concept_ids": [], "technique_ids": []}
            code = page.items[0].canonical_code
        concepts: dict[UUID, None] = {}
        techniques: dict[UUID, None] = {}
        for tag in _pages(ContentPtag, _pk(code), sk_begins="TAG#", consistent=False):
            if tag.review_status == "REJECTED":
                continue
            _, kind, entity = tag.SK.split("#")[:3]
            if kind == "CONCEPT":
                concepts[UUID(entity)] = None
            elif kind == "TECHEV":
                techniques[UUID(entity)] = None
        return {"concept_ids": list(concepts), "technique_ids": list(techniques)}

    def get_corpus_coverage(self) -> list[dict]:
        item = typed.get(ContentStats, "STATS#CORPUS", "COVERAGE", consistent=False)
        if item is None:
            return []
        return [{k: r[k] for k in ("competition", "papers", "problems", "problems_with_concept", "problems_with_technique")}
                for r in _dicts(item.resolve("rows"))]

    def get_student_image(self, image_id: UUID | str, *, engine: Any = None) -> dict | None:
        """``{"data": bytes, "media_type": mime}`` of a student-audience image, ``None`` when missing or not student-visible."""
        item = typed.get(ContentImage, f"IMAGE#{image_id}", "META", consistent=False)
        if item is None or item.audience != "STUDENT":
            return None
        try:
            body = ddb.client("s3").get_object(Bucket=ddb.content_bucket(), Key=item.s3_key)["Body"].read()
        except Exception as exc:  # any storage failure is "published image storage unavailable", never a 404
            raise StoreUnavailable("published image storage is unavailable", image_id=str(image_id)) from exc
        if hashlib.sha256(body).hexdigest() != item.sha256:
            raise StoreUnavailable("published image failed its checksum", image_id=str(image_id))
        return {"data": body, "media_type": item.mime}
