"""
MathBank corpus entity models — Pydantic v2.

Grounded in the CSV exports from the master question corpus spreadsheet.
Organised into eight layers:

  1. Enums
  2. Source & Archive tracking  (ArchiveFamily, TournamentEvent, SourceIngestionRecord)
  3. Core corpus entities       (Course, Competition, TestRegistryEntry, Paper, Question)
  4. Taxonomy & techniques      (Concept, TopicAlias, Technique,
                                 QuestionTaxonomyMap, QuestionTechniqueMap)
  5. Knowledge graph            (KnowledgeGraphEdge)
  6. Pipeline queues            (UnparsedPaperQueueItem, UnmappedQuestionQueueItem,
                                 FineConceptGapItem, ParseBatchItem, CorpusTask)
  7. Analytics & retrieval      (TopicCoverageMetric, DomainIndexedQuestion,
                                 AIMEYearIndex)
  8. Document storage           (Document, Chunk)

Every field carries a description.  Models carry json_schema_extra examples.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# 1. ENUMS
# ============================================================================

class CompetitionType(str, Enum):
    individual = "individual"
    team = "team"
    relay = "relay"


class EducationLevel(str, Enum):
    middle = "middle"
    high_school = "high_school"
    open = "open"


class DifficultyBand(str, Enum):
    entry = "entry"       # AIME Q1-5 / AMC easy
    core = "core"         # AIME Q6-9 / AMC medium
    advanced = "advanced" # AIME Q10-12 / AMC hard
    elite = "elite"       # AIME Q13-15
    easy = "easy"
    medium = "medium"
    hard = "hard"
    very_hard = "very_hard"


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class TaxonomyNodeType(str, Enum):
    domain = "Domain"
    topic = "Topic"
    concept = "Concept"
    subtopic = "Subtopic"
    technique = "Technique"


class AssociationType(str, Enum):
    primary_concept = "Primary Concept"
    additional_concept = "Additional Concept"
    technique_application = "Technique Application"


class ClassificationStatus(str, Enum):
    unclassified = "UNCLASSIFIED"
    partial = "PARTIAL"
    solution_reviewed = "SOLUTION_REVIEWED"
    fine_complete = "FINE_COMPLETE"
    skip_complete = "SKIP_COMPLETE"


class LinkStatus(str, Enum):
    valid = "VALID"
    broken = "BROKEN"
    redirected = "REDIRECTED"
    archive_only = "ARCHIVE_ONLY"
    unknown = "UNKNOWN"


class IngestionStatus(str, Enum):
    pending = "PENDING"
    crawling = "CRAWLING"
    crawled = "CRAWLED"
    parsing = "PARSING"
    parsed = "PARSED"
    indexed = "INDEXED"
    failed = "FAILED"
    skipped = "SKIPPED"


class SourceType(str, Enum):
    aops_wiki = "aops_wiki"
    official_site = "official_site"
    pdf = "pdf"
    html = "html"
    archive_org = "archive_org"
    unknown = "unknown"


class CopyrightRule(str, Enum):
    open = "open"
    fair_use = "fair_use"
    restricted = "restricted"
    unknown = "unknown"


class HierarchyLevel(str, Enum):
    archive_family = "archive_family"
    tournament_event = "tournament_event"
    paper = "paper"
    question = "question"


class AgentTraversalRule(str, Enum):
    expand_children = "EXPAND_CHILDREN"
    direct_index = "DIRECT_INDEX"
    skip = "SKIP"
    manual_review = "MANUAL_REVIEW"


class PipelineStage(str, Enum):
    """Ordered stages of the ingestion pipeline."""
    discover = "DISCOVER"
    crawl = "CRAWL"
    parse = "PARSE"
    extract = "EXTRACT"
    classify = "CLASSIFY"
    embed = "EMBED"
    sync = "SYNC"


class TaskStatus(str, Enum):
    not_started = "NOT_STARTED"
    in_progress = "IN_PROGRESS"
    blocked = "BLOCKED"
    done = "DONE"


class AttemptResult(str, Enum):
    correct = "CORRECT"
    incorrect = "INCORRECT"
    partial = "PARTIAL"
    skipped = "SKIPPED"


class EntityType(str, Enum):
    paper = "paper"
    question = "question"
    chunk = "chunk"


class ChunkType(str, Enum):
    header = "header"
    statement = "statement"
    solution = "solution"
    context = "context"


class Priority(str, Enum):
    p0 = "P0"
    p1 = "P1"
    p2 = "P2"


# ============================================================================
# 2. SOURCE & ARCHIVE TRACKING
# ============================================================================

class ArchiveFamily(BaseModel):
    """
    Top-level competition archive collection (e.g. all AMC10 exams ever).
    Sourced from archive_family_registry.csv.
    """
    model_config = {"json_schema_extra": {"example": {
        "archive_record_id": "AF_AMC10",
        "competition_id": "AMC10",
        "years": "2000-2024",
        "canonical_archive_url": "https://artofproblemsolving.com/wiki/index.php/AMC_10_Problems_and_Solutions",
        "problem_availability": "COMPLETE",
        "solution_availability": "COMPLETE",
        "archive_index_status": "INDEXED",
    }}}

    archive_record_id: str = Field(..., description="Stable PK, e.g. AF_AMC10")
    competition_id: str = Field(..., description="FK to Competition.competition_id")
    years: str = Field("", description="Year range covered, e.g. '2000-2024'")
    division_or_format: str = Field("", description="A/B form split, division tier, etc.")
    round_set: str = Field("", description="Comma-separated rounds in this archive, e.g. 'I,II'")
    canonical_archive_url: str = Field("", description="Stable AoPS or official index URL")
    problem_availability: str = Field("", description="COMPLETE | PARTIAL | MISSING")
    solution_availability: str = Field("", description="COMPLETE | PARTIAL | MISSING")
    stable_id_pattern: str = Field("", description="Regex describing canonical question ID pattern")
    archive_index_status: IngestionStatus = Field(IngestionStatus.pending,
        description="Has the archive index been crawled and enumerated?")
    question_level_status: IngestionStatus = Field(IngestionStatus.pending,
        description="Have individual question pages been crawled?")
    taxonomy_status: ClassificationStatus = Field(ClassificationStatus.unclassified,
        description="Overall taxonomy classification status for this archive")
    last_refresh: date | None = Field(None, description="Date archive was last re-crawled")
    notes: str = ""
    next_level_registry: str = Field("", description="Child registry collection name")
    event_registry_status: IngestionStatus = Field(IngestionStatus.pending,
        description="Status of the tournament-event-level registry beneath this archive")
    hierarchy_level: HierarchyLevel = Field(HierarchyLevel.archive_family,
        description="Position in the ingestion hierarchy")
    agent_traversal_rule: AgentTraversalRule = Field(AgentTraversalRule.expand_children,
        description="How the ingestion agent should traverse this node")

    def firestore_doc_id(self) -> str:
        return self.archive_record_id


class TournamentEvent(BaseModel):
    """
    One year/season of a competition (e.g. AMC10A 2023).
    Sits between ArchiveFamily and Paper in the hierarchy.
    Sourced from tournament_archive_registry.csv.
    """
    model_config = {"json_schema_extra": {"example": {
        "tournament_event_id": "TE_AMC10A_2023",
        "archive_family_id": "AF_AMC10",
        "competition_id": "AMC10",
        "year": 2023,
        "event_or_season": "2023",
        "event_status": "COMPLETE",
        "paper_count": 1,
        "question_index_status": "INDEXED",
    }}}

    tournament_event_id: str = Field(..., description="PK, e.g. TE_AMC10A_2023")
    archive_family_id: str = Field(..., description="FK to ArchiveFamily.archive_record_id")
    competition_id: str = Field(..., description="FK to Competition.competition_id")
    year: int | None = Field(None, description="Numeric year of the event")
    event_or_season: str = Field("", description="Season label, e.g. '2022-23' for HMMT")
    event_status: str = Field("", description="COMPLETE | PARTIAL | PLANNED")
    year_or_event_page_url: str = Field("", description="URL to the index page for this event year")
    parent_archive_url: str = Field("", description="URL of the parent archive family page")
    paper_count: int = Field(0, description="Number of papers (tests) in this event")
    problem_linked_papers: int = Field(0, description="Papers with confirmed problem URLs")
    solution_linked_papers: int = Field(0, description="Papers with confirmed solution URLs")
    round_set: str = Field("", description="Rounds in this event, e.g. 'AMC10A,AMC10B'")
    question_index_status: IngestionStatus = Field(IngestionStatus.pending,
        description="Question-level indexing status")
    taxonomy_status: ClassificationStatus = Field(ClassificationStatus.unclassified)
    source_resolution_status: str = Field("",
        description="RESOLVED | PARTIAL | UNRESOLVED — all source URLs confirmed?")
    agent_next_action: str = Field("", description="Free-text next action for the ingestion agent")
    notes: str = ""
    last_refresh: date | None = None
    hierarchy_level: HierarchyLevel = Field(HierarchyLevel.tournament_event)
    agent_traversal_rule: AgentTraversalRule = Field(AgentTraversalRule.expand_children)

    def firestore_doc_id(self) -> str:
        return self.tournament_event_id


class SourceIngestionRecord(BaseModel):
    """
    Tracks the web-crawl and parse lifecycle for one source URL.
    Sourced from source_ingestion_queue.csv.
    Maps to pipeline stages: CRAWL → PARSE → EXTRACT → CLASSIFY → EMBED.
    """
    model_config = {"json_schema_extra": {"example": {
        "source_id": "SRC_AMC10A_2023",
        "competition_id": "AMC10",
        "source_type": "aops_wiki",
        "canonical_source_url": "https://artofproblemsolving.com/wiki/index.php/2023_AMC_10A_Problems",
        "scope": "AMC10A_2023",
        "question_index_status": "INDEXED",
        "solution_classification_status": "CLASSIFIED",
        "rag_summary_status": "EMBEDDED",
        "copyright_rule": "fair_use",
    }}}

    source_id: str = Field(..., description="PK, e.g. SRC_AMC10A_2023")
    competition_id: str = Field(..., description="FK to Competition.competition_id")
    source_type: SourceType = Field(SourceType.unknown,
        description="aops_wiki | official_site | pdf | html | archive_org")
    canonical_source_url: str = Field("", description="Stable canonical URL for this source")
    scope: str = Field("", description="Test/round scope this source covers, e.g. 'AMC10A_2023'")
    crawl_status: IngestionStatus = Field(IngestionStatus.pending,
        description="Stage 1 — URL fetched and raw HTML/PDF saved locally")
    parse_status: IngestionStatus = Field(IngestionStatus.pending,
        description="Stage 2 — Question text extracted from raw source artifact")
    question_index_status: IngestionStatus = Field(IngestionStatus.pending,
        description="Stage 3 — Individual question rows written to Question Index")
    solution_classification_status: IngestionStatus = Field(IngestionStatus.pending,
        description="Stage 4 — Taxonomy and technique mapping completed")
    rag_summary_status: IngestionStatus = Field(IngestionStatus.pending,
        description="Stage 5 — Chunks embedded and written to vector index")
    last_crawled: datetime | None = Field(None, description="Timestamp of most recent crawl attempt")
    next_action: str = Field("", description="Agent next-action instruction")
    copyright_rule: CopyrightRule = Field(CopyrightRule.unknown,
        description="Copyright disposition for this source")
    notes: str = ""

    def firestore_doc_id(self) -> str:
        return self.source_id


# ============================================================================
# 3. CORE CORPUS ENTITIES
# ============================================================================

class Course(BaseModel):
    """
    A student study track grouping competitions (e.g. 'AMC10 Preparation').
    Top-level scoping key — course_id threads through every downstream entity.
    """
    model_config = {"json_schema_extra": {"example": {
        "course_id": "COURSE_AMC10_PREP",
        "display_name": "AMC 10 Preparation",
        "description": "Full AMC10 problem bank with taxonomy and worked solutions",
        "level": "high_school",
        "competition_ids": ["AMC10"],
    }}}

    course_id: str = Field(..., description="PK, e.g. COURSE_AMC10_PREP")
    display_name: str = Field(..., description="Human-readable course name")
    description: str = Field("", description="Short description of course scope and goals")
    level: EducationLevel = Field(..., description="Target student level")
    competition_ids: list[str] = Field(default_factory=list,
        description="Competitions included in this course")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc),
        description="ISO timestamp when course was created")

    def firestore_doc_id(self) -> str:
        return self.course_id


class Competition(BaseModel):
    """
    Named math competition series. Sourced from competition_catalog.csv.
    """
    model_config = {"json_schema_extra": {"example": {
        "competition_id": "AMC10",
        "display_name": "AMC 10",
        "organizer": "Mathematical Association of America",
        "competition_type": "individual",
        "level": "high_school",
        "canonical_archive_url": "https://artofproblemsolving.com/wiki/index.php/AMC_10",
        "taxonomy_mode": "FINE",
    }}}

    competition_id: str = Field(..., description="PK, e.g. AMC10, AIME, HMMT")
    course_ids: list[str] = Field(default_factory=list,
        description="Courses that include this competition")
    display_name: str = Field(..., description="Full human-readable name")
    organizer: str = Field("", description="Sponsoring organisation, e.g. 'MAA'")
    competition_type: CompetitionType = Field(..., description="individual | team | relay")
    level: EducationLevel = Field(..., description="middle | high_school | open")
    canonical_archive_url: str = Field("",
        description="Stable index URL for the full competition archive")
    typical_structure: str = Field("",
        description="Test structure description, e.g. '30 MCQ, 75 min'")
    taxonomy_mode: str = Field("",
        description="FINE (concept+technique) | TOPIC (topic only) | NONE")
    event_or_round: str = Field("",
        description="Default event/round label e.g. 'I,II' for two-form competitions")
    archive_from: int | None = Field(None, description="Earliest year in archive")
    archive_through: int | None = Field(None, description="Latest year in archive")
    question_format: str = Field("", description="MCQ | Free-response | Mixed")
    notes: str = ""

    def firestore_doc_id(self) -> str:
        return self.competition_id


class ExamEntry(BaseModel):
    """
    One specific test sitting with attempt tracking and link resolution.
    Sourced from test_registry.csv.
    """
    model_config = {"json_schema_extra": {"example": {
        "test_id": "AMC10A_2023",
        "competition_id": "AMC10",
        "exam_level": "AMC10",
        "year": 2023,
        "form": "A",
        "session": "November",
        "aops_test_url": "https://artofproblemsolving.com/wiki/index.php/2023_AMC_10A_Problems",
        "question_count": 30,
        "link_status": "VALID",
        "parsing_batch_eligibility": "ELIGIBLE",
    }}}

    test_id: str = Field(..., description="PK, e.g. AMC10A_2023")
    competition_id: str = Field(..., description="FK to Competition.competition_id")
    course_id: str = Field("", description="FK to Course.course_id")
    exam_level: str = Field("", description="Exam level label, e.g. AMC10, AIME, HMMT-Feb")
    year: int | None = Field(None, description="Year of the test sitting")
    form: str = Field("", description="Form/variant: A, B, I, II, etc.")
    session: str = Field("", description="Session: November, February, Annual, etc.")
    aops_test_url: str = Field("", description="AoPS wiki page for this test")
    direct_problem_url: str = Field("", description="Direct URL to problem PDF or page")
    direct_solution_url: str = Field("", description="Direct URL to solution PDF or page")
    question_count: int = Field(0, description="Official question count for this test")
    registered_question_count: int = Field(0,
        description="Questions actually registered in Question Index")
    taxonomy_mapping_row_count: int = Field(0,
        description="Total taxonomy mapping rows for this test")
    taxonomy_distinct_question_count: int = Field(0,
        description="Distinct questions with at least one taxonomy mapping")
    fine_mapped_question_count: int = Field(0,
        description="Questions with fine-concept-level mapping")
    attempt_status: str = Field("", description="NOT_ATTEMPTED | IN_PROGRESS | COMPLETE")
    latest_attempt_id: str = Field("", description="FK to latest attempt artifact")
    latest_score: str = Field("", description="Score on latest attempt, e.g. '25/30'")
    latest_attempt_date: date | None = Field(None, description="Date of latest attempt")
    full_test_artifact_url: str = Field("",
        description="Drive URL to the full test attempt artifact")
    latest_ai_review_id: str = Field("", description="FK to latest AI review artifact")
    link_status: LinkStatus = Field(LinkStatus.unknown,
        description="VALID | BROKEN | REDIRECTED | ARCHIVE_ONLY")
    link_type: str = Field("", description="GRANULAR | PAGE | ARCHIVE")
    registry_coverage_status: str = Field("",
        description="COMPLETE | PARTIAL | NONE")
    taxonomy_completion_status: ClassificationStatus = Field(ClassificationStatus.unclassified)
    parsing_batch_eligibility: str = Field("",
        description="ELIGIBLE | SKIP_COMPLETE | NEEDS_REVIEW")
    source_id: str = Field("", description="FK to SourceIngestionRecord.source_id")
    paper_id: str = Field("", description="FK to Paper.paper_id")
    tournament_event_id: str = Field("", description="FK to TournamentEvent.tournament_event_id")
    agent_next_action: str = Field("", description="Free-text next action for ingestion agent")
    notes: str = ""

    def firestore_doc_id(self) -> str:
        return self.test_id


class Paper(BaseModel):
    """
    One sitting of a competition as a parsed artifact with source URLs.
    Sourced from paper_registry.csv.
    """
    model_config = {"json_schema_extra": {"example": {
        "paper_id": "PAPER_AMC10A_2023",
        "course_id": "COURSE_AMC10_PREP",
        "test_id": "AMC10A_2023",
        "competition_id": "AMC10",
        "year": 2023,
        "form_or_round": "A",
        "problem_url": "https://artofproblemsolving.com/wiki/index.php/2023_AMC_10A_Problems",
        "question_count": 30,
        "link_status": "VALID",
        "question_index_status": "INDEXED",
    }}}

    paper_id: str = Field(..., description="PK, e.g. PAPER_AMC10A_2023")
    course_id: str = Field(..., description="FK to Course.course_id")
    test_id: str = Field(..., description="FK to TestRegistryEntry.test_id")
    competition_id: str = Field(..., description="FK to Competition.competition_id")
    tournament_event_id: str = Field("", description="FK to TournamentEvent.tournament_event_id")
    year: int | None = Field(None, description="Year of this paper sitting")
    year_or_years: str = Field("", description="Raw year or year-range string from source")
    form_or_round: str = Field("", description="A, B, I, II, Fall, Spring, Team, etc.")
    session: str = Field("", description="Annual | February | November")
    problem_url: str = Field("", description="Primary problem source URL")
    solution_url: str = Field("", description="Primary solution source URL")
    year_or_event_page_url: str = Field("",
        description="URL to the year-index or event page (parent of this paper)")
    link_status: LinkStatus = Field(LinkStatus.unknown)
    link_scope: str = Field("",
        description="GRANULAR (per-question) | PAGE (whole paper) | ARCHIVE")
    question_count: int = Field(0, description="Official expected question count")
    question_index_status: IngestionStatus = Field(IngestionStatus.pending)
    taxonomy_status: ClassificationStatus = Field(ClassificationStatus.unclassified)
    technique_status: ClassificationStatus = Field(ClassificationStatus.unclassified)
    canonical_row_status: str = Field("",
        description="CANONICAL | DUPLICATE | NEEDS_MERGE")
    source_record: str = Field("", description="Provenance note (source tab + row)")
    problem_sha256: str | None = Field(None, description="SHA256 of downloaded problem artifact")
    solution_sha256: str | None = Field(None, description="SHA256 of downloaded solution artifact")
    last_refresh: date | None = Field(None, description="Date metadata was last refreshed")
    next_action: str = Field("", description="Agent next-action instruction")
    hierarchy_level: HierarchyLevel = Field(HierarchyLevel.paper)
    agent_traversal_rule: AgentTraversalRule = Field(AgentTraversalRule.direct_index)
    source_tab: str = Field("", description="Spreadsheet tab this row was imported from")
    source_row: int | None = Field(None, description="Row index within source tab")
    notes: str = ""

    def firestore_doc_id(self) -> str:
        return self.paper_id


class Question(BaseModel):
    """
    One question from one paper, with taxonomy, attempt, and classification metadata.
    Sourced from question_index.csv.
    """
    model_config = {"json_schema_extra": {"example": {
        "question_id": "AMC10A_2023_Q05",
        "course_id": "COURSE_AMC10_PREP",
        "paper_id": "PAPER_AMC10A_2023",
        "competition_id": "AMC10",
        "year": 2023,
        "q_number": 5,
        "primary_topic": "Probability",
        "subtopic": "Conditional Probability",
        "difficulty_band": "medium",
        "correct_answer": "C",
        "classification_status": "FINE_COMPLETE",
    }}}

    question_id: str = Field(..., description="PK, e.g. AMC10A_2023_Q05")
    course_id: str = Field(..., description="FK to Course.course_id — inherited from paper")
    paper_id: str = Field(..., description="FK to Paper.paper_id")
    competition_id: str = Field("", description="Denormalised for efficient Firestore queries")
    tournament_event_id: str = Field("", description="FK to TournamentEvent.tournament_event_id")
    test_id: str = Field("", description="FK to TestRegistryEntry.test_id")
    year: int | None = Field(None, description="Year of the paper this question appears in")
    exam_level: str = Field("", description="AMC10 | AMC12 | AIME | HMMT-Feb | etc.")
    form: str = Field("", description="A | B | I | II | etc.")
    session: str = Field("", description="November | February | Annual")
    q_number: int = Field(..., description="1-based question number within the paper")
    primary_topic: str = Field("", description="Algebra | Geometry | Probability | etc.")
    subtopic: str = Field("", description="Narrower classification within primary topic")
    technique: str = Field("", description="Primary technique name as a short label")
    primary_concept_id: str = Field("", description="FK to Concept.canonical_topic_id")
    concept_ids: list[str] = Field(default_factory=list,
        description="All taxonomy concept IDs assigned to this question")
    technique_ids: list[str] = Field(default_factory=list,
        description="FK list to Technique.technique_id")
    difficulty_band: DifficultyBand | None = Field(None,
        description="easy | medium | hard | very_hard | entry | core | advanced | elite")
    correct_answer: str = Field("", description="Official answer: letter for MCQ, integer for AIME")
    aops_question_url: str = Field("", description="AoPS wiki URL for this specific question")
    direct_problem_url: str = Field("", description="Direct problem PDF or page URL")
    direct_solution_url: str = Field("", description="Direct solution PDF or page URL")
    granular_link_status: LinkStatus = Field(LinkStatus.unknown,
        description="Link resolution status at the individual question level")
    year_or_event_page_url: str = Field("", description="Parent year/event index page URL")
    # Attempt tracking
    latest_student_answer: str = Field("", description="Most recent answer given by the student")
    latest_result: AttemptResult | None = Field(None,
        description="CORRECT | INCORRECT | PARTIAL | SKIPPED")
    latest_confidence: Confidence | None = Field(None,
        description="Student self-reported confidence on latest attempt")
    latest_time_sec: int | None = Field(None, description="Time taken on latest attempt in seconds")
    latest_work_artifact_url: str = Field("", description="Drive URL to latest written work artifact")
    latest_error_id: str = Field("", description="FK to error journal entry for latest incorrect attempt")
    retest_status: str = Field("", description="NEEDS_RETEST | PASSED_RETEST | NOT_REQUIRED")
    # Classification metadata
    classification_status: ClassificationStatus = Field(ClassificationStatus.unclassified)
    taxonomy_evidence_status: str = Field("",
        description="SOLUTION_REVIEWED | FEATURE_MD | AGENT_INFERRED | UNREVIEWED")
    taxonomy_mapping_count: int = Field(0, description="Total concept mapping rows for this question")
    distinct_concept_id_count: int = Field(0, description="Count of distinct concept IDs mapped")
    high_confidence_mapping_count: int = Field(0, description="Count of high-confidence concept mappings")
    technique_mapping_count: int = Field(0, description="Count of technique mappings")
    fine_concept_mapping_count: int = Field(0, description="Count of Concept/Subtopic-level mappings")
    # Visual evidence
    visual_role: str = Field("none",
        description="none | geometry_diagram | graph | table | combinatorial_figure | illustration")
    visual_asset_ids: list[str] = Field(default_factory=list,
        description="Stable asset IDs of referenced visual evidence files")
    visual_feature_summary: str = Field("",
        description="Compact structural description of what the figure contributes")
    visual_evidence_locator: str = Field("",
        description="Source/page/figure reference for the visual asset")
    evidence_locator: str = Field("", description="Page/figure reference used as classification evidence")
    notes: str = ""

    @field_validator("concept_ids", "technique_ids", "visual_asset_ids", mode="before")
    @classmethod
    def _split_semicolon(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [x.strip() for x in v.split(";") if x.strip()]
        return v or []

    def firestore_doc_id(self) -> str:
        return self.question_id


# ============================================================================
# 4. TAXONOMY & TECHNIQUES
# ============================================================================

class Concept(BaseModel):
    """
    Canonical taxonomy node. Sourced from canonical_topic_hierarchy.csv.
    New categories = new rows; no schema migration required.
    """
    model_config = {"json_schema_extra": {"example": {
        "canonical_topic_id": "PROB_COND",
        "domain": "Probability",
        "topic": "Conditional Probability",
        "node_type": "Concept",
        "parent_id": "PROB",
        "canonical_path": "Probability/Conditional Probability",
        "definition": "Probability of event A given event B has occurred.",
        "amc10": True,
        "amc12": True,
        "aime": True,
    }}}

    canonical_topic_id: str = Field(..., description="PK, e.g. PROB_COND")
    course_ids: list[str] = Field(default_factory=list,
        description="Courses referencing this concept (derived at index time)")
    domain: str = Field("", description="Algebra | Geometry | Number Theory | Probability | etc.")
    topic: str = Field("", description="Mid-level topic within the domain")
    subtopic: str = Field("", description="Optional finer split within the topic")
    concept_or_technique: str = Field("", description="Leaf-level name as used in problem analysis")
    node_type: TaxonomyNodeType = Field(TaxonomyNodeType.concept,
        description="Domain | Topic | Concept | Subtopic | Technique")
    parent_id: str = Field("", description="FK to parent Concept.canonical_topic_id")
    canonical_path: str = Field("",
        description="Slash-delimited full path, e.g. 'Probability/Conditional Probability'")
    definition: str = Field("", description="Plain-English definition of this concept")
    synonyms: str = Field("", description="Semicolon-separated synonym labels")
    related_nodes: str = Field("", description="Semicolon-separated related canonical_topic_ids")
    # Competition presence flags
    amc10: bool = Field(False, description="Appears in AMC10 problems")
    amc12: bool = Field(False, description="Appears in AMC12 problems")
    aime: bool = Field(False, description="Appears in AIME problems")
    mpg: bool = Field(False, description="Appears in MathPrize for Girls problems")
    hmmt: bool = Field(False, description="Appears in HMMT problems")
    smt: bool = Field(False, description="Appears in SMT problems")
    pumac: bool = Field(False, description="Appears in PUMaC problems")
    cmm: bool = Field(False, description="Appears in CMM problems")
    chmmc: bool = Field(False, description="Appears in CHMMC problems")

    def firestore_doc_id(self) -> str:
        return self.canonical_topic_id


class TopicAlias(BaseModel):
    """
    Alternative names that resolve to a canonical concept.
    Sourced from topic_alias_index.csv.
    Used by the RAG query router to normalise free-text topic queries.
    """
    model_config = {"json_schema_extra": {"example": {
        "alias": "conditional probability",
        "normalized_alias": "conditional probability",
        "canonical_topic_id": "PROB_COND",
        "canonical_path": "Probability/Conditional Probability",
        "alias_type": "SYNONYM",
        "priority": 1,
    }}}

    alias: str = Field(..., description="Raw alias string as it might appear in a user query")
    normalized_alias: str = Field("", description="Lowercased, whitespace-normalised alias")
    canonical_topic_id: str = Field(..., description="FK to Concept.canonical_topic_id")
    canonical_path: str = Field("", description="Slash-delimited path of the canonical concept")
    alias_type: str = Field("", description="SYNONYM | ABBREVIATION | COLLOQUIAL | LEGACY")
    priority: int = Field(0,
        description="Disambiguation priority when multiple concepts match (higher = prefer)")
    notes: str = ""

    def firestore_doc_id(self) -> str:
        import re
        return re.sub(r"[^a-z0-9_]", "_", (self.normalized_alias or self.alias).lower())


class Technique(BaseModel):
    """
    Fine-grained solution technique cross-referenced to a parent concept.
    Sourced from technique_catalog.csv.
    """
    model_config = {"json_schema_extra": {"example": {
        "technique_id": "TECH_CASEWORK",
        "parent_concept_id": "COMB",
        "technique_name": "Casework",
        "canonical_path": "Combinatorics/Casework",
        "definition": "Enumerate all disjoint cases and sum their counts.",
        "recognition_signals": "phrases like 'how many ways', distinct case boundaries",
        "primary_or_secondary": "PRIMARY",
    }}}

    technique_id: str = Field(..., description="PK, e.g. TECH_CASEWORK")
    course_ids: list[str] = Field(default_factory=list,
        description="Courses referencing this technique (derived at index time)")
    parent_concept_id: str = Field("",
        description="FK to Concept.canonical_topic_id this technique belongs to")
    technique_name: str = Field(..., description="Human-readable technique name")
    canonical_path: str = Field("", description="Full slash-delimited taxonomy path")
    definition: str = Field("", description="Plain-English definition of the technique")
    recognition_signals: str = Field("",
        description="How to spot this technique in a problem statement or solution")
    algebraic_signature: str = Field("",
        description="Characteristic algebraic or formula pattern, if any")
    aliases: str = Field("", description="Semicolon-separated alternative names")
    related_techniques: str = Field("",
        description="Semicolon-separated related Technique.technique_ids")
    can_cooccur: str = Field("",
        description="Semicolon-separated techniques that commonly co-occur")
    primary_or_secondary: str = Field("",
        description="PRIMARY (main method) | SECONDARY (supporting step)")
    evidence_standard: str = Field("",
        description="What evidence is required before this tag is applied")
    agent_search_terms: str = Field("",
        description="Semicolon-separated keywords the agent uses to detect this technique")
    notes: str = ""

    def firestore_doc_id(self) -> str:
        return self.technique_id


class QuestionTaxonomyMap(BaseModel):
    """
    Many-to-many mapping between a question and taxonomy concept nodes.
    Sourced from question_taxonomy_map.csv and questions_by_taxonomy.csv.
    """
    model_config = {"json_schema_extra": {"example": {
        "mapping_id": "MAP_PROB_COND_AMC10A_2023_Q05_FEATUREMD_V1",
        "question_id": "AMC10A_2023_Q05",
        "concept_id": "PROB_COND",
        "association_type": "Primary Concept",
        "confidence": "high",
        "evidence_source": "Validated feature MD from official problem/solution",
    }}}

    mapping_id: str = Field(...,
        description="PK, deterministic format MAP_<concept>_<question>_<source>_<version>")
    question_id: str = Field(..., description="FK to Question.question_id")
    test_id: str = Field("", description="Denormalised FK to TestRegistryEntry.test_id")
    exam_level: str = Field("", description="Denormalised exam level label")
    domain: str = Field("", description="Denormalised domain of the mapped concept")
    concept_id: str = Field(..., description="FK to Concept.canonical_topic_id")
    concept: str = Field("", description="Denormalised concept name")
    concept_type: str = Field("", description="Denormalised node type")
    canonical_node_type: TaxonomyNodeType | None = Field(None,
        description="Node type of the mapped concept")
    canonical_path: str = Field("", description="Slash-delimited path of the mapped concept")
    solution_id: str = Field("", description="Source artifact ID this mapping was derived from")
    association_type: AssociationType = Field(AssociationType.primary_concept)
    evidence_source: str = Field("",
        description="Validated feature MD | Manual | Agent inferred | Solution reviewed")
    evidence_url: str = Field("", description="URL of the evidence document")
    confidence: Confidence = Field(Confidence.medium)
    notes: str = ""
    canonical_paper_id: str = Field("", description="FK to Paper.paper_id")
    direct_problem_url: str = ""
    direct_solution_url: str = ""
    canonical_evidence_url: str = Field("",
        description="Best available evidence URL (solution preferred over problem)")
    tournament_event_id: str = ""

    def firestore_doc_id(self) -> str:
        return self.mapping_id


class QuestionTechniqueMap(BaseModel):
    """
    Many-to-many mapping between a question and a solution technique.
    Sourced from question_technique_map.csv.
    """
    model_config = {"json_schema_extra": {"example": {
        "technique_map_id": "TMAP_AMC10A_2023_Q05_TECH_CASEWORK_FEATUREMD_V1",
        "question_id": "AMC10A_2023_Q05",
        "technique_id": "TECH_CASEWORK",
        "role": "Solution-reviewed",
        "evidence_confidence": "high",
        "classification_status": "SOLUTION_REVIEWED",
    }}}

    technique_map_id: str = Field(...,
        description="PK, deterministic format TMAP_<question>_<technique>_<source>_<version>")
    question_id: str = Field(..., description="FK to Question.question_id")
    parent_concept_id: str = Field("", description="FK to the concept this technique belongs to")
    technique_id: str = Field(..., description="FK to Technique.technique_id")
    technique_name: str = Field("", description="Denormalised technique name")
    role: str = Field("", description="Solution-reviewed | Agent-inferred | Manual")
    solution_id: str = Field("", description="Source artifact ID this mapping was derived from")
    competition_id: str = ""
    year: int | None = None
    form_round: str = ""
    problem_number: int | None = Field(None, description="Denormalised question number")
    evidence_source: str = Field("", description="How mapping was established")
    evidence_url: str = Field("", description="URL of evidence document")
    evidence_confidence: Confidence = Field(Confidence.medium)
    evidence_snippet_or_reason: str = Field("",
        description="Short text quote or reasoning supporting the tag")
    classification_status: ClassificationStatus = Field(ClassificationStatus.unclassified)
    last_reviewed: date | None = Field(None, description="Date mapping was last reviewed")
    notes: str = ""
    canonical_paper_id: str = ""
    direct_problem_url: str = ""
    direct_solution_url: str = ""
    canonical_evidence_url: str = ""
    tournament_event_id: str = ""

    def firestore_doc_id(self) -> str:
        return self.technique_map_id


# ============================================================================
# 5. KNOWLEDGE GRAPH
# ============================================================================

class KnowledgeGraphEdge(BaseModel):
    """
    Directed edge between any two corpus entities.
    Sourced from knowledge_graph_edges.csv.
    Enables prerequisite chains, co-occurrence, and specialisation graphs.
    """
    model_config = {"json_schema_extra": {"example": {
        "edge_id": "EDGE_PROB_COND_PROB_BASIC_PREREQUISITE",
        "from_type": "Concept",
        "from_id": "PROB_COND",
        "edge_type": "PREREQUISITE",
        "to_type": "Concept",
        "to_id": "PROB_BASIC",
        "weight": 0.9,
        "confidence": "high",
    }}}

    edge_id: str = Field(..., description="PK, deterministic slug")
    from_type: str = Field(...,
        description="Source entity type: Concept | Technique | Question | Paper")
    from_id: str = Field(..., description="ID of the source entity")
    edge_type: str = Field(...,
        description="PREREQUISITE | COAPPLIED | SPECIALIZES | GENERALIZES | RELATED | IMPLIES")
    to_type: str = Field(..., description="Target entity type")
    to_id: str = Field(..., description="ID of the target entity")
    weight: float = Field(1.0,
        description="Strength of the relationship 0–1, used for curriculum ordering")
    evidence_type: str = Field("",
        description="MANUAL | AGENT_INFERRED | CO_OCCURRENCE | SOLUTION_REVIEWED")
    evidence_id: str = Field("", description="FK to source evidence artifact")
    evidence_url: str = Field("", description="URL of evidence document")
    confidence: Confidence = Field(Confidence.medium)
    student_specific: bool = Field(False,
        description="True if this edge was personalised for a specific student profile")
    valid_from: date | None = Field(None, description="Edge validity start date")
    valid_to: date | None = Field(None, description="Edge validity end date (None = current)")
    notes: str = ""

    def firestore_doc_id(self) -> str:
        return self.edge_id


# ============================================================================
# 6. PIPELINE QUEUES & TASK TRACKING
# ============================================================================

class UnparsedPaperQueueItem(BaseModel):
    """
    A paper awaiting question-text extraction.
    Sourced from unparsed_paper_queue.csv.
    Feeds Stage PARSE of the ingestion pipeline.
    """
    model_config = {"json_schema_extra": {"example": {
        "paper_id": "PAPER_HMMT_FEB_2023_TEAM",
        "competition_id": "HMMT",
        "year": 2023,
        "test_or_round": "Team",
        "question_count": 10,
        "question_index_status": "PENDING",
        "priority": "P1",
        "agent_next_action": "CRAWL_AND_PARSE",
    }}}

    paper_id: str = Field(..., description="FK to Paper.paper_id")
    tournament_event_id: str = Field("", description="FK to TournamentEvent.tournament_event_id")
    competition_id: str = Field("", description="FK to Competition.competition_id")
    year: int | None = None
    test_or_round: str = ""
    problem_url: str = Field("", description="Problem source URL to crawl and parse")
    solution_url: str = ""
    question_count: int = Field(0, description="Expected question count")
    question_index_status: IngestionStatus = Field(IngestionStatus.pending)
    taxonomy_status: ClassificationStatus = Field(ClassificationStatus.unclassified)
    link_status: LinkStatus = Field(LinkStatus.unknown)
    year_or_event_page_url: str = ""
    priority: Priority = Field(Priority.p1)
    agent_next_action: str = Field("", description="Next pipeline action instruction")
    last_refresh: date | None = None


class UnmappedQuestionQueueItem(BaseModel):
    """
    A question with no taxonomy concept mapping yet.
    Sourced from unmapped_question_queue.csv.
    Feeds Stage CLASSIFY of the ingestion pipeline.
    """
    model_config = {"json_schema_extra": {"example": {
        "question_id": "SMT_2022_TEAM_Q03",
        "exam_level": "SMT",
        "suggested_domain": "Algebra",
        "mapping_status": "PENDING",
        "priority": "P1",
    }}}

    question_id: str = Field(..., description="FK to Question.question_id")
    test_id: str = ""
    exam_level: str = ""
    year: int | None = None
    form: str = ""
    session: str = ""
    q_number: int | None = None
    problem_url: str = ""
    suggested_domain: str = Field("", description="Agent-inferred domain before full classification")
    inference_basis: str = Field("", description="Evidence behind the suggested domain")
    suggested_confidence: Confidence = Field(Confidence.low)
    mapping_status: IngestionStatus = Field(IngestionStatus.pending)
    priority: Priority = Field(Priority.p1)
    next_action: str = ""
    notes: str = ""


class FineConceptGapItem(BaseModel):
    """
    A question mapped to topics but lacking fine Concept/Subtopic tags.
    Sourced from fine_concept_gap_queue.csv.
    Targets the gap between PARTIAL and FINE_COMPLETE classification.
    """
    model_config = {"json_schema_extra": {"example": {
        "question_id": "AMC10A_2021_Q18",
        "exam_level": "AMC10",
        "classification_status": "PARTIAL",
        "fine_concept_mapping_count": 0,
        "priority": "P0",
        "agent_next_action": "REVIEW_SOLUTION_AND_MAP_FINE_CONCEPT",
    }}}

    question_id: str = Field(..., description="FK to Question.question_id")
    test_id: str = ""
    exam_level: str = ""
    year: int | None = None
    form: str = ""
    session: str = ""
    q_number: int | None = None
    paper_id: str = ""
    tournament_event_id: str = ""
    direct_problem_url: str = ""
    direct_solution_url: str = ""
    taxonomy_mapping_count: int = Field(0, description="Total concept mapping rows for this question")
    fine_concept_mapping_count: int = Field(0,
        description="Concept/Subtopic-level mapping count — target is > 0")
    classification_status: ClassificationStatus = Field(ClassificationStatus.partial)
    taxonomy_evidence_status: str = Field("",
        description="SOLUTION_REVIEWED | FEATURE_MD | AGENT_INFERRED | UNREVIEWED")
    priority: Priority = Field(Priority.p1)
    agent_next_action: str = Field("",
        description="e.g. REVIEW_SOLUTION_AND_MAP_FINE_CONCEPT | NEEDS_HUMAN_REVIEW")


class ParseBatchItem(BaseModel):
    """
    One paper slot within a 10-paper parsing batch.
    Sourced from parsing_batch_queue.csv.
    Controls the prepare → validate → upload → sync pipeline cycle.
    """
    model_config = {"json_schema_extra": {"example": {
        "batch_id": "COLLEGE_BATCH_001",
        "slot": 1,
        "unit_id": "PAPER_AMC10A_2023",
        "test_id": "AMC10A_2023",
        "scope": "AMC10",
        "expected_questions": 30,
        "current_status": "PREPARED",
        "eligibility": "ELIGIBLE",
        "agent_action": "VALIDATE",
    }}}

    batch_id: str = Field(..., description="Batch identifier, e.g. COLLEGE_BATCH_001")
    slot: int = Field(..., description="1-based slot position within the batch")
    unit_id: str = Field("", description="FK to Paper.paper_id or unique unit identifier")
    test_id: str = Field("", description="FK to TestRegistryEntry.test_id")
    scope: str = Field("", description="Competition scope, e.g. AMC10 or HMMT")
    competition_id: str = ""
    year: str = Field("", description="Year as string (may be a range for multi-year papers)")
    form_or_round: str = ""
    expected_questions: int | None = None
    registered_questions: int | None = Field(None,
        description="Questions already registered in Question Index")
    fine_mapped_questions: int | None = Field(None,
        description="Questions with fine-concept mapping complete")
    problem_url: str | None = None
    solution_url: str | None = None
    current_status: str = Field("",
        description="PENDING | PREPARED | VALIDATED | UPLOADED | SYNCED | SKIP_COMPLETE | FAILED")
    eligibility: str = Field("", description="ELIGIBLE | SKIP_COMPLETE | NEEDS_REVIEW")
    priority: Priority = Field(Priority.p1)
    agent_action: str = Field("",
        description="PREPARE | VALIDATE | UPLOAD | SYNC | SKIP")

    def firestore_doc_id(self) -> str:
        return f"{self.batch_id}_S{self.slot:02d}"


class CorpusTask(BaseModel):
    """
    A tracked corpus-build or curation task.
    Sourced from corpus_task_tracker.csv.
    """
    model_config = {"json_schema_extra": {"example": {
        "task_id": "TASK_AMC10_TAXONOMY_2023",
        "workstream": "Taxonomy",
        "competition_scope": "AMC10",
        "task": "Map all 2023 AMC10A questions to fine concepts",
        "status": "IN_PROGRESS",
        "current_coverage": "18/30",
        "owner": "agent",
    }}}

    task_id: str = Field(..., description="PK")
    workstream: str = Field("",
        description="Taxonomy | Technique | Parse | RAG | Index | etc.")
    competition_scope: str = Field("", description="Competition or scope this task covers")
    task: str = Field("", description="Human-readable task description")
    status: TaskStatus = Field(TaskStatus.not_started)
    baseline: str = Field("", description="Starting coverage at task creation")
    current_coverage: str = Field("", description="Current metric, e.g. '18/30' or '60%'")
    last_action: str = Field("", description="Summary of last action taken")
    next_action: str = Field("", description="Next planned action")
    evidence_tab: str = Field("", description="Spreadsheet tab containing evidence")
    evidence_url: str = ""
    owner: str = Field("", description="agent | human | mixed")
    last_updated: date | None = None
    notes: str = ""

    def firestore_doc_id(self) -> str:
        return self.task_id


# ============================================================================
# 7. ANALYTICS & RETRIEVAL
# ============================================================================

class TopicCoverageMetric(BaseModel):
    """
    Coverage statistics for one concept across one competition.
    Sourced from topic_coverage_matrix.csv.
    Answers queries like 'How well-covered is Probability in AIME?'
    """
    model_config = {"json_schema_extra": {"example": {
        "canonical_topic_id": "PROB_COND",
        "canonical_path": "Probability/Conditional Probability",
        "competition_id": "AMC10",
        "indexed_question_count": 14,
        "high_confidence_count": 12,
        "coverage_status": "STRONG",
        "earliest_year": 2010,
        "latest_year": 2023,
    }}}

    canonical_topic_id: str = Field(..., description="FK to Concept.canonical_topic_id")
    canonical_path: str = Field("", description="Slash-delimited concept path")
    competition_id: str = Field(..., description="FK to Competition.competition_id")
    indexed_question_count: int = Field(0,
        description="Total questions mapped to this concept in this competition")
    solution_reviewed_count: int = Field(0,
        description="Questions with solution-reviewed mapping status")
    high_confidence_count: int = Field(0, description="Mappings tagged high confidence")
    medium_confidence_count: int = Field(0)
    low_confidence_count: int = Field(0)
    earliest_year: int | None = Field(None, description="Earliest year a mapping exists")
    latest_year: int | None = Field(None, description="Most recent year a mapping exists")
    coverage_status: str = Field("", description="STRONG | ADEQUATE | SPARSE | NONE")
    last_refresh: date | None = None
    missing_ranges: str = Field("",
        description="Year ranges with no mapped questions, e.g. '2015-2017'")
    notes: str = ""

    def firestore_doc_id(self) -> str:
        return f"{self.canonical_topic_id}__{self.competition_id}"


class DomainIndexedQuestion(BaseModel):
    """
    Shared model for domain-specific question–concept views.
    Sourced from combinatorics_indexed_questions.csv,
    geometry_indexed_questions.csv, number_theory_indexed_questions.csv,
    complex_numbers_indexed_questions.csv.
    The domain field distinguishes which topic view a row belongs to.
    """
    model_config = {"json_schema_extra": {"example": {
        "question_id": "AMC10A_2023_Q12",
        "test_id": "AMC10A_2023",
        "competition": "AMC10",
        "concept_id": "COMB_CASEWORK",
        "concept_or_technique": "Casework",
        "association_type": "Primary Concept",
        "confidence": "high",
        "source_link_level": "GRANULAR",
        "domain": "Combinatorics",
    }}}

    question_id: str = Field(..., description="FK to Question.question_id")
    test_id: str = Field("", description="FK to TestRegistryEntry.test_id")
    competition: str = Field("", description="Competition label (denormalised)")
    concept_id: str = Field("", description="FK to Concept.canonical_topic_id")
    concept_or_technique: str = Field("", description="Concept or technique name")
    solution_id: str = Field("", description="Artifact ID of the solution used as evidence")
    association_type: AssociationType = Field(AssociationType.primary_concept)
    evidence_source: str = Field("", description="Evidence source description")
    evidence_url: str = Field("", description="URL of evidence document")
    confidence: Confidence = Field(Confidence.medium)
    notes: str = ""
    canonical_paper_id: str = Field("", description="FK to Paper.paper_id")
    direct_problem_url: str = ""
    direct_solution_url: str = ""
    canonical_evidence_url: str = ""
    source_link_level: str = Field("",
        description="GRANULAR | PAGE | ARCHIVE — resolution level of the source link")
    canonical_node_type: TaxonomyNodeType | None = None
    canonical_path: str = ""
    tournament_event_id: str = ""
    domain: str = Field("",
        description="Domain this view covers: Combinatorics | Geometry | Number Theory | Complex Numbers")


class AIMEYearIndex(BaseModel):
    """
    Per-test metadata for AIME exams including difficulty-band question ranges.
    Sourced from aime_year_index.csv.
    """
    model_config = {"json_schema_extra": {"example": {
        "test_id": "AIME_I_2023",
        "year": 2023,
        "form": "I",
        "aops_test_url": "https://artofproblemsolving.com/wiki/index.php/2023_AIME_I_Problems",
        "question_count": 15,
        "index_status": "INDEXED",
    }}}

    test_id: str = Field(..., description="FK to TestRegistryEntry.test_id")
    year: int | None = Field(None, description="Year of the AIME")
    form: str = Field("", description="I or II")
    aops_test_url: str = Field("", description="AoPS page URL for this AIME")
    question_count: int = Field(15, description="Always 15 for AIME")
    entry_q1_5: str = Field("", description="Entry difficulty range label (Q1-5)")
    core_q6_9: str = Field("", description="Core difficulty range label (Q6-9)")
    advanced_q10_12: str = Field("", description="Advanced difficulty range label (Q10-12)")
    elite_q13_15: str = Field("", description="Elite difficulty range label (Q13-15)")
    question_id_prefix: str = Field("",
        description="Prefix for question IDs in this test, e.g. AIME_I_2023_Q")
    index_status: IngestionStatus = Field(IngestionStatus.pending,
        description="Question indexing status for this AIME year")
    topic_tag_status: ClassificationStatus = Field(ClassificationStatus.unclassified)

    def firestore_doc_id(self) -> str:
        return self.test_id


# ============================================================================
# 8. DOCUMENT STORAGE
# ============================================================================

class Document(BaseModel):
    """
    Canonical markdown artifact stored in GCS.
    Metadata only lives in Firestore; markdown content lives in Cloud Storage.
    """
    model_config = {"json_schema_extra": {"example": {
        "doc_id": "DOC_PAPER_AMC10A_2023",
        "course_id": "COURSE_AMC10_PREP",
        "entity_type": "paper",
        "entity_id": "PAPER_AMC10A_2023",
        "chunk_index": 0,
        "char_count": 18400,
        "gcs_uri": "gs://mathbank-corpus-docs/papers/PAPER_AMC10A_2023.md",
    }}}

    doc_id: str = Field(..., description="PK, deterministic slug")
    course_id: str = Field(..., description="FK to Course.course_id — inherited from parent entity")
    entity_type: EntityType = Field(..., description="paper | question | chunk")
    entity_id: str = Field(..., description="FK to Paper.paper_id or Question.question_id")
    chunk_index: int = Field(0,
        description="0 = whole document; 1+ = chunk sequence number within the document")
    char_count: int = Field(0, description="Character count of the markdown content")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc),
        description="SHA256 of content_md — used to skip unchanged uploads")
    gcs_uri: str = Field("",
        description="gs:// URI where the markdown file is stored in Cloud Storage")
    drive_file_id: str = Field("", description="Google Drive file ID of the mirrored artifact")
    drive_url: str = Field("", description="Google Drive webViewLink for human access")

    def firestore_doc_id(self) -> str:
        return self.doc_id


class Chunk(BaseModel):
    """
    A window of a document sized for vector embedding.
    Embedding vector stored in Vertex AI Vector Search, not Firestore.
    """
    model_config = {"json_schema_extra": {"example": {
        "chunk_id": "CHK_AMC10A_2023_Q05_STMT",
        "course_id": "COURSE_AMC10_PREP",
        "doc_id": "DOC_Q_AMC10A_2023_Q05",
        "question_id": "AMC10A_2023_Q05",
        "competition_id": "AMC10",
        "primary_topic": "Probability",
        "difficulty_band": "medium",
        "chunk_type": "statement",
        "token_count": 148,
        "embedding_model": "text-embedding-004",
    }}}

    chunk_id: str = Field(..., description="PK, deterministic slug")
    course_id: str = Field(...,
        description="FK to Course.course_id — inherited from parent document")
    doc_id: str = Field(..., description="FK to Document.doc_id")
    question_id: str | None = Field(None,
        description="FK to Question.question_id when chunk is question-scoped")
    competition_id: str = Field("",
        description="Denormalised for filter-before-search Firestore queries")
    primary_topic: str = Field("",
        description="Denormalised topic for filter-before-search queries")
    difficulty_band: DifficultyBand | None = Field(None,
        description="Denormalised difficulty for filter-before-search queries")
    chunk_type: ChunkType = Field(...,
        description="header | statement | solution | context")
    content: str = Field("",
        description="Plain text content of this chunk (also stored in GCS)")
    token_count: int = Field(0,
        description="Token count using the embedding model's tokeniser")
    embedding_model: str = Field("",
        description="Model used to produce the vector, e.g. text-embedding-004")
    content_hash: str = Field("",
        description="SHA256 of content — used to skip redundant re-embedding")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def firestore_doc_id(self) -> str:
        return self.chunk_id
