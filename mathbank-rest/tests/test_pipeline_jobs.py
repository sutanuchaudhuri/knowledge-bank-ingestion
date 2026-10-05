from datetime import datetime, timezone

from mathbank_rest.db.pipeline_jobs import apply_relationships, build_item, coverage_status


def fixture():
    return (
        {
            "download_status": "DOWNLOADED",
            "parse_status": "PARSED",
            "ingest_status": "INGESTED",
            "question_count": 1,
        },
        [
            {
                "problem_id": "p",
                "concept_edges": 1,
                "technique_edges": 0,
                "skill_edges": 1,
                "difficulty": True,
                "solutions": 1,
                "images": 2,
                "pedagogy_status": "COMPLETED",
                "published_at": datetime.now(timezone.utc),
                "pedagogy_at": None,
                "last_error": None,
            }
        ],
        [
            {"chunks": 2, "embedded": 2, "representations": 1, "embedded_at": None},
            {"chunks": 1, "embedded": 1, "representations": 1, "embedded_at": None},
        ],
        {("p", "TESTS", "c", "primary", "REVIEWED", "automatic", 0.9)},
        {("p", "s", "REQUIRES", "primary", "REVIEWED", "automatic")},
        {
            "p": {
                "pedagogy_status": "REVIEWED",
                "edges": [
                    ["TESTS", "c", "primary", "REVIEWED", "automatic", 0.9, "automatic", "corpus"],
                    [
                        "REQUIRES",
                        "s",
                        "primary",
                        "REVIEWED",
                        "automatic",
                        0.9,
                        "automatic",
                        "skill",
                    ],
                ],
            }
        },
    )


def test_complete_requires_every_layer():
    item, *args = fixture()
    build_item(item, *args, datetime.now(timezone.utc))
    assert item["overall_status"] == "COMPLETED"
    assert item["metrics"]["embedded_chunks"] == 3
    assert item["metrics"]["solutions"] == 1


def test_single_vector_is_not_complete_problem_or_solution_coverage():
    item, ps, vs, *rest = fixture()
    vs[0]["embedded"] = 1
    build_item(item, ps, vs, *rest, datetime.now(timezone.utc))
    assert item["stages"]["vectors"]["status"] == "PARTIAL"
    assert item["overall_status"] != "COMPLETED"


def test_outage_is_unknown_not_zero_or_completed():
    item, ps, vs, edges, skills, _ = fixture()
    build_item(item, ps, vs, edges, skills, None, datetime.now(timezone.utc))
    assert item["stages"]["graph"]["status"] == "UNKNOWN"
    assert item["metrics"]["graph_corpus_edges"] is None
    assert item["overall_status"] != "COMPLETED"


def test_same_edge_count_wrong_identity_is_not_complete():
    item, ps, vs, edges, skills, graph = fixture()
    graph["p"]["edges"][0][1] = "wrong"
    build_item(item, ps, vs, edges, skills, graph, datetime.now(timezone.utc))
    assert item["stages"]["graph"]["status"] == "PARTIAL"


def test_missing_source_history_never_certifies_end_to_end():
    item, *args = fixture()
    item["download_status"] = None
    build_item(item, *args, datetime.now(timezone.utc))
    assert item["stages"]["download"]["status"] == "NOT_TRACKED"
    assert item["overall_status"] != "COMPLETED"


def test_expected_count_and_empty_scope():
    assert coverage_status(0, 0) == "PENDING"
    item, *args = fixture()
    item["question_count"] = 2
    build_item(item, *args, datetime.now(timezone.utc))
    assert item["stages"]["ingest"]["status"] == "PARTIAL"


def test_relationship_publication_is_a_separate_completion_gate():
    item, *args = fixture()
    build_item(item, *args, datetime.now(timezone.utc))
    apply_relationships(
        item,
        [
            {
                "id": "s",
                "status": "FAILED",
                "published_at": None,
                "updated_at": None,
                "last_error": "cycle rejected",
            }
        ],
        [],
        set(),
    )
    assert item["stages"]["relationships"]["status"] == "FAILED"
    assert item["overall_status"] == "FAILED"
    assert "cycle rejected" in item["errors"]


def test_relationship_equal_counts_wrong_direction_is_partial():
    item, *args = fixture()
    build_item(item, *args, datetime.now(timezone.utc))
    anchors = [
        {
            "id": "s",
            "status": "COMPLETED",
            "published_at": datetime.now(timezone.utc),
            "updated_at": None,
            "last_error": None,
        }
    ]
    expected = [
        {
            "kind": "skill",
            "src": "s",
            "dst": "t",
            "relation_type": "PART_OF",
            "review_status": "REVIEWED",
            "approval_method": "automatic",
        }
    ]
    apply_relationships(
        item, anchors, expected, {("skill", "t", "s", "PART_OF", "REVIEWED", "automatic")}
    )
    assert item["stages"]["relationships"]["status"] == "PARTIAL"
    assert item["overall_status"] != "COMPLETED"


def test_stale_in_progress_is_not_success():
    item, ps, vs, edges, skills, graph = fixture()
    vs[0]["embedded"] = 0
    item.update(
        batch_status="IN_PROGRESS",
        batch_metrics={"stage": "vectors"},
        heartbeat_at=None,
        run_status="IN_PROGRESS",
    )
    build_item(item, ps, vs, edges, skills, graph, datetime.now(timezone.utc))
    assert item["stages"]["vectors"]["status"] == "STALLED"


def test_verified_classifier_done_before_batch_mapping_import():
    item, ps, vs, edges, skills, graph = fixture()
    ps[0]["concept_edges"] = 0
    item.update(
        batch_status="IN_PROGRESS",
        batch_metrics={
            "stage": "classified",
            "classification_status": "COMPLETED",
            "questions": 1,
        },
    )
    build_item(item, ps, vs, edges, skills, graph, datetime.now(timezone.utc))
    assert item["stages"]["classify"]["status"] == "COMPLETED"
    assert item["metrics"]["classified_problems"] == 0
    assert item["metrics"]["verified_classifier_problems"] == 1
    assert item["stages"]["graph"]["status"] != "COMPLETED"
