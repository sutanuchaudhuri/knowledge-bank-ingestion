"""WP2 step / learning-item / taxonomy search on S3 Vectors + mb-content: filter mapping, hydration shape, eligibility re-check,
dedupe, exact-vs-ANN, similar_steps_for_step without an embedding call, the concept-search route, and the legacy SQL path
untouched when the flag is off. MemoryVectorStore + moto, no AWS, no Postgres."""
from __future__ import annotations

import datetime as dt
import random
import uuid

import pytest

from mathbank_rest import embeddings, rate_limit
from mathbank_rest.config import settings
from mathbank_rest.db import step_search
from mathbank_rest.db import step_search_vectors as ssv
from mathbank_rest.models.ddb.content import ContentFacet, ContentLi, ContentStep, ContentTaxnode
from mathbank_rest.stores import typed
from mathbank_rest.vector_catalog import (
    DIMENSIONS,
    Family,
    LearningItemMeta,
    StepMeta,
    TaxonomySearchMeta,
)
from mathbank_rest.vector_store import MemoryVectorStore, VectorItem, set_vector_store_for_tests, vf

NOW = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
STEP_KEYS = {"solution_step_id", "problem_id", "solution_id", "solution_part_id", "global_step_index", "step_type", "tutor_role",
             "hint_level", "is_checkpoint", "skill_node_id", "skill_name", "subconcept_node_id", "concept_node_id", "problem_code",
             "rrf_score", "semantic_rank", "lexical_rank"}
ITEM_KEYS = {"learning_item_id", "source_problem_id", "learning_item_type", "transformation_type", "target_skill_node_id",
             "target_subconcept_node_id", "difficulty_direction", "question_text", "choices", "diagram_strategy",
             "rrf_score", "semantic_rank", "lexical_rank"}
TAXONOMY_KEYS = {"taxonomy_node_id", "node_type", "name", "parent_node_id", "parent_name", "chapter_number", "section_number", "slug",
                 "slug_kind", "problem_count", "example_problem_codes", "rrf_score", "semantic_rank", "lexical_rank"}


def vec(seed: int) -> list[float]:
    r = random.Random(seed)
    return [r.uniform(-1, 1) for _ in range(DIMENSIONS)]


class Spy(MemoryVectorStore):
    def __init__(self) -> None:
        super().__init__()
        self.queries = 0
        self.gets = 0

    def query(self, *a, **k):
        self.queries += 1
        return super().query(*a, **k)

    def get(self, *a, **k):
        self.gets += 1
        return super().get(*a, **k)


class NoPostgres:
    def connect(self):
        raise AssertionError("Postgres must not be used when S3 Vectors is on")


@pytest.fixture()
def world(ddb, monkeypatch):
    ddb.create_table(TableName="mb-content-ut", AttributeDefinitions=[{"AttributeName": a, "AttributeType": "S"} for a in ("PK", "SK")],
                     KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
                     BillingMode="PAY_PER_REQUEST")
    store = Spy()
    set_vector_store_for_tests(store)
    monkeypatch.setattr(settings, "vector_store", "s3vectors")
    monkeypatch.setattr(step_search, "engine", NoPostgres())
    embeddings.reset_for_tests()
    queries: list[str] = []
    seeds = {"inversion": 1, "tangent circles": 2, "parity": 3}
    monkeypatch.setattr(embeddings, "EMBEDDER", lambda t: (queries.append(t), vec(seeds.get(t, 99)))[1])
    yield store, queries
    set_vector_store_for_tests(None)
    embeddings.reset_for_tests()


def facet(unit: str, dim: str, value: str, entity: str, keys: list[str], **extra) -> None:
    typed.put(ContentFacet.model_validate({
        "PK": f"FACET#{unit}#{dim}#{value}", "SK": entity, "type": "FACET", "content_sha256": "c" * 64, "dim": dim, "entity_id": entity,
        "src_rev": 1, "unit": unit, "value": value, "vector_keys": keys, **extra}))


def add_step(store, sid: str, seed: int, *, problem: str | None = None, skill: str = "SKILL.A", sub: str = "SUB.1", concept: str = "CON.1",
             step_type: str = "COMPUTE", role: str = "CORE_BRIDGE", hint: int = 1, checkpoint: bool = False,
             techniques: tuple[str, ...] = (), eligible: bool = True, stale: bool = False, facets: bool = True,
             text: str | None = None) -> str:
    problem = problem or str(uuid.uuid4())
    key = str(uuid.uuid4())
    typed.put(ContentStep.model_validate({
        "PK": f"STEP#{sid}", "SK": "META", "type": "STEP", "book_code": "BK", "concept_node_id": concept, "content_sha256": "c" * 64,
        "eligible": eligible, "global_step_index": 4, "hint_level": hint, "is_checkpoint": checkpoint, "problem_code": f"BK_{sid}",
        "problem_id": problem, "skill_name": f"name of {skill}", "skill_node_id": skill, "solution_id": str(uuid.uuid4()),
        "solution_part_id": "MAIN", "solution_step_id": sid, "src_rev": 1, "step_index_in_part": 2, "step_text": text or f"text of {sid}",
        "step_type": step_type, "subconcept_node_id": sub, "technique_node_ids": list(techniques), "tutor_role": role, "updated_at": NOW,
        "vector_state": {"index": Family.STEP.index_name, "keys": [str(uuid.uuid4())] if stale else [key],
                         "model": "text-embedding-3-small", "sha256": "s" * 64}}))
    store.put(Family.STEP, [VectorItem(key=key, vector=vec(seed), metadata=StepMeta(
        skill_node_id=skill, subconcept_node_id=sub, concept_node_id=concept, step_type=step_type, tutor_role=role, is_checkpoint=checkpoint,
        hint_level=hint, problem_id=problem, technique_node_ids=list(techniques) or None, book_code="BK", solution_step_id=sid,
        content_sha256="s" * 64, problem_code=f"BK_{sid}").to_metadata())])
    if facets:
        for dim, value in (("PROBLEM", problem), ("SKILL", skill), ("SUBCONCEPT", sub), ("CONCEPT", concept),
                           *(("TECHNIQUE", t) for t in techniques)):
            facet("STEP", dim, value, sid, [key])
    return key


def add_li(store, lid: str, seed: int, *, source: str | None = None, skill: str = "SKILL.A", sub: str = "SUB.1", form: str = "MCQ",
           ttype: str = "MCQ_FIRST_MOVE", direction: str = "LOWER", anchors: tuple[str, ...] = ("STEP-1",), eligible: bool = True,
           chunks: int = 1, stale: bool = False, facets: bool = True) -> list[str]:
    source = source or str(uuid.uuid4())
    keys = [str(uuid.uuid4()) for _ in range(chunks)]
    typed.put(ContentLi.model_validate({
        "PK": f"LI#{lid}", "SK": "META", "type": "LI", "anchor_step_ids": list(anchors), "approval_method": "automatic",
        "approved_at": NOW, "book_code": "BK", "content_sha256": "c" * 64, "diagram_strategy": "NONE_REQUIRED_BY_SOURCE",
        "difficulty_direction": direction, "eligible": eligible, "generation_mode": "RULE_SEEDED_V3", "learning_item_id": lid,
        "occurrence": 1, "requires_source_problem": False, "source_problem_code": "BK_P1", "source_problem_id": source,
        "source_transformation_id": "t", "src_rev": 1, "target_concept_node_id": "CON.1", "target_subconcept_node_id": sub,
        "transformation_type": ttype, "transformed_form": form, "updated_at": NOW, "question_text": f"question {lid}",
        "choices": ["a", "b"], "target_skill_node_id": skill,
        "vector_state": {"index": Family.LEARNING_ITEM.index_name, "keys": [str(uuid.uuid4())] if stale else keys,
                         "model": "text-embedding-3-small", "sha256": "s" * 64}}))
    store.put(Family.LEARNING_ITEM, [VectorItem(key=k, vector=vec(seed if i == 0 else seed + 700 + i), metadata=LearningItemMeta(
        kind="QUESTION", target_skill_node_id=skill, target_subconcept_node_id=sub, transformed_form=form, transformation_type=ttype,
        difficulty_direction=direction, source_problem_id=source, anchor_step_ids=list(anchors), learning_item_id=lid,
        content_sha256="s" * 64).to_metadata()) for i, k in enumerate(keys)])
    if facets:
        for dim, value in (("TARGET_SKILL", skill), ("TARGET_SUBCONCEPT", sub), *(("ANCHOR", a) for a in anchors)):
            facet("LI", dim, value, lid, keys)
    return keys


def add_node(store, nid: str, seed: int, *, ntype: str = "SKILL", chapter: int | None = 3, eligible: bool = True,
             stale_search: bool = False, parent: tuple[str, str] | None = ("GEO.C03", "Parent")) -> str:
    key, other = str(uuid.uuid4()), str(uuid.uuid4())
    typed.put(ContentTaxnode.model_validate({
        "PK": f"TAXNODE#{nid}", "SK": "META", "type": "TAXNODE", "content_sha256": "c" * 64, "eligible": eligible,
        "example_problem_codes": ["BK_P1", "BK_P2"], "lifecycle": "ACTIVE", "name": f"name {nid}", "node_type": ntype, "problem_count": 7,
        "src_rev": 1, "taxonomy_node_id": nid, "updated_at": NOW, "slug": nid.lower(), "slug_kind": "skill", "section_number": "3.1",
        "vector_state": {"index": Family.TAXONOMY_NODE.index_name, "keys": [key], "model": "text-embedding-3-small", "sha256": "s" * 64},
        "search_vector_state": {"index": Family.TAXONOMY_SEARCH.index_name, "keys": [other if stale_search else key],
                                "model": "text-embedding-3-small", "sha256": "s" * 64},
        **({"chapter_number": chapter} if chapter is not None else {}),
        **({"parent": {"id": parent[0], "name": parent[1]}} if parent else {})}))
    store.put(Family.TAXONOMY_SEARCH, [VectorItem(key=key, vector=vec(seed), metadata=TaxonomySearchMeta(
        node_type=ntype, chapter_number=chapter, taxonomy_node_id=nid, content_sha256="s" * 64, representation_id="r").to_metadata())])
    facet("TAXSEARCH", "NODETYPE", ntype, nid, [key])
    if chapter is not None:
        facet("TAXSEARCH", "CHAPTER", str(chapter), nid, [key])
    return key


def ids(rows, key="solution_step_id") -> list[str]:
    return [r[key] for r in rows]


# ------------------------------------------------------------------ filter mapping

def test_each_allow_listed_filter_maps_to_a_metadata_filter():
    p = "11111111-1111-1111-1111-111111111111"
    step = {"skill_node_id": "S", "subconcept_node_id": "SB", "concept_node_id": "C", "step_type": "T", "tutor_role": "R",
            "is_checkpoint": True, "problem_id": p, "exclude_problem_id": p, "max_hint_level": 2, "technique_node_id": "TECH"}
    expected = {"skill_node_id": vf.eq("skill_node_id", "S"), "subconcept_node_id": vf.eq("subconcept_node_id", "SB"),
                "concept_node_id": vf.eq("concept_node_id", "C"), "step_type": vf.eq("step_type", "T"),
                "tutor_role": vf.eq("tutor_role", "R"), "is_checkpoint": vf.eq("is_checkpoint", True),
                "problem_id": vf.eq("problem_id", p), "exclude_problem_id": vf.ne("problem_id", p),
                "max_hint_level": vf.lte("hint_level", 2), "technique_node_id": vf.eq("technique_node_ids", "TECH")}
    for name, value in step.items():
        assert ssv.build_filter("step", {name: value}) == expected[name], name
    item = {"target_skill_node_id": "S", "target_subconcept_node_id": "SB", "learning_item_type": "MCQ", "transformation_type": "X",
            "difficulty": "LOWER", "anchor_step_id": "STEP-1", "exclude_problem_id": p}
    expected = {"target_skill_node_id": vf.eq("target_skill_node_id", "S"),
                "target_subconcept_node_id": vf.eq("target_subconcept_node_id", "SB"),
                "learning_item_type": vf.eq("transformed_form", "MCQ"), "transformation_type": vf.eq("transformation_type", "X"),
                "difficulty": vf.eq("difficulty_direction", "LOWER"), "anchor_step_id": vf.eq("anchor_step_ids", "STEP-1"),
                "exclude_problem_id": vf.ne("source_problem_id", p)}
    for name, value in item.items():
        assert ssv.build_filter("learning_item", {name: value}) == expected[name], name
    assert ssv.build_filter("taxonomy", {"node_types": ["SKILL", "CONCEPT"]}) == vf.in_("node_type", ["SKILL", "CONCEPT"])
    assert ssv.build_filter("taxonomy", {"chapter_number": 3}) == vf.eq("chapter_number", 3)
    assert ssv.build_filter("step", {"skill_node_id": None}) is None
    assert ssv.build_filter("step", {"skill_node_id": "S", "step_type": "T"}) == {
        "$and": [vf.eq("skill_node_id", "S"), vf.eq("step_type", "T")]}


def test_every_filter_key_is_filterable_in_the_family_metadata():
    from mathbank_rest.vector_catalog import meta_model
    from mathbank_rest.vector_store import filter_keys

    probes = {"step": {"skill_node_id": "S", "subconcept_node_id": "S", "concept_node_id": "S", "step_type": "S", "tutor_role": "S",
                       "is_checkpoint": True, "problem_id": "p", "exclude_problem_id": "p", "max_hint_level": 1, "technique_node_id": "S"},
              "learning_item": {"target_skill_node_id": "S", "target_subconcept_node_id": "S", "learning_item_type": "S",
                                "transformation_type": "S", "difficulty": "S", "anchor_step_id": "S", "exclude_problem_id": "p"},
              "taxonomy": {"node_types": ["SKILL"], "chapter_number": 1}}
    for unit, filters in probes.items():
        assert filter_keys(ssv.build_filter(unit, filters)) <= meta_model(ssv._UNITS[unit].family).filterable()


@pytest.mark.parametrize("exact_max", [300, 0], ids=["exact", "ann"])
def test_step_filters_select_the_same_rows_through_the_exact_and_ann_paths(world, monkeypatch, exact_max):
    store, _ = world
    monkeypatch.setattr(ssv, "EXACT_MAX", exact_max)
    p1, p2 = str(uuid.uuid4()), str(uuid.uuid4())
    add_step(store, "S1", 1, problem=p1, skill="SKILL.A", sub="SUB.1", concept="CON.1", step_type="COMPUTE", role="CORE_BRIDGE",
             hint=1, checkpoint=True, techniques=("TECH.X",))
    add_step(store, "S2", 2, problem=p2, skill="SKILL.A", sub="SUB.2", concept="CON.1", step_type="DEFINE", role="ORIENT_OR_SETUP",
             hint=3, techniques=("TECH.X", "TECH.Y"))
    add_step(store, "S3", 3, problem=p2, skill="SKILL.B", sub="SUB.2", concept="CON.2", step_type="COMPUTE", role="CONCLUSION", hint=2)
    cases = [
        ({"skill_node_id": "SKILL.A"}, {"S1", "S2"}), ({"subconcept_node_id": "SUB.2"}, {"S2", "S3"}),
        ({"concept_node_id": "CON.2"}, {"S3"}), ({"step_type": "COMPUTE"}, {"S1", "S3"}),
        ({"tutor_role": "CONCLUSION"}, {"S3"}), ({"is_checkpoint": True}, {"S1"}), ({"is_checkpoint": False}, {"S2", "S3"}),
        ({"problem_id": p2}, {"S2", "S3"}), ({"exclude_problem_id": p2}, {"S1"}), ({"max_hint_level": 2}, {"S1", "S3"}),
        ({"technique_node_id": "TECH.Y"}, {"S2"}), ({"technique_node_id": "TECH.X"}, {"S1", "S2"}),
        ({"skill_node_id": "SKILL.A", "exclude_problem_id": p1, "max_hint_level": 3}, {"S2"}),
        ({"problem_id": p2, "step_type": "COMPUTE"}, {"S3"}), ({}, {"S1", "S2", "S3"}),
    ]
    for filters, want in cases:
        assert set(ids(step_search.search_solution_steps("inversion", **filters))) == want, filters


@pytest.mark.parametrize("exact_max", [300, 0], ids=["exact", "ann"])
def test_learning_item_and_taxonomy_filters(world, monkeypatch, exact_max):
    store, _ = world
    monkeypatch.setattr(ssv, "EXACT_MAX", exact_max)
    p1, p2 = str(uuid.uuid4()), str(uuid.uuid4())
    add_li(store, "L1", 1, source=p1, skill="SKILL.A", sub="SUB.1", form="MCQ", ttype="MCQ_FIRST_MOVE", anchors=("STEP-1", "STEP-2"))
    add_li(store, "L2", 2, source=p2, skill="SKILL.B", sub="SUB.1", form="SUBPROBLEM", ttype="SUBPROBLEM_FIRST_MOVE", anchors=("STEP-2",))
    add_li(store, "L3", 3, source=p2, skill="SKILL.A", sub="SUB.2", form="MCQ", ttype="MCQ_LOCAL_GOAL", direction="HIGHER",
           anchors=("STEP-3",))
    cases = [
        ({"target_skill_node_id": "SKILL.A"}, {"L1", "L3"}), ({"target_subconcept_node_id": "SUB.1"}, {"L1", "L2"}),
        ({"learning_item_type": "SUBPROBLEM"}, {"L2"}), ({"transformation_type": "MCQ_LOCAL_GOAL"}, {"L3"}),
        ({"difficulty": "HIGHER"}, {"L3"}), ({"anchor_step_id": "STEP-2"}, {"L1", "L2"}), ({"exclude_problem_id": p2}, {"L1"}),
        ({"target_skill_node_id": "SKILL.A", "exclude_problem_id": p1}, {"L3"}), ({}, {"L1", "L2", "L3"}),
    ]
    for filters, want in cases:
        assert set(ids(step_search.search_learning_items("inversion", **filters), "learning_item_id")) == want, filters
    add_node(store, "N.SKILL", 1, ntype="SKILL", chapter=3)
    add_node(store, "N.CONCEPT", 2, ntype="CONCEPT", chapter=4)
    add_node(store, "N.SUB", 3, ntype="SUBCONCEPT", chapter=3)
    tax = lambda **f: set(ids(step_search.search_taxonomy_nodes("inversion", **f), "taxonomy_node_id"))
    assert tax(node_types=["SKILL"]) == {"N.SKILL"} and tax(node_types=["SKILL", "CONCEPT"]) == {"N.SKILL", "N.CONCEPT"}
    assert tax(chapter_number=3) == {"N.SKILL", "N.SUB"} and tax(node_types=["SUBCONCEPT"], chapter_number=3) == {"N.SUB"}
    assert tax() == {"N.SKILL", "N.CONCEPT", "N.SUB"} and tax(chapter_number=99) == set()


# ------------------------------------------------------------------ hydration

def test_step_rows_have_the_sql_shape_and_step_text_is_opt_in(world):
    store, queries = world
    p = str(uuid.uuid4())
    add_step(store, "S1", 1, problem=p, techniques=("TECH.X",))
    rows = step_search.search_solution_steps("inversion", skill_node_id="SKILL.A")
    assert set(rows[0]) == STEP_KEYS and queries == ["inversion"]
    assert rows[0]["problem_id"] == p and isinstance(rows[0]["solution_id"], str) and rows[0]["problem_code"] == "BK_S1"
    assert rows[0]["skill_name"] == "name of SKILL.A" and rows[0]["hint_level"] == 1 and rows[0]["global_step_index"] == 4
    assert rows[0]["rrf_score"] == pytest.approx(1.0) and rows[0]["semantic_rank"] == 1 and rows[0]["lexical_rank"] is None
    with_text = step_search.search_solution_steps("inversion", include_step_text=True)
    assert set(with_text[0]) == STEP_KEYS | {"step_text"} and with_text[0]["step_text"] == "text of S1"


def test_learning_item_and_taxonomy_rows_have_the_sql_shape(world):
    store, _ = world
    add_li(store, "L1", 1)
    add_node(store, "N.A", 1)
    add_node(store, "N.B", 2, chapter=None, parent=None)
    item = step_search.search_learning_items("inversion")[0]
    assert set(item) == ITEM_KEYS and item["learning_item_type"] == "MCQ" and item["choices"] == ["a", "b"]
    assert item["question_text"] == "question L1" and isinstance(item["source_problem_id"], str)
    nodes = {r["taxonomy_node_id"]: r for r in step_search.search_taxonomy_nodes("inversion")}
    a, b = nodes["N.A"], nodes["N.B"]
    assert set(a) == TAXONOMY_KEYS and a["parent_node_id"] == "GEO.C03" and a["parent_name"] == "Parent" and a["chapter_number"] == 3
    assert a["problem_count"] == 7 and a["example_problem_codes"] == ["BK_P1", "BK_P2"] and a["slug"] == "n.a" and a["slug_kind"] == "skill"
    assert b["parent_node_id"] is None and b["parent_name"] is None and b["chapter_number"] is None
    assert a["rrf_score"] == pytest.approx(1.0) and a["semantic_rank"] == 1 and nodes["N.B"]["semantic_rank"] == 2


def test_results_are_ranked_by_similarity_best_first(world):
    store, _ = world
    for i, seed in enumerate((5, 1, 3)):
        add_step(store, f"S{i}", seed)
    rows = step_search.search_solution_steps("inversion")
    assert ids(rows)[0] == "S1" and [r["semantic_rank"] for r in rows] == [1, 2, 3]
    assert [r["rrf_score"] for r in rows] == sorted((r["rrf_score"] for r in rows), reverse=True)


# ------------------------------------------------------------------ eligibility and dedupe

def test_ineligible_unpublished_stale_and_missing_content_never_surface(world):
    store, _ = world
    add_step(store, "OK", 1)
    add_step(store, "OFF", 1, eligible=False)
    add_step(store, "STALE", 1, stale=True)
    store.put(Family.STEP, [VectorItem(key="orphan", vector=vec(1), metadata=StepMeta(
        problem_id="p", solution_step_id="GONE", content_sha256="s").to_metadata())])
    assert ids(step_search.search_solution_steps("inversion")) == ["OK"]
    assert ids(step_search.search_solution_steps("inversion", skill_node_id="SKILL.A")) == ["OK"]      # exact path rechecks too
    add_li(store, "L-OK", 1), add_li(store, "L-OFF", 1, eligible=False), add_li(store, "L-STALE", 1, stale=True)
    assert ids(step_search.search_learning_items("inversion"), "learning_item_id") == ["L-OK"]
    add_node(store, "N-OK", 1), add_node(store, "N-OFF", 1, eligible=False)
    add_node(store, "N-STALE", 1, stale_search=True)                           # only its *search* vector counts for taxonomy-search
    assert ids(step_search.search_taxonomy_nodes("inversion"), "taxonomy_node_id") == ["N-OK"]


def test_an_entity_with_several_vectors_appears_once_with_its_best_distance(world):
    store, _ = world
    add_li(store, "L1", 1, chunks=3), add_li(store, "L2", 2)
    rows = step_search.search_learning_items("inversion", limit=10)
    assert ids(rows, "learning_item_id").count("L1") == 1 and rows[0]["learning_item_id"] == "L1"
    assert rows[0]["rrf_score"] == pytest.approx(1.0) and [r["semantic_rank"] for r in rows] == [1, 2]
    exact = step_search.search_learning_items("inversion", target_skill_node_id="SKILL.A", limit=10)
    assert ids(exact, "learning_item_id").count("L1") == 1


def test_limit_is_applied_after_the_eligibility_recheck(world):
    store, _ = world
    for i in range(12):
        add_step(store, f"BAD{i}", 1, eligible=False)
    for i in range(3):
        add_step(store, f"GOOD{i}", 10 + i)
    assert len(step_search.search_solution_steps("inversion", limit=3)) == 3
    assert len(step_search.search_solution_steps("inversion", limit=3, skill_node_id="SKILL.A")) == 3


# ------------------------------------------------------------------ exact vs ANN

def test_exact_and_ann_paths_give_the_same_ranking(world, monkeypatch):
    store, _ = world
    problem = str(uuid.uuid4())
    for i, seed in enumerate((4, 1, 9, 1, 7, 2)):                              # two steps share a vector: a genuine tie
        add_step(store, f"S{i}", seed, problem=problem if i % 2 else None, skill="SKILL.A")
    add_step(store, "OTHER", 1, skill="SKILL.B")
    flt = {"skill_node_id": "SKILL.A", "exclude_problem_id": str(uuid.uuid4()), "max_hint_level": 3}
    monkeypatch.setattr(ssv, "EXACT_MAX", 300)
    before = store.queries
    exact = step_search.search_solution_steps("inversion", limit=10, **flt)
    assert store.queries == before                                             # exact path: no ANN query
    monkeypatch.setattr(ssv, "EXACT_MAX", 0)
    ann = step_search.search_solution_steps("inversion", limit=10, **flt)
    assert store.queries == before + 1
    assert [round(r["rrf_score"], 9) for r in exact] == [round(r["rrf_score"], 9) for r in ann] and len(exact) == 6
    for score in {round(r["rrf_score"], 9) for r in exact}:                    # tie-aware: compare the sets within equal scores
        assert {r["solution_step_id"] for r in exact if round(r["rrf_score"], 9) == score} == \
               {r["solution_step_id"] for r in ann if round(r["rrf_score"], 9) == score}


def test_a_selective_filter_without_facets_or_above_the_limit_falls_back_to_ann(world, monkeypatch):
    store, _ = world
    add_step(store, "S1", 1, facets=False)
    add_step(store, "S2", 2, facets=False)
    assert set(ids(step_search.search_solution_steps("inversion", skill_node_id="SKILL.A"))) == {"S1", "S2"}   # no FACET items: ANN
    assert store.queries == 1
    add_step(store, "S3", 3)
    monkeypatch.setattr(ssv, "EXACT_MAX", 0)
    assert ssv.facet_candidates("step", {"skill_node_id": "SKILL.A"}) is None
    assert ssv.facet_candidates("step", {"step_type": "COMPUTE"}) is None      # no facet dimension for step_type
    monkeypatch.setattr(ssv, "EXACT_MAX", 300)
    assert set(ssv.facet_candidates("step", {"skill_node_id": "SKILL.A"}).values()) == {"S3"}
    assert ssv.facet_candidates("step", {"skill_node_id": "SKILL.NONE"}) is None


def test_the_most_selective_facet_that_fits_is_used(world, monkeypatch):
    store, _ = world
    problem = str(uuid.uuid4())
    for i in range(5):
        add_step(store, f"S{i}", i + 1, problem=problem if i < 2 else None)
    monkeypatch.setattr(ssv, "EXACT_MAX", 3)
    cands = ssv.facet_candidates("step", {"skill_node_id": "SKILL.A", "problem_id": problem})   # skill has 5 > 3, problem has 2
    assert set(cands.values()) == {"S0", "S1"}
    assert ssv.facet_candidates("step", {"skill_node_id": "SKILL.A"}) is None


# ------------------------------------------------------------------ query vector

def test_query_vector_text_skips_the_embedding_call(world):
    store, queries = world
    add_step(store, "S1", 1), add_step(store, "S2", 2)
    text = "[" + ",".join(repr(x) for x in vec(2)) + "]"
    rows = step_search.search_solution_steps("anything", query_vector=text)
    assert queries == [] and rows[0]["solution_step_id"] == "S2"
    with pytest.raises(ValueError, match="query_vector"):
        step_search.search_solution_steps("x", query_vector="not a vector")
    assert step_search.search_taxonomy_nodes("x", query_vector=text) == []


def test_lexical_is_not_applied_and_semantic_false_returns_nothing(world):
    store, queries = world
    add_step(store, "S1", 1)
    assert step_search.search_solution_steps("inversion", semantic=False, lexical=True) == []
    assert queries == []
    assert step_search.search_solution_steps("inversion", semantic=True, lexical=False)[0]["lexical_rank"] is None
    with pytest.raises(ValueError, match="semantic or lexical"):
        step_search.search_solution_steps("x", semantic=False, lexical=False)


def test_limit_validation_and_unknown_filters_raise_like_the_sql_path(world):
    for bad in (0, 51, -1):
        with pytest.raises(ValueError, match="limit must be between 1 and 50"):
            step_search.search_solution_steps("x", limit=bad)
        with pytest.raises(ValueError, match="limit must be between 1 and 50"):
            step_search.search_taxonomy_nodes("x", limit=bad)
    with pytest.raises(ValueError, match=r"Unsupported step filter\(s\): \['bogus'\]"):
        ssv.search("step", "x", {"bogus": 1}, semantic=True, lexical=True, limit=5)
    with pytest.raises(ValueError, match=r"Unsupported learning_item filter\(s\)"):
        ssv.search("learning_item", "x", {"skill_node_id": "S"}, semantic=True, lexical=True, limit=5)
    with pytest.raises(ValueError, match="Unsupported node type"):
        step_search.search_taxonomy_nodes("x", node_types=["PROBLEM"])


# ------------------------------------------------------------------ similar_steps_for_step

def test_similar_steps_uses_the_stored_vector_and_excludes_the_own_problem(world):
    store, queries = world
    own = str(uuid.uuid4())
    add_step(store, "ANCHOR", 1, problem=own, skill="SKILL.A")
    add_step(store, "SAME-PROBLEM", 1, problem=own, skill="SKILL.A")
    add_step(store, "SIM1", 1, skill="SKILL.A"), add_step(store, "SIM2", 2, skill="SKILL.A")
    add_step(store, "OTHER-SKILL", 1, skill="SKILL.B")
    out = step_search.similar_steps_for_step("ANCHOR", limit=5)
    assert queries == []                                                       # no paid embedding call
    assert out["embedding_available"] is True and out["anchor"] == {
        "solution_step_id": "ANCHOR", "skill_node_id": "SKILL.A", "skill_name": "name of SKILL.A", "step_type": "COMPUTE"}
    assert ids(out["results"]) == ["SIM1", "SIM2"] and all("step_text" not in r for r in out["results"])
    wide = ids(step_search.similar_steps_for_step("ANCHOR", same_skill=False)["results"])
    assert set(wide[:2]) == {"SIM1", "OTHER-SKILL"} and "SAME-PROBLEM" not in wide and "ANCHOR" not in wide


def test_similar_steps_for_an_unknown_unpublished_or_unembedded_step(world):
    store, _ = world
    add_step(store, "OFF", 1, eligible=False)
    for missing in ("NOPE", "OFF"):
        with pytest.raises(LookupError):
            step_search.similar_steps_for_step(missing)
    add_step(store, "NOVEC", 1)
    store.delete(Family.STEP, list(store.keys(Family.STEP)))
    out = step_search.similar_steps_for_step("NOVEC")
    assert out["embedding_available"] is False and out["results"] == []


# ------------------------------------------------------------------ flag off and the concept-search route

def test_the_postgres_path_runs_when_the_flag_is_off(monkeypatch):
    set_vector_store_for_tests(None)
    monkeypatch.setattr(settings, "vector_store", "pgvector")
    monkeypatch.setattr(ssv, "search", lambda *a, **k: pytest.fail("vector path must not run"))
    monkeypatch.setattr(ssv, "similar_steps", lambda *a, **k: pytest.fail("vector path must not run"))
    calls = []

    class Conn:
        def __enter__(self):
            calls.append(1)
            raise RuntimeError("postgres reached")

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(step_search, "engine", type("E", (), {"connect": lambda self: Conn()})())
    for fn in (lambda: step_search.search_solution_steps("x", semantic=False),
               lambda: step_search.search_learning_items("x", semantic=False),
               lambda: step_search.search_taxonomy_nodes("x", semantic=False),
               lambda: step_search.similar_steps_for_step("S1")):
        with pytest.raises(RuntimeError, match="postgres reached"):
            fn()
    assert len(calls) == 4
    with pytest.raises(ValueError, match="limit must be between 1 and 50"):
        step_search.search_solution_steps("x", limit=0)


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from mathbank_rest.main import app

    return TestClient(app)


ADMIN = lambda: {"X-Admin-Api-Key": settings.admin_api_key}


def test_concept_search_route_in_s3_mode_is_semantic_only(world, client):
    store, queries = world
    add_node(store, "N.A", 1), add_node(store, "N.B", 2, ntype="CONCEPT")
    body = client.post("/v1/search/concepts", json={"query": " inversion ", "node_types": ["SKILL"]}, headers=ADMIN())
    assert body.status_code == 200, body.text
    data = body.json()
    assert [r["taxonomy_node_id"] for r in data["results"]] == ["N.A"] and queries == ["inversion"]
    assert data["retrieval"] == {"semantic": "queried", "lexical": "not_applied", "unit": "TAXONOMY_NODE", "profile": step_search.PROFILE_NAME}
    assert any("Lexical ranking is not applied" in w for w in data["warnings"]) and set(data["results"][0]) == TAXONOMY_KEYS
    only_semantic = client.post("/v1/search/concepts", json={"query": "inversion", "retrieval": {"lexical": False}}, headers=ADMIN()).json()
    assert only_semantic["retrieval"]["lexical"] == "disabled" and only_semantic["warnings"] == []
    lexical_only = client.post("/v1/search/concepts", json={"query": "inversion", "retrieval": {"semantic": False}}, headers=ADMIN()).json()
    assert lexical_only["results"] == [] and lexical_only["retrieval"]["lexical"] == "not_applied"


def test_concept_search_route_keeps_the_anonymous_rules_and_never_falls_back(world, client, monkeypatch):
    store, queries = world
    add_node(store, "N.A", 1)
    assert client.post("/v1/search/concepts", json={"query": "inversion"}).status_code == 401      # no free source with S3 Vectors
    assert queries == []

    def boom(text):
        raise RuntimeError("provider down")

    monkeypatch.setattr(embeddings, "EMBEDDER", boom)
    embeddings.reset_for_tests()
    failed = client.post("/v1/search/concepts", json={"query": "unseen topic"}, headers=ADMIN())
    assert failed.status_code == 503 and failed.json()["detail"]["code"] == "SEMANTIC_UNAVAILABLE"
    assert client.post("/v1/search/concepts", json={"query": "x", "node_types": ["PROBLEM"]}, headers=ADMIN()).status_code == 422


def test_rate_limit_module_is_still_the_gate_for_embeddings(world):
    with rate_limit.embeddings_blocked(), pytest.raises(rate_limit.EmbeddingsNotPermitted):
        step_search.search_taxonomy_nodes("never embedded before")
