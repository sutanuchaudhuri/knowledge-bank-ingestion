"""
SQLite schema — CREATE TABLE statements for every corpus entity.

Column types are TEXT throughout so raw CSV values load without coercion.
Numeric columns are REAL or INTEGER where the pipeline always writes numbers.
Every table has a rowid (implicit) plus the domain primary key as TEXT PK.
"""

# Each entry: (table_name, [(col_name, col_type), ...])
# First column is the primary key when marked PK.

TABLES: list[tuple[str, list[tuple[str, str]]]] = [

    # ── Competitions ─────────────────────────────────────────────────────────
    ("competitions", [
        ("competition_id",       "TEXT PRIMARY KEY"),
        ("competition",          "TEXT"),
        ("event_or_round",       "TEXT"),
        ("archive_from",         "TEXT"),
        ("archive_through",      "TEXT"),
        ("question_format",      "TEXT"),
        ("typical_structure",    "TEXT"),
        ("canonical_archive_url","TEXT"),
        ("taxonomy_mode",        "TEXT"),
        ("attempt_folder",       "TEXT"),
        ("question_work_folder", "TEXT"),
        ("ai_review_folder",     "TEXT"),
        ("notes",                "TEXT"),
    ]),

    # ── Archive Families ──────────────────────────────────────────────────────
    ("archive_families", [
        ("archive_record_id",    "TEXT PRIMARY KEY"),
        ("competition_id",       "TEXT"),
        ("years",                "TEXT"),
        ("division_or_format",   "TEXT"),
        ("round_set",            "TEXT"),
        ("canonical_archive_url","TEXT"),
        ("problem_availability", "TEXT"),
        ("solution_availability","TEXT"),
        ("stable_id_pattern",    "TEXT"),
        ("archive_index_status", "TEXT"),
        ("question_level_status","TEXT"),
        ("taxonomy_status",      "TEXT"),
        ("last_refresh",         "TEXT"),
        ("notes",                "TEXT"),
        ("next_level_registry",  "TEXT"),
        ("event_registry_status","TEXT"),
        ("hierarchy_level",      "TEXT"),
        ("agent_traversal_rule", "TEXT"),
    ]),

    # ── Tournament Events ─────────────────────────────────────────────────────
    ("tournament_events", [
        ("tournament_event_id",      "TEXT PRIMARY KEY"),
        ("archive_family_id",        "TEXT"),
        ("competition_id",           "TEXT"),
        ("year",                     "TEXT"),
        ("event_or_season",          "TEXT"),
        ("event_status",             "TEXT"),
        ("year_or_event_page_url",   "TEXT"),
        ("parent_archive_url",       "TEXT"),
        ("paper_count",              "INTEGER"),
        ("problem_linked_papers",    "INTEGER"),
        ("solution_linked_papers",   "INTEGER"),
        ("round_set",                "TEXT"),
        ("question_index_status",    "TEXT"),
        ("taxonomy_status",          "TEXT"),
        ("source_resolution_status", "TEXT"),
        ("agent_next_action",        "TEXT"),
        ("notes",                    "TEXT"),
        ("last_refresh",             "TEXT"),
        ("hierarchy_level",          "TEXT"),
        ("agent_traversal_rule",     "TEXT"),
    ]),

    # ── Exam Entries (test_registry) ──────────────────────────────────────────
    ("exam_entries", [
        ("test_id",                       "TEXT PRIMARY KEY"),
        ("exam_level",                    "TEXT"),
        ("year",                          "TEXT"),
        ("form",                          "TEXT"),
        ("session",                       "TEXT"),
        ("aops_test_url",                 "TEXT"),
        ("question_count",                "INTEGER"),
        ("attempt_status",                "TEXT"),
        ("latest_attempt_id",             "TEXT"),
        ("latest_score",                  "TEXT"),
        ("latest_attempt_date",           "TEXT"),
        ("full_test_artifact_url",        "TEXT"),
        ("latest_ai_review_id",           "TEXT"),
        ("notes",                         "TEXT"),
        ("competition_id",                "TEXT"),
        ("registered_question_count",     "INTEGER"),
        ("taxonomy_mapping_row_count",    "INTEGER"),
        ("taxonomy_distinct_question_count","INTEGER"),
        ("link_status",                   "TEXT"),
        ("link_type",                     "TEXT"),
        ("source_id",                     "TEXT"),
        ("registry_coverage_status",      "TEXT"),
        ("agent_next_action",             "TEXT"),
        ("paper_id",                      "TEXT"),
        ("direct_problem_url",            "TEXT"),
        ("direct_solution_url",           "TEXT"),
        ("tournament_event_id",           "TEXT"),
        ("fine_mapped_question_count",    "INTEGER"),
        ("taxonomy_completion_status",    "TEXT"),
        ("parsing_batch_eligibility",     "TEXT"),
    ]),

    # ── Papers ────────────────────────────────────────────────────────────────
    ("papers", [
        ("paper_id",              "TEXT PRIMARY KEY"),
        ("competition_id",        "TEXT"),
        ("year_or_years",         "TEXT"),
        ("test_or_round",         "TEXT"),
        ("link_scope",            "TEXT"),
        ("problem_url",           "TEXT"),
        ("solution_url",          "TEXT"),
        ("link_status",           "TEXT"),
        ("test_id",               "TEXT"),
        ("question_count",        "INTEGER"),
        ("question_index_status", "TEXT"),
        ("taxonomy_status",       "TEXT"),
        ("technique_status",      "TEXT"),
        ("source_record",         "TEXT"),
        ("last_refresh",          "TEXT"),
        ("next_action",           "TEXT"),
        ("notes",                 "TEXT"),
        ("year_or_event_page_url","TEXT"),
        ("test_id_row_count",     "INTEGER"),
        ("canonical_row_status",  "TEXT"),
        ("tournament_event_id",   "TEXT"),
        ("hierarchy_level",       "TEXT"),
        ("agent_traversal_rule",  "TEXT"),
    ]),

    # ── Questions (question_index) ────────────────────────────────────────────
    ("questions", [
        ("question_id",                 "TEXT PRIMARY KEY"),
        ("competition_id",              "TEXT"),
        ("test_id",                     "TEXT"),
        ("exam_level",                  "TEXT"),
        ("year",                        "TEXT"),
        ("form",                        "TEXT"),
        ("session",                     "TEXT"),
        ("q_number",                    "INTEGER"),
        ("aops_question_url",           "TEXT"),
        ("primary_topic",               "TEXT"),
        ("subtopic",                    "TEXT"),
        ("technique",                   "TEXT"),
        ("difficulty_band",             "TEXT"),
        ("correct_answer",              "TEXT"),
        ("latest_student_answer",       "TEXT"),
        ("latest_result",               "TEXT"),
        ("latest_confidence",           "TEXT"),
        ("latest_time_sec",             "REAL"),
        ("latest_work_artifact_url",    "TEXT"),
        ("latest_error_id",             "TEXT"),
        ("retest_status",               "TEXT"),
        ("paper_id",                    "TEXT"),
        ("direct_problem_url",          "TEXT"),
        ("direct_solution_url",         "TEXT"),
        ("granular_link_status",        "TEXT"),
        ("year_or_event_page_url",      "TEXT"),
        ("tournament_event_id",         "TEXT"),
        ("taxonomy_mapping_count",      "INTEGER"),
        ("distinct_concept_id_count",   "INTEGER"),
        ("high_confidence_mapping_count","INTEGER"),
        ("technique_mapping_count",     "INTEGER"),
        ("fine_concept_mapping_count",  "INTEGER"),
        ("classification_status",       "TEXT"),
        ("taxonomy_evidence_status",    "TEXT"),
    ]),

    # ── Concepts (canonical_topic_hierarchy) ──────────────────────────────────
    ("concepts", [
        ("canonical_topic_id",  "TEXT PRIMARY KEY"),
        ("domain",              "TEXT"),
        ("topic",               "TEXT"),
        ("subtopic",            "TEXT"),
        ("concept_or_technique","TEXT"),
        ("node_type",           "TEXT"),
        ("parent_id",           "TEXT"),
        ("canonical_path",      "TEXT"),
        ("definition",          "TEXT"),
        ("synonyms",            "TEXT"),
        ("related_nodes",       "TEXT"),
        ("amc10",               "TEXT"),
        ("amc12",               "TEXT"),
        ("aime",                "TEXT"),
        ("mpg",                 "TEXT"),
        ("hmmt",                "TEXT"),
        ("smt",                 "TEXT"),
        ("pumac",               "TEXT"),
        ("cmm",                 "TEXT"),
        ("chmmc",               "TEXT"),
    ]),

    # ── Topic Aliases ─────────────────────────────────────────────────────────
    ("topic_aliases", [
        ("alias",               "TEXT"),
        ("normalized_alias",    "TEXT"),
        ("canonical_topic_id",  "TEXT"),
        ("canonical_path",      "TEXT"),
        ("alias_type",          "TEXT"),
        ("priority",            "INTEGER"),
        ("notes",               "TEXT"),
    ]),

    # ── Techniques ────────────────────────────────────────────────────────────
    ("techniques", [
        ("technique_id",         "TEXT PRIMARY KEY"),
        ("parent_concept_id",    "TEXT"),
        ("technique_name",       "TEXT"),
        ("canonical_path",       "TEXT"),
        ("definition",           "TEXT"),
        ("recognition_signals",  "TEXT"),
        ("algebraic_signature",  "TEXT"),
        ("aliases",              "TEXT"),
        ("related_techniques",   "TEXT"),
        ("can_cooccur",          "TEXT"),
        ("primary_or_secondary", "TEXT"),
        ("evidence_standard",    "TEXT"),
        ("agent_search_terms",   "TEXT"),
        ("notes",                "TEXT"),
    ]),

    # ── Question Taxonomy Map ─────────────────────────────────────────────────
    ("question_taxonomy_maps", [
        ("mapping_id",           "TEXT PRIMARY KEY"),
        ("question_id",          "TEXT"),
        ("test_id",              "TEXT"),
        ("exam_level",           "TEXT"),
        ("domain",               "TEXT"),
        ("concept_id",           "TEXT"),
        ("concept",              "TEXT"),
        ("concept_type",         "TEXT"),
        ("solution_id",          "TEXT"),
        ("association_type",     "TEXT"),
        ("evidence_source",      "TEXT"),
        ("evidence_url",         "TEXT"),
        ("confidence",           "TEXT"),
        ("notes",                "TEXT"),
        ("canonical_paper_id",   "TEXT"),
        ("direct_problem_url",   "TEXT"),
        ("direct_solution_url",  "TEXT"),
        ("canonical_evidence_url","TEXT"),
        ("canonical_node_type",  "TEXT"),
        ("canonical_path",       "TEXT"),
        ("tournament_event_id",  "TEXT"),
    ]),

    # ── Question Technique Map ────────────────────────────────────────────────
    ("question_technique_maps", [
        ("technique_map_id",           "TEXT PRIMARY KEY"),
        ("question_id",                "TEXT"),
        ("parent_concept_id",          "TEXT"),
        ("technique_id",               "TEXT"),
        ("technique_name",             "TEXT"),
        ("role",                       "TEXT"),
        ("solution_id",                "TEXT"),
        ("competition_id",             "TEXT"),
        ("year",                       "TEXT"),
        ("form_round",                 "TEXT"),
        ("problem_number",             "TEXT"),
        ("evidence_source",            "TEXT"),
        ("evidence_url",               "TEXT"),
        ("evidence_confidence",        "TEXT"),
        ("evidence_snippet_or_reason", "TEXT"),
        ("classification_status",      "TEXT"),
        ("last_reviewed",              "TEXT"),
        ("notes",                      "TEXT"),
        ("canonical_paper_id",         "TEXT"),
        ("direct_problem_url",         "TEXT"),
        ("direct_solution_url",        "TEXT"),
        ("canonical_evidence_url",     "TEXT"),
        ("tournament_event_id",        "TEXT"),
    ]),

    # ── Knowledge Graph Edges ─────────────────────────────────────────────────
    ("knowledge_graph_edges", [
        ("edge_id",          "TEXT PRIMARY KEY"),
        ("from_type",        "TEXT"),
        ("from_id",          "TEXT"),
        ("edge_type",        "TEXT"),
        ("to_type",          "TEXT"),
        ("to_id",            "TEXT"),
        ("weight",           "REAL"),
        ("evidence_type",    "TEXT"),
        ("evidence_id",      "TEXT"),
        ("evidence_url",     "TEXT"),
        ("confidence",       "TEXT"),
        ("student_specific", "TEXT"),
        ("valid_from",       "TEXT"),
        ("valid_to",         "TEXT"),
        ("notes",            "TEXT"),
    ]),

    # ── Source Ingestion Queue ────────────────────────────────────────────────
    ("source_ingestion", [
        ("source_id",                     "TEXT PRIMARY KEY"),
        ("competition_id",                "TEXT"),
        ("source_type",                   "TEXT"),
        ("canonical_source_url",          "TEXT"),
        ("scope",                         "TEXT"),
        ("question_index_status",         "TEXT"),
        ("solution_classification_status","TEXT"),
        ("rag_summary_status",            "TEXT"),
        ("last_crawled",                  "TEXT"),
        ("next_action",                   "TEXT"),
        ("copyright_rule",                "TEXT"),
        ("notes",                         "TEXT"),
    ]),

    # ── Topic Coverage Matrix ─────────────────────────────────────────────────
    ("topic_coverage", [
        ("canonical_topic_id",      "TEXT"),
        ("canonical_path",          "TEXT"),
        ("competition_id",          "TEXT"),
        ("indexed_question_count",  "INTEGER"),
        ("solution_reviewed_count", "INTEGER"),
        ("high_confidence_count",   "INTEGER"),
        ("medium_confidence_count", "INTEGER"),
        ("low_confidence_count",    "INTEGER"),
        ("earliest_year",           "TEXT"),
        ("latest_year",             "TEXT"),
        ("coverage_status",         "TEXT"),
        ("last_refresh",            "TEXT"),
        ("missing_ranges",          "TEXT"),
        ("notes",                   "TEXT"),
    ]),

    # ── AIME Year Index ───────────────────────────────────────────────────────
    ("aime_year_index", [
        ("test_id",            "TEXT PRIMARY KEY"),
        ("year",               "TEXT"),
        ("form",               "TEXT"),
        ("aops_test_url",      "TEXT"),
        ("question_count",     "INTEGER"),
        ("entry_q1_5",         "TEXT"),
        ("core_q6_9",          "TEXT"),
        ("advanced_q10_12",    "TEXT"),
        ("elite_q13_15",       "TEXT"),
        ("question_id_prefix", "TEXT"),
        ("index_status",       "TEXT"),
        ("topic_tag_status",   "TEXT"),
    ]),

    # ── AIME Glossary ─────────────────────────────────────────────────────────
    ("aime_glossary", [
        ("glossary_id",             "TEXT PRIMARY KEY"),
        ("domain",                  "TEXT"),
        ("topic",                   "TEXT"),
        ("subtopic",                "TEXT"),
        ("term",                    "TEXT"),
        ("node_type",               "TEXT"),
        ("definition",              "TEXT"),
        ("typical_aime_signal",     "TEXT"),
        ("related_nodes",           "TEXT"),
        ("agent_search_terms",      "TEXT"),
        ("canonical_path",          "TEXT"),
        ("aime_mapping_rows",       "TEXT"),
        ("distinct_aime_questions", "TEXT"),
        ("high_confidence_rows",    "TEXT"),
        ("example_question_ids",    "TEXT"),
        ("frequency_band",          "TEXT"),
        ("glossary_status",         "TEXT"),
    ]),

    # ── Unparsed Paper Queue ──────────────────────────────────────────────────
    ("unparsed_papers", [
        ("paper_id",              "TEXT PRIMARY KEY"),
        ("tournament_event_id",   "TEXT"),
        ("competition_id",        "TEXT"),
        ("year",                  "TEXT"),
        ("test_or_round",         "TEXT"),
        ("problem_url",           "TEXT"),
        ("solution_url",          "TEXT"),
        ("question_count",        "INTEGER"),
        ("question_index_status", "TEXT"),
        ("taxonomy_status",       "TEXT"),
        ("link_status",           "TEXT"),
        ("year_or_event_page_url","TEXT"),
        ("priority",              "TEXT"),
        ("agent_next_action",     "TEXT"),
        ("last_refresh",          "TEXT"),
    ]),

    # ── Unmapped Question Queue ───────────────────────────────────────────────
    ("unmapped_questions", [
        ("question_id",        "TEXT PRIMARY KEY"),
        ("test_id",            "TEXT"),
        ("exam_level",         "TEXT"),
        ("year",               "TEXT"),
        ("form",               "TEXT"),
        ("session",            "TEXT"),
        ("q_number",           "TEXT"),
        ("problem_url",        "TEXT"),
        ("suggested_domain",   "TEXT"),
        ("inference_basis",    "TEXT"),
        ("suggested_confidence","TEXT"),
        ("mapping_status",     "TEXT"),
        ("priority",           "TEXT"),
        ("next_action",        "TEXT"),
        ("notes",              "TEXT"),
    ]),

    # ── Fine Concept Gap Queue ────────────────────────────────────────────────
    ("fine_concept_gaps", [
        ("question_id",              "TEXT PRIMARY KEY"),
        ("test_id",                  "TEXT"),
        ("exam_level",               "TEXT"),
        ("year",                     "TEXT"),
        ("form",                     "TEXT"),
        ("session",                  "TEXT"),
        ("q_number",                 "TEXT"),
        ("paper_id",                 "TEXT"),
        ("tournament_event_id",      "TEXT"),
        ("direct_problem_url",       "TEXT"),
        ("direct_solution_url",      "TEXT"),
        ("taxonomy_mapping_count",   "INTEGER"),
        ("fine_concept_mapping_count","INTEGER"),
        ("classification_status",    "TEXT"),
        ("taxonomy_evidence_status", "TEXT"),
        ("priority",                 "TEXT"),
        ("agent_next_action",        "TEXT"),
    ]),

    # ── Corpus Task Tracker ───────────────────────────────────────────────────
    ("corpus_tasks", [
        ("task_id",          "TEXT PRIMARY KEY"),
        ("workstream",       "TEXT"),
        ("competition_scope","TEXT"),
        ("task",             "TEXT"),
        ("status",           "TEXT"),
        ("baseline",         "TEXT"),
        ("current_coverage", "TEXT"),
        ("last_action",      "TEXT"),
        ("next_action",      "TEXT"),
        ("evidence_tab",     "TEXT"),
        ("evidence_url",     "TEXT"),
        ("owner",            "TEXT"),
        ("last_updated",     "TEXT"),
        ("notes",            "TEXT"),
    ]),

    # ── Fast Topic Question Index ─────────────────────────────────────────────
    ("fast_topic_index", [
        ("index_key",           "TEXT PRIMARY KEY"),
        ("canonical_topic_id",  "TEXT"),
        ("canonical_path",      "TEXT"),
        ("association_type",    "TEXT"),
        ("competition_id",      "TEXT"),
        ("year",                "TEXT"),
        ("event_form_round",    "TEXT"),
        ("question_id",         "TEXT"),
        ("problem_number",      "TEXT"),
        ("problem_url",         "TEXT"),
        ("solution_id",         "TEXT"),
        ("solution_url",        "TEXT"),
        ("difficulty_band",     "TEXT"),
        ("student_attempt_status","TEXT"),
        ("student_result",      "TEXT"),
        ("latest_attempt_id",   "TEXT"),
        ("latest_ai_review_id", "TEXT"),
        ("evidence_confidence", "TEXT"),
    ]),

    # ── Domain Indexed Questions (union of 4 domain sheets) ───────────────────
    ("domain_indexed_questions", [
        ("rowid_",              "INTEGER PRIMARY KEY AUTOINCREMENT"),
        ("domain",              "TEXT"),
        ("question_id",         "TEXT"),
        ("test_id",             "TEXT"),
        ("competition",         "TEXT"),
        ("concept_id",          "TEXT"),
        ("concept_or_technique","TEXT"),
        ("solution_id",         "TEXT"),
        ("association_type",    "TEXT"),
        ("evidence_source",     "TEXT"),
        ("evidence_url",        "TEXT"),
        ("confidence",          "TEXT"),
        ("notes",               "TEXT"),
        ("canonical_paper_id",  "TEXT"),
        ("direct_problem_url",  "TEXT"),
        ("direct_solution_url", "TEXT"),
        ("canonical_evidence_url","TEXT"),
        ("source_link_level",   "TEXT"),
        ("canonical_node_type", "TEXT"),
        ("canonical_path",      "TEXT"),
        ("tournament_event_id", "TEXT"),
    ]),

    # ── Documents (markdown artifacts — populated by pipeline) ────────────────
    ("documents", [
        ("doc_id",         "TEXT PRIMARY KEY"),
        ("course_id",      "TEXT"),
        ("entity_type",    "TEXT"),
        ("entity_id",      "TEXT"),
        ("chunk_index",    "INTEGER"),
        ("char_count",     "INTEGER"),
        ("content_hash",   "TEXT"),
        ("local_md_path",  "TEXT"),
        ("gcs_uri",        "TEXT"),
        ("drive_file_id",  "TEXT"),
        ("drive_url",      "TEXT"),
        ("created_at",     "TEXT"),
    ]),

    # ── Visual Assets (images extracted from PDFs — populated by pipeline) ────
    ("visual_assets", [
        ("asset_id",             "TEXT PRIMARY KEY"),
        ("question_id",          "TEXT"),
        ("paper_id",             "TEXT"),
        ("source_side",          "TEXT"),
        ("asset_type",           "TEXT"),
        ("page_number",          "INTEGER"),
        ("local_file_path",      "TEXT"),
        ("pixel_width",          "INTEGER"),
        ("pixel_height",         "INTEGER"),
        ("bbox_pdf",             "TEXT"),
        ("drive_asset_url",      "TEXT"),
        ("captures_vector_content","TEXT"),
        ("created_at",           "TEXT"),
    ]),
]

# ── Indexes ───────────────────────────────────────────────────────────────────

INDEXES: list[tuple[str, str, list[str]]] = [
    ("idx_questions_exam_level",   "questions",              ["exam_level"]),
    ("idx_questions_primary_topic","questions",              ["primary_topic"]),
    ("idx_questions_difficulty",   "questions",              ["difficulty_band"]),
    ("idx_questions_paper",        "questions",              ["paper_id"]),
    ("idx_questions_test",         "questions",              ["test_id"]),
    ("idx_questions_classification","questions",             ["classification_status"]),
    ("idx_qtm_question",           "question_taxonomy_maps", ["question_id"]),
    ("idx_qtm_concept",            "question_taxonomy_maps", ["concept_id"]),
    ("idx_qtechm_question",        "question_technique_maps",["question_id"]),
    ("idx_qtechm_technique",       "question_technique_maps",["technique_id"]),
    ("idx_papers_competition",     "papers",                 ["competition_id"]),
    ("idx_papers_link_status",     "papers",                 ["link_status"]),
    ("idx_exam_entries_competition","exam_entries",           ["competition_id"]),
    ("idx_concepts_domain",        "concepts",               ["domain"]),
    ("idx_concepts_node_type",     "concepts",               ["node_type"]),
    ("idx_fast_topic_concept",     "fast_topic_index",       ["canonical_topic_id"]),
    ("idx_fast_topic_question",    "fast_topic_index",       ["question_id"]),
    ("idx_domain_idx_domain",      "domain_indexed_questions",["domain"]),
    ("idx_domain_idx_question",    "domain_indexed_questions",["question_id"]),
    ("idx_domain_idx_concept",     "domain_indexed_questions",["concept_id"]),
    ("idx_kg_from",                "knowledge_graph_edges",  ["from_id"]),
    ("idx_kg_to",                  "knowledge_graph_edges",  ["to_id"]),
    ("idx_kg_edge_type",           "knowledge_graph_edges",  ["edge_type"]),
    ("idx_visual_question",        "visual_assets",          ["question_id"]),
    ("idx_visual_paper",           "visual_assets",          ["paper_id"]),
    ("idx_documents_entity",       "documents",              ["entity_type", "entity_id"]),
]

# ── Views ─────────────────────────────────────────────────────────────────────

VIEWS: list[tuple[str, str]] = [
    ("v_question_concept_summary", """
        SELECT
            q.question_id,
            q.exam_level,
            q.year,
            q.q_number,
            q.primary_topic,
            q.subtopic,
            q.difficulty_band,
            q.classification_status,
            q.fine_concept_mapping_count,
            c.canonical_path,
            c.definition
        FROM questions q
        LEFT JOIN concepts c ON q.primary_topic = c.topic
            AND c.node_type IN ('Topic','Concept')
    """),

    ("v_topic_question_counts", """
        SELECT
            primary_topic,
            COUNT(*) AS total_questions,
            SUM(CASE WHEN classification_status = 'FINE_COMPLETE' THEN 1 ELSE 0 END) AS fine_complete,
            SUM(CASE WHEN difficulty_band = 'easy'      THEN 1 ELSE 0 END) AS easy,
            SUM(CASE WHEN difficulty_band = 'medium'    THEN 1 ELSE 0 END) AS medium,
            SUM(CASE WHEN difficulty_band = 'hard'      THEN 1 ELSE 0 END) AS hard,
            SUM(CASE WHEN difficulty_band = 'very_hard' THEN 1 ELSE 0 END) AS very_hard
        FROM questions
        WHERE primary_topic != ''
        GROUP BY primary_topic
        ORDER BY total_questions DESC
    """),

    ("v_competition_coverage", """
        SELECT
            p.competition_id,
            COUNT(DISTINCT p.paper_id)   AS paper_count,
            SUM(p.question_count)        AS expected_questions,
            COUNT(DISTINCT q.question_id) AS indexed_questions,
            SUM(CASE WHEN q.classification_status = 'FINE_COMPLETE' THEN 1 ELSE 0 END) AS fine_complete_questions
        FROM papers p
        LEFT JOIN questions q ON q.paper_id = p.paper_id
        GROUP BY p.competition_id
        ORDER BY indexed_questions DESC
    """),

    ("v_unmapped_by_competition", """
        SELECT
            q.exam_level,
            COUNT(*) AS unmapped_count
        FROM unmapped_questions q
        GROUP BY q.exam_level
        ORDER BY unmapped_count DESC
    """),

    ("v_fine_gap_by_competition", """
        SELECT
            exam_level,
            COUNT(*) AS gap_count,
            SUM(CASE WHEN priority = 'P0' THEN 1 ELSE 0 END) AS p0_count
        FROM fine_concept_gaps
        GROUP BY exam_level
        ORDER BY gap_count DESC
    """),

    ("v_technique_usage", """
        SELECT
            t.technique_name,
            t.parent_concept_id,
            COUNT(DISTINCT m.question_id) AS question_count,
            SUM(CASE WHEN m.evidence_confidence = 'high' THEN 1 ELSE 0 END) AS high_confidence
        FROM techniques t
        LEFT JOIN question_technique_maps m ON m.technique_id = t.technique_id
        GROUP BY t.technique_id
        ORDER BY question_count DESC
    """),
]
