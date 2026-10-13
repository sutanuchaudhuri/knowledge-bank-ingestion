"""Regression tests for the revised corpus_models schema."""
from datetime import date, datetime
from mathbank.corpus_models import (
    ArchiveFamily, TournamentEvent, SourceIngestionRecord,
    Course, Competition, ExamEntry, Paper, Question,
    Concept, TopicAlias, Technique, QuestionTaxonomyMap, QuestionTechniqueMap,
    KnowledgeGraphEdge,
    UnparsedPaperQueueItem, UnmappedQuestionQueueItem,
    FineConceptGapItem, ParseBatchItem, CorpusTask,
    TopicCoverageMetric, DomainIndexedQuestion, AIMEYearIndex,
    Document, Chunk,
    EducationLevel, CompetitionType, IngestionStatus, ClassificationStatus,
    LinkStatus, DifficultyBand, Confidence, TaxonomyNodeType,
    AssociationType, ChunkType, EntityType, Priority, TaskStatus,
)


def test_archive_family_round_trip():
    af = ArchiveFamily(
        archive_record_id="AF_AMC10",
        competition_id="AMC10",
        years="2000-2024",
    )
    assert af.firestore_doc_id() == "AF_AMC10"
    assert af.archive_index_status == IngestionStatus.pending


def test_tournament_event():
    te = TournamentEvent(
        tournament_event_id="TE_AMC10A_2023",
        archive_family_id="AF_AMC10",
        competition_id="AMC10",
        year=2023,
        paper_count=1,
    )
    assert te.firestore_doc_id() == "TE_AMC10A_2023"
    assert te.question_index_status == IngestionStatus.pending


def test_source_ingestion_all_stages_pending():
    s = SourceIngestionRecord(
        source_id="SRC_AMC10A_2023",
        competition_id="AMC10",
        canonical_source_url="https://artofproblemsolving.com/wiki/2023_AMC_10A",
    )
    for field in ("crawl_status", "parse_status", "question_index_status",
                  "solution_classification_status", "rag_summary_status"):
        assert getattr(s, field) == IngestionStatus.pending, field


def test_course_round_trip():
    c = Course(
        course_id="COURSE_AMC10_PREP",
        display_name="AMC 10 Preparation",
        level=EducationLevel.high_school,
        competition_ids=["AMC10"],
    )
    assert c.firestore_doc_id() == "COURSE_AMC10_PREP"
    data = c.model_dump()
    assert Course(**data) == c


def test_competition_fields():
    comp = Competition(
        competition_id="AMC10",
        display_name="AMC 10",
        competition_type=CompetitionType.individual,
        level=EducationLevel.high_school,
        canonical_archive_url="https://artofproblemsolving.com/wiki/AMC_10",
        taxonomy_mode="FINE",
        archive_from=2000,
        archive_through=2024,
    )
    assert comp.taxonomy_mode == "FINE"
    assert comp.archive_from == 2000


def test_test_registry_entry():
    t = ExamEntry(
        test_id="AMC10A_2023",
        competition_id="AMC10",
        year=2023,
        form="A",
        question_count=30,
        registered_question_count=30,
        fine_mapped_question_count=28,
        link_status=LinkStatus.valid,
    )
    assert t.firestore_doc_id() == "AMC10A_2023"
    assert t.link_status == LinkStatus.valid


def test_paper_inherits_course_id():
    p = Paper(
        paper_id="PAPER_AMC10A_2023",
        course_id="COURSE_AMC10_PREP",
        test_id="AMC10A_2023",
        competition_id="AMC10",
        year=2023,
        tournament_event_id="TE_AMC10A_2023",
    )
    assert p.course_id == "COURSE_AMC10_PREP"
    assert p.firestore_doc_id() == "PAPER_AMC10A_2023"
    assert p.question_index_status == IngestionStatus.pending


def test_question_semicolon_split():
    q = Question(
        question_id="AMC10A_2023_Q05",
        course_id="COURSE_AMC10_PREP",
        paper_id="PAPER_AMC10A_2023",
        q_number=5,
        concept_ids="PROB_COND;PROB_BASIC",  # type: ignore[arg-type]
        technique_ids="TECH_CASEWORK",       # type: ignore[arg-type]
    )
    assert q.concept_ids == ["PROB_COND", "PROB_BASIC"]
    assert q.technique_ids == ["TECH_CASEWORK"]
    assert q.firestore_doc_id() == "AMC10A_2023_Q05"


def test_question_attempt_tracking():
    q = Question(
        question_id="AMC10A_2023_Q05",
        course_id="COURSE_AMC10_PREP",
        paper_id="PAPER_AMC10A_2023",
        q_number=5,
        latest_student_answer="C",
        latest_time_sec=180,
        retest_status="NOT_REQUIRED",
    )
    assert q.latest_student_answer == "C"
    assert q.latest_time_sec == 180


def test_concept_competition_flags():
    c = Concept(
        canonical_topic_id="PROB_COND",
        domain="Probability",
        topic="Conditional Probability",
        node_type=TaxonomyNodeType.concept,
        canonical_path="Probability/Conditional Probability",
        definition="Probability of A given B.",
        amc10=True,
        amc12=True,
        aime=True,
    )
    assert c.amc10 is True
    assert c.hmmt is False
    assert c.firestore_doc_id() == "PROB_COND"


def test_topic_alias_firestore_id():
    alias = TopicAlias(
        alias="conditional probability",
        canonical_topic_id="PROB_COND",
        alias_type="SYNONYM",
    )
    fid = alias.firestore_doc_id()
    assert "conditional" in fid


def test_technique_fields():
    t = Technique(
        technique_id="TECH_CASEWORK",
        technique_name="Casework",
        parent_concept_id="COMB",
        definition="Enumerate all disjoint cases and sum their counts.",
        recognition_signals="'how many ways', distinct case boundaries",
        primary_or_secondary="PRIMARY",
    )
    assert t.firestore_doc_id() == "TECH_CASEWORK"
    assert t.primary_or_secondary == "PRIMARY"


def test_question_taxonomy_map():
    m = QuestionTaxonomyMap(
        mapping_id="MAP_PROB_COND_AMC10A_2023_Q05_V1",
        question_id="AMC10A_2023_Q05",
        concept_id="PROB_COND",
        association_type=AssociationType.primary_concept,
        confidence=Confidence.high,
    )
    assert m.firestore_doc_id() == "MAP_PROB_COND_AMC10A_2023_Q05_V1"


def test_question_technique_map():
    m = QuestionTechniqueMap(
        technique_map_id="TMAP_AMC10A_2023_Q05_TECH_CASEWORK_V1",
        question_id="AMC10A_2023_Q05",
        technique_id="TECH_CASEWORK",
        evidence_confidence=Confidence.high,
        classification_status=ClassificationStatus.solution_reviewed,
    )
    assert m.classification_status == ClassificationStatus.solution_reviewed


def test_knowledge_graph_edge():
    e = KnowledgeGraphEdge(
        edge_id="EDGE_PROB_COND_PROB_BASIC_PREREQ",
        from_type="Concept",
        from_id="PROB_COND",
        edge_type="PREREQUISITE",
        to_type="Concept",
        to_id="PROB_BASIC",
        weight=0.9,
    )
    assert e.firestore_doc_id() == "EDGE_PROB_COND_PROB_BASIC_PREREQ"
    assert e.weight == 0.9


def test_unparsed_paper_queue():
    item = UnparsedPaperQueueItem(
        paper_id="PAPER_HMMT_FEB_2023_TEAM",
        competition_id="HMMT",
        year=2023,
        question_count=10,
        priority=Priority.p1,
    )
    assert item.question_index_status == IngestionStatus.pending


def test_fine_concept_gap_item():
    item = FineConceptGapItem(
        question_id="AMC10A_2021_Q18",
        classification_status=ClassificationStatus.partial,
        fine_concept_mapping_count=0,
        priority=Priority.p0,
    )
    assert item.fine_concept_mapping_count == 0


def test_parse_batch_item_doc_id():
    b = ParseBatchItem(
        batch_id="COLLEGE_BATCH_001",
        slot=3,
        test_id="AMC10A_2023",
        expected_questions=30,
        current_status="PREPARED",
        agent_action="VALIDATE",
    )
    assert b.firestore_doc_id() == "COLLEGE_BATCH_001_S03"


def test_corpus_task():
    t = CorpusTask(
        task_id="TASK_AMC10_TAXONOMY_2023",
        workstream="Taxonomy",
        status=TaskStatus.in_progress,
        current_coverage="18/30",
    )
    assert t.firestore_doc_id() == "TASK_AMC10_TAXONOMY_2023"


def test_topic_coverage_metric_doc_id():
    m = TopicCoverageMetric(
        canonical_topic_id="PROB_COND",
        competition_id="AMC10",
        indexed_question_count=14,
        high_confidence_count=12,
        coverage_status="STRONG",
    )
    assert m.firestore_doc_id() == "PROB_COND__AMC10"


def test_aime_year_index():
    a = AIMEYearIndex(
        test_id="AIME_I_2023",
        year=2023,
        form="I",
        question_count=15,
        index_status=IngestionStatus.indexed,
    )
    assert a.firestore_doc_id() == "AIME_I_2023"
    assert a.question_count == 15


def test_domain_indexed_question():
    q = DomainIndexedQuestion(
        question_id="AMC10A_2023_Q12",
        competition="AMC10",
        concept_id="COMB_CASEWORK",
        domain="Combinatorics",
        confidence=Confidence.high,
    )
    assert q.domain == "Combinatorics"


def test_document():
    d = Document(
        doc_id="DOC_PAPER_AMC10A_2023",
        course_id="COURSE_AMC10_PREP",
        entity_type=EntityType.paper,
        entity_id="PAPER_AMC10A_2023",
        gcs_uri="gs://mathbank-corpus-docs/papers/PAPER_AMC10A_2023.md",
    )
    assert d.firestore_doc_id() == "DOC_PAPER_AMC10A_2023"
    assert d.chunk_index == 0


def test_chunk_no_embedding_vector():
    c = Chunk(
        chunk_id="CHK_AMC10A_2023_Q05_STMT",
        course_id="COURSE_AMC10_PREP",
        doc_id="DOC_Q_AMC10A_2023_Q05",
        question_id="AMC10A_2023_Q05",
        competition_id="AMC10",
        primary_topic="Probability",
        difficulty_band=DifficultyBand.medium,
        chunk_type=ChunkType.statement,
        content="Find the probability that...",
        token_count=148,
        embedding_model="text-embedding-004",
    )
    assert c.firestore_doc_id() == "CHK_AMC10A_2023_Q05_STMT"
    assert not hasattr(c, "embedding_vector")  # vector lives in Vector Search, not here
