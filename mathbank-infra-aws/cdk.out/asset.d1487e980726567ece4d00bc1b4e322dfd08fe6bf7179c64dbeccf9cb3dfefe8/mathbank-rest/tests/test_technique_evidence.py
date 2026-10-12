from sqlalchemy import create_engine

from mathbank_rest.db import queries


def test_technique_readers_agree_and_do_not_resurrect_rejections(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        for schema in ("core", "knowledge", "pedagogy"):
            conn.exec_driver_sql(f"ATTACH DATABASE ':memory:' AS {schema}")
        definitions = [
            "core.competition(competition_id TEXT,name TEXT,external_code TEXT)",
            "core.competition_edition(edition_id TEXT,competition_id TEXT,year INTEGER)",
            "core.paper(paper_id TEXT,edition_id TEXT,paper_code TEXT)",
            "core.problem(problem_id TEXT,canonical_code TEXT,problem_number INTEGER,paper_id TEXT,official_answer TEXT,source_url TEXT)",
            "knowledge.technique(technique_id TEXT,slug TEXT)",
            "knowledge.problem_technique(problem_id TEXT,technique_id TEXT,role TEXT,confidence REAL,review_status TEXT,approval_method TEXT)",
            "pedagogy.taxonomy_node(taxonomy_node_id TEXT,technique_id TEXT)",
            "pedagogy.solution_step(solution_step_id TEXT,problem_id TEXT,publication_status TEXT)",
            "pedagogy.solution_step_technique(solution_step_id TEXT,technique_node_id TEXT,confidence REAL,review_status TEXT)",
        ]
        for definition in definitions:
            conn.exec_driver_sql(f"CREATE TABLE {definition}")
        conn.exec_driver_sql("INSERT INTO core.competition VALUES('c','Competition','C')")
        conn.exec_driver_sql("INSERT INTO core.competition_edition VALUES('e','c',2000)")
        conn.exec_driver_sql("INSERT INTO core.paper VALUES('pa','e','PAPER')")
        conn.exec_driver_sql("INSERT INTO knowledge.technique VALUES('t','power-point')")
        conn.exec_driver_sql("INSERT INTO pedagogy.taxonomy_node VALUES('node','t')")
        for index, (code, status, method, step_status, tag_status) in enumerate([
            ("STEP_ONLY", None, None, "PUBLISHED", "APPROVED"),
            ("SUPPORTED", "REVIEWED", "automatic", "PUBLISHED", "APPROVED"),
            ("WRONG", "REVIEWED", "automatic", "PUBLISHED", None),
            ("HUMAN", "REVIEWED", "human", "PUBLISHED", None),
            ("NON_STEP", "REVIEWED", "automatic", None, None),
            ("REJECTED", "REJECTED", "human", "PUBLISHED", "APPROVED"),
            ("PENDING", "PENDING", None, "PUBLISHED", "APPROVED"),
            ("UNPUBLISHED", None, None, "DRAFT", "APPROVED"),
            ("UNAPPROVED", None, None, "PUBLISHED", "PENDING_REVIEW"),
        ]):
            conn.exec_driver_sql("INSERT INTO core.problem VALUES(?,?,?,'pa',NULL,NULL)", (code, code, index))
            if status:
                conn.exec_driver_sql(
                    "INSERT INTO knowledge.problem_technique VALUES(?,'t','PRIMARY',0.94,?,?)",
                    (code, status, method),
                )
            if step_status:
                conn.exec_driver_sql("INSERT INTO pedagogy.solution_step VALUES(?,?,?)", (code, code, step_status))
            if tag_status:
                conn.exec_driver_sql(
                    "INSERT INTO pedagogy.solution_step_technique VALUES(?,'node',0.8,?)", (code, tag_status),
                )
    monkeypatch.setattr(queries, "engine", engine)
    listed = queries.get_technique_problems("power-point")
    filtered = queries.list_problems(technique="power-point")
    expected = {"STEP_ONLY", "SUPPORTED", "HUMAN", "NON_STEP"}
    assert {p["canonical_code"] for p in listed} == expected
    assert {p["canonical_code"] for p in filtered} == expected
    assert next(p for p in listed if p["canonical_code"] == "STEP_ONLY")["role"] == "STEP_SUPPORTED"
    assert len(queries.list_problems()) == 9
    engine.dispose()
