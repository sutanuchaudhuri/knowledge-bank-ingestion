import pytest
from fakes import FakeDynamo, FakeS3, FakeS3Vectors, offloaded, unit_vector

from mathbank_genai_poc.config import Settings
from mathbank_genai_poc.knowledge import (
    Clients,
    ContentIntegrityError,
    KnowledgeBase,
    TopicError,
    clean,
    public_view,
)


def hit(key, distance, **metadata):
    return {"key": key, "distance": distance, "metadata": metadata}


def build(hits, items, objects=None, unprocessed_once=False, embed_calls=None):
    calls = embed_calls if embed_calls is not None else []

    def embed(text):
        calls.append(text)
        return unit_vector()

    vectors = FakeS3Vectors(hits)
    dynamo = FakeDynamo(items, unprocessed_once=unprocessed_once)
    kb = KnowledgeBase(Settings(), embedder=embed, clients=Clients(vectors, dynamo, FakeS3(objects or {})))
    return kb, vectors, dynamo


def taxnode(node_id, keys, eligible=True, **extra):
    return {"PK": f"TAXNODE#{node_id}", "SK": "META", "type": "TAXNODE", "taxonomy_node_id": node_id,
            "name": node_id.title(), "node_type": "SKILL", "eligible": eligible,
            "search_vector_state": {"keys": keys}, "vector_state": {"keys": ["other"]}, **extra}


def step(step_id, keys, text="Draw the bisector and compare the two triangle areas.", eligible=True):
    return {"PK": f"STEP#{step_id}", "SK": "META", "type": "STEP", "solution_step_id": step_id, "eligible": eligible,
            "skill_name": "Apply the angle bisector theorem", "problem_code": "P1", "tutor_role": "CORE_BRIDGE",
            "step_text": text, "vector_state": {"keys": keys}}


def problem(code, keys, visibility="ACTIVE", **extra):
    return {"PK": f"PROBLEM#{code}", "SK": "META", "type": "PROBLEM", "canonical_code": code, "visibility": visibility,
            "competition": {"name": "Prasolov"}, "vector_state": {"keys": keys}, **extra}


def test_search_hydrates_only_published_current_hits_and_hides_private_moves():
    statement_ref, body = offloaded("In triangle ABC the bisector of angle A meets BC at D. Prove BD/DC = AB/AC.", "p/2")
    kb, vectors, _ = build(
        hits={
            "taxonomy-search": [hit("c1", 0.2, taxonomy_node_id="SKILL.BISECTOR"),
                                hit("c2", 0.25, taxonomy_node_id="SKILL.BISECTOR"),   # same node: deduplicated
                                hit("old", 0.1, taxonomy_node_id="SKILL.STALE"),      # vector key no longer current
                                hit("c3", 0.3, taxonomy_node_id="SKILL.HIDDEN"),      # not eligible
                                hit("far", 0.9, taxonomy_node_id="SKILL.FAR")],       # below similarity floor
            "step": [hit("s1", 0.3, solution_step_id="S1")],
            "problem": [hit("p1", 0.2, canonical_code="P1"), hit("p2", 0.3, canonical_code="P2"),
                        hit("p3", 0.3, canonical_code="P3")],
        },
        items=[
            taxnode("SKILL.BISECTOR", ["c1", "c2"], description="Ratio of sides adjacent to a bisected angle."),
            taxnode("SKILL.STALE", ["new-key"]),
            taxnode("SKILL.HIDDEN", ["c3"], eligible=False),
            step("S1", ["s1"]),
            problem("P1", ["p1"], visibility="HIDDEN", statement_text="hidden"),
            problem("P2", ["p2"], statement_text_ref=statement_ref),
            problem("P3", ["p3"], statement_text="Second practice problem."),
        ],
        objects={"p/2": body},
    )
    result = kb.search("  angle   bisector theorem ")
    assert result["topic"] == "angle bisector theorem" and result["grounded"]
    assert [c["id"] for c in result["concepts"]] == ["SKILL.BISECTOR"]
    assert result["concepts"][0]["similarity"] == 0.8
    assert [p["code"] for p in result["practice_problems"]] == ["P2", "P3"]
    assert result["practice_problems"][0]["statement"].startswith("In triangle ABC")
    assert result["teaching_moves"][0]["guidance"].startswith("Draw the bisector")
    public = public_view(result)
    assert public["teaching_moves"] == 1 and "Draw the bisector" not in str(public)
    assert {c["indexName"] for c in vectors.calls} == {
        "taxonomy-search-te3small-1536-v1", "step-te3small-1536-v1", "problem-te3small-1536-v1"}
    assert all(c["vectorBucketName"] == "mathbank-vectors-dev" for c in vectors.calls)


def test_weak_tail_matches_outside_relative_window_are_dropped():
    kb, _, _ = build(
        hits={"taxonomy-search": [hit("a", 0.30, taxonomy_node_id="A"), hit("b", 0.38, taxonomy_node_id="B"),
                                  hit("c", 0.45, taxonomy_node_id="C"), hit("d", 0.6, taxonomy_node_id="D")]},
        items=[taxnode("A", ["a"]), taxnode("B", ["b"]), taxnode("C", ["c"]), taxnode("D", ["d"])])
    # 0.70 best; 0.62 within 0.10; 0.55 outside the window; 0.40 below the 0.45 floor.
    assert [c["id"] for c in kb.search("power of a point")["concepts"]] == ["A", "B"]


def test_ungrounded_when_nothing_is_close():
    kb, _, dynamo = build(hits={"taxonomy-search": [hit("x", 0.95, taxonomy_node_id="A")]}, items=[])
    result = kb.search("cooking recipes")
    assert not result["grounded"] and not result["concepts"]
    assert dynamo.requests == []


def test_unprocessed_keys_are_retried():
    kb, _, dynamo = build(
        hits={"taxonomy-search": [hit("a", 0.1, taxonomy_node_id="A"), hit("b", 0.1, taxonomy_node_id="B")]},
        items=[taxnode("A", ["a"]), taxnode("B", ["b"])], unprocessed_once=True)
    assert len(kb.search("invariants")["concepts"]) == 2
    assert len(dynamo.requests) == 2


def test_offloaded_text_digest_mismatch_is_rejected():
    ref, body = offloaded("statement", "p/x")
    kb, _, _ = build(hits={"problem": [hit("p", 0.1, canonical_code="PX")]},
                     items=[problem("PX", ["p"], statement_text_ref=ref)], objects={"p/x": body + b" "})
    with pytest.raises(ContentIntegrityError):
        kb.search("similar triangles")


@pytest.mark.parametrize("topic", ["", " x ", "y" * 301])
def test_topic_bounds(topic):
    kb, _, _ = build(hits={}, items=[])
    with pytest.raises(TopicError):
        kb.search(topic)


def test_query_embeddings_are_cached_case_insensitively():
    calls = []
    kb, _, _ = build(hits={}, items=[], embed_calls=calls)
    kb.search("Power of a point")
    kb.search("power of a POINT")
    assert calls == ["Power of a point"]


def test_wrong_embedding_dimension_is_refused():
    kb = KnowledgeBase(Settings(), embedder=lambda _t: [0.1] * 1024, clients=Clients(None, None, None))
    with pytest.raises(ValueError, match="1536"):
        kb.search("vectors")


def test_clean_truncates_on_word_boundary():
    assert clean("one two three four", 9) == "one two …"
    assert clean(None, 5) == ""
