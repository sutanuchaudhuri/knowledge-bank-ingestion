"""Import an enriched textbook content package (Prasolov pedagogy_v3) into Postgres.

Implements v2 pack docs 28 / runtime_extension 03-05:

    REGISTER PACKAGE -> VERIFY FILES + HASHES -> LOAD STAGING -> VALIDATE
    -> TAXONOMY -> BOOK/CHAPTERS -> PROBLEMS+SOLUTIONS(+metadata)
    -> PARTS -> STEPS -> STEP DEPENDENCIES -> LEARNING ITEMS -> DIAGRAMS
    -> RECONCILE -> POSTGRES_COMPLETE

Validation and planning are pure Python (``build_plan``) so they can be tested
offline; database writes are idempotent COPY+upserts, one transaction per stage.

    python etl/import_textbook_package.py PACKAGE_DIR [PACKAGE_DIR ...] --dry-run
    python etl/import_textbook_package.py PACKAGE_DIR --chapter 1      # pilot
    python etl/import_textbook_package.py --status
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from power_geometry_evidence import POWER, power_structure

SOURCE = "prasolov-package-v3"
PACKAGE_VERSION = "pedagogy_v3"
BOOK_CODES = {"PRASOLOV_PLANE_GEOMETRY_V1": "PRASOLOV_PGV1"}
IMPORTED_FILES = {
    "csv/source_manifest.csv": "book",
    "csv/chapters_sections.csv": "chapter_section",
    "csv/problems.csv": "problem",
    "csv/solutions.csv": "solution",
    "csv/diagram_manifest.csv": "diagram",
    "pedagogy_v3/csv/taxonomy_nodes.csv": "taxonomy_node",
    "pedagogy_v3/csv/taxonomy_edges.csv": "taxonomy_edge",
    "pedagogy_v3/csv/problem_taxonomy_enriched.csv": "problem_enrichment",
    "pedagogy_v3/csv/solution_parts.csv": "solution_part",
    "pedagogy_v3/csv/solution_steps.csv": "solution_step",
    "pedagogy_v3/csv/solution_step_dependencies.csv": "step_dependency",
    "pedagogy_v3/csv/transformations_v3_no_proof.csv": "learning_item",
}
CONCEPT_TYPES = {"DOMAIN": 0, "CONCEPT": 1, "SUBCONCEPT": 2}
LEARNING_REVIEW = {"PENDING_REVIEW", "APPROVED", "REJECTED", "NEEDS_REVISION"}
# Same tables and order as import_pedagogy.import_manifest (used by the
# enrichment watcher), so concurrent writers queue instead of deadlocking.
KNOWLEDGE_LOCK = (
    "LOCK TABLE knowledge.skill, knowledge.skill_relation, knowledge.skill_concept, "
    "knowledge.problem_skill, knowledge.problem_pedagogy, knowledge.concept_relation, "
    "knowledge.concept, core.problem IN SHARE ROW EXCLUSIVE MODE"
)
DEPENDENCY_TYPES = {"NEXT", "DEPENDS_ON", "USES_RESULT", "JUSTIFIES", "ALTERNATIVE_TO", "CHECKS"}
PROBLEM_ID = re.compile(r"(\d+)\.(\d+)")


# ------------------------------------------------------------------ helpers --
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)]


def as_int(value: str | None) -> int | None:
    value = (value or "").strip()
    return int(value) if re.fullmatch(r"-?\d+", value) else None


def as_float(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def as_bool(value: str | None) -> bool | None:
    value = (value or "").strip().upper()
    return {"TRUE": True, "1": True, "YES": True, "FALSE": False, "0": False, "NO": False}.get(value)


def split_pipe(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split("|") if part.strip()]


def suffix(base: str, occurrence: int) -> str:
    return base if occurrence == 1 else f"{base}#{occurrence}"


def chapter_of(problem_id: str) -> int | None:
    match = PROBLEM_ID.fullmatch(problem_id or "")
    return int(match.group(1)) if match else None


# ------------------------------------------------------------------ package --
@dataclass
class Package:
    root: Path
    name: str
    files: dict[str, dict[str, Any]]
    rows: dict[str, list[dict[str, str]]]
    manifest_hash: str

    @property
    def book(self) -> dict[str, str]:
        return self.rows["csv/source_manifest.csv"][0]


def load_package(root: Path) -> Package:
    root = root.resolve()
    missing = [rel for rel in IMPORTED_FILES if not (root / rel).is_file()]
    if missing:
        raise SystemExit(f"{root}: missing package files {missing}")
    files: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("csv/*.csv")) + sorted(root.glob("pedagogy_v3/csv/*.csv")):
        rel = path.relative_to(root).as_posix()
        files[rel] = {
            "role": "ENRICHED" if rel.startswith("pedagogy_v3/") else "RAW",
            "sha256": sha256_file(path),
            "size": path.stat().st_size,
        }
    for path in sorted((root / "diagrams").rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            files[rel] = {"role": "ASSET", "sha256": sha256_file(path), "size": path.stat().st_size}
    rows = {rel: read_csv(root / rel) for rel in IMPORTED_FILES}
    for rel in files:
        if rel.endswith(".csv"):
            files[rel]["rows"] = len(rows[rel]) if rel in rows else len(read_csv(root / rel))
    manifest = "\n".join(f"{rel}\t{meta['sha256']}" for rel, meta in sorted(files.items()))
    name = f"{root.name.lower()}_{PACKAGE_VERSION}"
    return Package(root, name, files, rows, hashlib.sha256(manifest.encode()).hexdigest())


# --------------------------------------------------------------------- plan --
@dataclass
class StageRow:
    source_file: str
    row_number: int
    entity_type: str
    external_id: str
    row: dict[str, str]
    status: str = "PENDING"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    target_key: str | None = None

    def reject(self, message: str) -> None:
        self.status = "REJECTED"
        self.errors.append(message)


@dataclass
class Plan:
    package: Package
    book_code: str
    scope: str
    chapters: set[int] | None
    staging: list[StageRow] = field(default_factory=list)
    conflicts: dict[tuple[str, str, str], dict[str, Any]] = field(default_factory=dict)
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: dict[tuple[str, str, str], dict[str, Any]] = field(default_factory=dict)
    chapter_sections: dict[tuple[int, str], dict[str, Any]] = field(default_factory=dict)
    problems: dict[str, dict[str, Any]] = field(default_factory=dict)
    solutions: dict[str, dict[str, Any]] = field(default_factory=dict)
    enrichment: dict[str, dict[str, Any]] = field(default_factory=dict)
    parts: dict[str, dict[str, Any]] = field(default_factory=dict)
    steps: dict[str, dict[str, Any]] = field(default_factory=dict)
    dependencies: dict[tuple[str, str, str], dict[str, Any]] = field(default_factory=dict)
    learning_items: dict[str, dict[str, Any]] = field(default_factory=dict)
    anchors: dict[tuple[str, str], int] = field(default_factory=dict)
    diagrams: dict[str, dict[str, Any]] = field(default_factory=dict)

    def conflict(self, entity: str, external_id: str, kind: str, severity: str, **detail: Any) -> None:
        self.conflicts[(entity, external_id, kind)] = {"severity": severity, "detail": detail}

    def in_scope(self, problem_id: str) -> bool:
        return self.chapters is None or chapter_of(problem_id) in self.chapters

    def summary(self) -> dict[str, Any]:
        by_entity: dict[str, Counter] = defaultdict(Counter)
        for stage in self.staging:
            by_entity[stage.entity_type][stage.status] += 1
        severities = Counter(c["severity"] for c in self.conflicts.values())
        kinds = Counter(f"{k[0]}:{k[2]}" for k in self.conflicts)
        return {
            "package": self.package.name,
            "scope": self.scope,
            "manifest_hash": self.package.manifest_hash,
            "staging": {entity: dict(counts) for entity, counts in sorted(by_entity.items())},
            "planned": {
                "taxonomy_node": len(self.nodes),
                "taxonomy_edge": len(self.edges),
                "problem": len(self.problems),
                "solution": len(self.solutions),
                "problem_enrichment": len(self.enrichment),
                "solution_part": len(self.parts),
                "solution_step": len(self.steps),
                "step_dependency": len(self.dependencies),
                "learning_item": len(self.learning_items),
                "learning_item_anchor": len(self.anchors),
                "diagram": len(self.diagrams),
            },
            "conflicts": dict(severities),
            "conflict_kinds": dict(sorted(kinds.items())),
        }


def _stage(plan: Plan, rel: str, external: str) -> list[StageRow]:
    entity = IMPORTED_FILES[rel]
    rows = []
    for index, row in enumerate(plan.package.rows[rel], start=2):
        stage = StageRow(rel, index, entity, row.get(external, "") if external else str(index), row)
        plan.staging.append(stage)
        rows.append(stage)
    return rows


def _scoped(plan: Plan, stage: StageRow, problem_id: str) -> bool:
    if plan.in_scope(problem_id):
        return True
    stage.warnings.append(f"outside import scope {plan.scope}")
    return False


def build_plan(package: Package, chapters: Iterable[int] | None = None) -> Plan:
    book_id = package.book.get("book_id", "")
    chapter_set = set(chapters) if chapters else None
    scope = "all" if chapter_set is None else "chapters:" + ",".join(map(str, sorted(chapter_set)))
    plan = Plan(package, BOOK_CODES.get(book_id, book_id), scope, chapter_set)
    book = plan.book_code
    for stage in _stage(plan, "csv/source_manifest.csv", "book_id"):
        stage.status, stage.target_key = "VALID", book

    # Taxonomy nodes/edges are always imported in full: they are shared vocabulary.
    for stage in _stage(plan, "pedagogy_v3/csv/taxonomy_nodes.csv", "taxonomy_node_id"):
        row, node_id = stage.row, stage.external_id
        if not node_id or not row.get("name"):
            stage.reject("taxonomy node requires taxonomy_node_id and name")
        elif row.get("node_type") not in {*CONCEPT_TYPES, "SKILL", "TECHNIQUE"}:
            stage.reject(f"unsupported node_type {row.get('node_type')!r}")
        elif node_id in plan.nodes:
            stage.reject("duplicate taxonomy_node_id")
            plan.conflict("taxonomy_node", node_id, "DUPLICATE_ID", "WARNING")
        else:
            stage.status, stage.target_key = "VALID", node_id
            plan.nodes[node_id] = {
                "taxonomy_node_id": node_id,
                "node_type": row["node_type"],
                "name": row["name"],
                "parent_node_id": row.get("parent_node_id") or None,
                "chapter_number": as_int(row.get("chapter_number")),
                "section_number": row.get("section_number") or None,
                "source_basis": row.get("source_basis") or None,
                "description": row.get("description") or None,
            }
    for stage in _stage(plan, "pedagogy_v3/csv/taxonomy_edges.csv", ""):
        row = stage.row
        key = (row.get("from_node_id", ""), row.get("to_node_id", ""), row.get("relationship_type", ""))
        stage.external_id = "->".join(key)
        if key[0] not in plan.nodes or key[1] not in plan.nodes:
            stage.reject("taxonomy edge endpoint missing")
        elif key[0] == key[1] or not key[2]:
            stage.reject("taxonomy edge self-loop or missing relationship_type")
        else:
            stage.status, stage.target_key = "VALID", stage.external_id
            plan.edges[key] = {"source_basis": row.get("source_basis") or None,
                               "confidence": as_float(row.get("confidence"))}

    for stage in _stage(plan, "csv/chapters_sections.csv", ""):
        row = stage.row
        chapter = as_int(row.get("chapter_number"))
        section = row.get("section_number") or "-"
        stage.external_id = f"{chapter}.{section}"
        if chapter is None:
            stage.reject("chapter_number is not an integer")
        elif chapter_set is None or chapter in chapter_set:
            stage.status, stage.target_key = "VALID", stage.external_id
            plan.chapter_sections[(chapter, section)] = {
                "chapter_title": row.get("chapter_title") or None,
                "section_title": row.get("section_title") or None,
            }
        else:
            stage.warnings.append(f"outside import scope {scope}")

    # Problems: a duplicated id keeps the numbered-section row (the other copy is
    # chapter-introduction prose mis-captured as a problem, e.g. 13.39 INTRO).
    candidates: dict[str, list[StageRow]] = defaultdict(list)
    for stage in _stage(plan, "csv/problems.csv", "problem_id"):
        row, pid = stage.row, stage.external_id
        match = PROBLEM_ID.fullmatch(pid)
        if not match:
            stage.reject("problem_id must look like <chapter>.<number>")
        elif str(as_int(row.get("chapter_number"))) != match.group(1):
            stage.reject("problem_id chapter does not match chapter_number")
        elif not row.get("problem_text"):
            stage.reject("problem_text is empty")
        elif _scoped(plan, stage, pid):
            candidates[pid].append(stage)
    for pid, stages in candidates.items():
        chosen = max(stages, key=lambda s: (s.row.get("section_number", "").isdigit(),
                                            bool(s.row.get("source_page_start")), -s.row_number))
        for other in stages:
            if other is not chosen:
                other.reject(f"duplicate problem_id; kept source row {chosen.row_number}")
                plan.conflict("problem", pid, "DUPLICATE_PROBLEM_ID", "WARNING",
                              kept_row=chosen.row_number, rejected_row=other.row_number,
                              rejected_section=other.row.get("section_number"),
                              rejected_text=other.row.get("problem_text", "")[:240])
        row = chosen.row
        chapter, number = (int(x) for x in PROBLEM_ID.fullmatch(pid).groups())
        code = f"{book}_CH{chapter:02d}_P{number:03d}"
        chosen.status, chosen.target_key = "VALID", code
        band = as_int(row.get("difficulty_band_source_order"))
        plan.problems[pid] = {
            "source_problem_id": pid,
            "chapter": chapter,
            "problem_number": number,
            "canonical_code": code,
            "statement_text": row["problem_text"],
            "content_hash": hashlib.sha256(row["problem_text"].encode()).hexdigest(),
            "difficulty_band": f"Textbook band {band}/5 (source order)" if band else None,
            "row": row,
        }

    for stage in _stage(plan, "csv/solutions.csv", "solution_id"):
        row, pid = stage.row, stage.row.get("problem_id", "")
        if not _scoped(plan, stage, pid):
            continue
        if pid not in plan.problems:
            stage.reject("solution references a problem that is not in problems.csv")
            plan.conflict("solution", stage.external_id, "ORPHAN_SOLUTION", "WARNING", problem_id=pid)
        elif not row.get("solution_text"):
            stage.reject("solution_text is empty")
        elif pid in plan.solutions:
            stage.reject("second solution for the same problem")
            plan.conflict("solution", stage.external_id, "DUPLICATE_SOLUTION", "WARNING", problem_id=pid)
        else:
            stage.status, stage.target_key = "VALID", stage.external_id
            plan.solutions[pid] = {"source_solution_id": stage.external_id, "row": row}

    def node(stage: StageRow, value: str | None, label: str) -> str | None:
        if not value:
            return None
        if value in plan.nodes:
            return value
        stage.warnings.append(f"{label} {value} is not a taxonomy node; left empty")
        return None

    enrich_candidates: dict[str, list[StageRow]] = defaultdict(list)
    for stage in _stage(plan, "pedagogy_v3/csv/problem_taxonomy_enriched.csv", "problem_id"):
        if not _scoped(plan, stage, stage.external_id):
            continue
        if stage.external_id not in plan.problems:
            stage.reject("taxonomy row references an unknown or rejected problem")
        else:
            enrich_candidates[stage.external_id].append(stage)
    for pid, stages in enrich_candidates.items():
        section = plan.problems[pid]["row"].get("section_number")

        def matches(stage: StageRow) -> bool:
            sub = plan.nodes.get(stage.row.get("subconcept_id", ""), {})
            return str(sub.get("section_number") or "") == section

        chosen = next((s for s in stages if matches(s)), stages[0])
        for other in stages:
            if other is not chosen:
                other.reject("duplicate taxonomy row for problem; kept the section-matching row")
                plan.conflict("problem_enrichment", pid, "DUPLICATE_TAXONOMY_ROW", "INFO",
                              kept=chosen.row.get("subconcept_id"), rejected=other.row.get("subconcept_id"))
        row = chosen.row
        chosen.status, chosen.target_key = "VALID", pid
        plan.enrichment[pid] = {
            "concept_node_id": node(chosen, row.get("concept_id"), "concept_id"),
            "subconcept_node_id": node(chosen, row.get("subconcept_id"), "subconcept_id"),
            "primary_skill_node_id": node(chosen, row.get("primary_skill_id"), "primary_skill_id"),
            "solution_step_skill_ids": [s for s in split_pipe(row.get("solution_step_skill_ids")) if s in plan.nodes],
            "technique_ids": [t for t in split_pipe(row.get("technique_ids")) if t in plan.nodes],
            "problem_form": row.get("problem_form") or None,
            "difficulty_band_source_order": as_int(row.get("difficulty_band_source_order")),
            "solution_step_count": as_int(row.get("solution_step_count")),
            "taxonomy_mapping_basis": row.get("taxonomy_mapping_basis") or None,
            "taxonomy_confidence": as_float(row.get("taxonomy_confidence")),
        }

    # Parts: repeated part ids (a label reused inside one solution) become
    # occurrence-suffixed keys; source ids are preserved.
    part_occurrences: dict[str, list[str]] = defaultdict(list)
    part_ordinal: Counter = Counter()
    for stage in _stage(plan, "pedagogy_v3/csv/solution_parts.csv", "solution_part_id"):
        row, pid = stage.row, stage.row.get("problem_id", "")
        if not _scoped(plan, stage, pid):
            continue
        solution = plan.solutions.get(pid)
        if solution is None or solution["source_solution_id"] != row.get("solution_id"):
            stage.reject("part references a missing or rejected solution")
            continue
        occurrence = len(part_occurrences[stage.external_id]) + 1
        key = suffix(f"{book}/{stage.external_id}", occurrence)
        part_occurrences[stage.external_id].append(key)
        part_ordinal[pid] += 1
        if occurrence > 1:
            plan.conflict("solution_part", stage.external_id, "REPEATED_PART_ID", "INFO", occurrences=occurrence)
        stage.status, stage.target_key = "VALID", key
        plan.parts[key] = {
            "source_part_id": stage.external_id,
            "occurrence": occurrence,
            "problem": pid,
            "part_label": row.get("part_label") or None,
            "part_ordinal": part_ordinal[pid],
            "source_step_count": as_int(row.get("step_count")),
            "source_page": as_int(row.get("source_page")),
            "part_text_normalized": row.get("part_text_normalized") or None,
            "step_count": 0,
        }

    step_occurrences: dict[str, list[str]] = defaultdict(list)
    step_stages = [s for s in _stage(plan, "pedagogy_v3/csv/solution_steps.csv", "solution_step_id")]
    step_stages.sort(key=lambda s: (s.row.get("problem_id", ""), as_int(s.row.get("global_step_index")) or 0, s.row_number))
    for stage in step_stages:
        row, pid = stage.row, stage.row.get("problem_id", "")
        if not _scoped(plan, stage, pid):
            continue
        parts = part_occurrences.get(row.get("solution_part_id", ""), [])
        if not parts or plan.parts[parts[0]]["problem"] != pid:
            stage.reject("step references a missing or rejected solution part")
            continue
        if not row.get("step_text") or not row.get("step_type"):
            stage.reject("step_text and step_type are required")
            continue
        index_in_part, global_index = as_int(row.get("step_index_in_part")), as_int(row.get("global_step_index"))
        if index_in_part is None or global_index is None:
            stage.reject("step indexes must be integers")
            continue
        occurrence = len(step_occurrences[stage.external_id]) + 1
        part_key = parts[min(occurrence, len(parts)) - 1]
        if occurrence > len(parts):
            stage.warnings.append("more step occurrences than part occurrences; attached to the last part")
        key = suffix(f"{book}/{stage.external_id}", occurrence)
        step_occurrences[stage.external_id].append(key)
        if occurrence > 1:
            plan.conflict("solution_step", stage.external_id, "REPEATED_STEP_ID", "INFO", occurrences=occurrence)
        hint = as_int(row.get("hint_level"))
        if hint is not None and not 1 <= hint <= 4:
            stage.warnings.append(f"hint_level {hint} outside 1-4; left empty")
            hint = None
        stage.status, stage.target_key = "VALID", key
        plan.parts[part_key]["step_count"] += 1
        plan.steps[key] = {
            "source_step_id": stage.external_id,
            "occurrence": occurrence,
            "part": part_key,
            "problem": pid,
            "global_step_index": global_index,
            "step_index_in_part": index_in_part,
            "step_text": row["step_text"],
            "step_type": row["step_type"],
            "tutor_role": row.get("tutor_role") or None,
            "concept_node_id": node(stage, row.get("concept_id"), "concept_id"),
            "subconcept_node_id": node(stage, row.get("subconcept_id"), "subconcept_id"),
            "skill_node_id": node(stage, row.get("skill_id"), "skill_id"),
            "skill_name": row.get("skill_name") or None,
            "hint_level": hint,
            "is_checkpoint": bool(as_bool(row.get("is_checkpoint"))),
            "source_previous_step_id": row.get("previous_step_id") or None,
            "source_next_step_id": row.get("next_step_id") or None,
            "source_page": as_int(row.get("source_page")),
            "source_metadata": {"solution_part": row.get("solution_part"), "source_row": stage.row_number},
        }
    for key, part in plan.parts.items():
        if part["source_step_count"] is not None and part["source_step_count"] != part["step_count"]:
            plan.conflict("solution_part", key, "STEP_COUNT_MISMATCH", "INFO",
                          source_step_count=part["source_step_count"], imported_step_count=part["step_count"])

    # Dependencies come only from the dependency CSV (previous/next are hints).
    for stage in _stage(plan, "pedagogy_v3/csv/solution_step_dependencies.csv", ""):
        row = stage.row
        source_from, source_to, kind = row.get("from_step_id", ""), row.get("to_step_id", ""), row.get("relationship_type", "")
        stage.external_id = f"{source_from}->{source_to}:{kind}"
        pid = (source_from.split("-") + ["", ""])[1]
        if not _scoped(plan, stage, pid):
            continue
        froms, tos = step_occurrences.get(source_from, []), step_occurrences.get(source_to, [])
        if not froms or not tos:
            stage.reject("dependency endpoint is missing or was rejected")
            continue
        if kind not in DEPENDENCY_TYPES:
            stage.warnings.append(f"non-standard relationship_type {kind}")
        if len(froms) > 1 or len(tos) > 1:
            plan.conflict("step_dependency", stage.external_id, "AMBIGUOUS_REPEATED_STEP_ID", "INFO",
                          resolved_to_occurrence=1)
        key = (froms[0], tos[0], kind)
        if key[0] == key[1]:
            stage.reject("self-loop dependency")
            continue
        if key in plan.dependencies:
            stage.status, stage.target_key = "VALID", "|".join(key)
            stage.warnings.append("duplicate dependency row merged")
            continue
        stage.status, stage.target_key = "VALID", "|".join(key)
        plan.dependencies[key] = {
            "logical_dependency": row.get("logical_dependency") or None,
            "confidence": as_float(row.get("confidence")),
            "stage": stage,
        }
    _reject_cycles(plan)

    item_occurrences: Counter = Counter()
    for stage in _stage(plan, "pedagogy_v3/csv/transformations_v3_no_proof.csv", "transformation_id"):
        row, pid = stage.row, stage.row.get("source_problem_id", "")
        if not _scoped(plan, stage, pid):
            continue
        if pid not in plan.problems:
            stage.reject("transformation source problem is missing or rejected")
            continue
        if as_bool(row.get("no_proof")) is not True:
            stage.reject("transformation must have no_proof=TRUE")
            continue
        if not row.get("transformed_question") or not row.get("transformation_type"):
            stage.reject("transformation_type and transformed_question are required")
            continue
        item_occurrences[stage.external_id] += 1
        occurrence = item_occurrences[stage.external_id]
        key = suffix(f"{book}/{stage.external_id}", occurrence)
        if occurrence > 1:
            plan.conflict("learning_item", stage.external_id, "DUPLICATE_TRANSFORMATION_ID", "INFO",
                          occurrences=occurrence)
        choices = None
        if row.get("choices_json"):
            try:
                choices = json.loads(row["choices_json"])
            except json.JSONDecodeError:
                stage.warnings.append("choices_json is not valid JSON; left empty")
        review = row.get("review_status") or "PENDING_REVIEW"
        if review not in LEARNING_REVIEW:
            stage.warnings.append(f"review_status {review} mapped to PENDING_REVIEW")
            review = "PENDING_REVIEW"
        stage.status, stage.target_key = "VALID", key
        parent = row.get("parent_transformation_id")
        plan.learning_items[key] = {
            "source_transformation_id": stage.external_id,
            "occurrence": occurrence,
            "problem": pid,
            "parent_learning_item_id": f"{book}/{parent}" if parent else None,
            "transformation_type": row["transformation_type"],
            "transformed_form": row.get("transformed_form") or None,
            "target_concept_node_id": node(stage, row.get("target_concept_id"), "target_concept_id"),
            "target_subconcept_node_id": node(stage, row.get("target_subconcept_id"), "target_subconcept_id"),
            "target_skill_node_id": node(stage, row.get("target_skill_id"), "target_skill_id"),
            "difficulty_direction": row.get("difficulty_direction") or None,
            "question_text": row["transformed_question"],
            "choices": choices,
            "correct_answer": row.get("correct_answer") or None,
            "answer_or_solution_seed": row.get("answer_or_solution_seed") or None,
            "generation_mode": row.get("generation_mode") or None,
            "solution_part_label": row.get("solution_part") or None,
            "requires_source_problem": as_bool(row.get("requires_source_problem")),
            "diagram_strategy": row.get("diagram_strategy") or None,
            "review_status": review,
        }
        for ordinal, anchor in enumerate(split_pipe(row.get("solution_step_anchor_id")), start=1):
            resolved = step_occurrences.get(anchor)
            if resolved and plan.steps[resolved[0]]["problem"] == pid:
                plan.anchors.setdefault((key, resolved[0]), ordinal)
            else:
                stage.warnings.append(f"anchor step {anchor} not found; skipped")
                plan.conflict("learning_item", key, "MISSING_STEP_ANCHOR", "WARNING", anchor=anchor)

    for stage in _stage(plan, "csv/diagram_manifest.csv", "diagram_id"):
        row, pid = stage.row, stage.row.get("problem_id", "")
        if not _scoped(plan, stage, pid):
            continue
        asset = package.root / row.get("asset_path", "")
        if pid not in plan.problems:
            stage.reject("diagram references a missing or rejected problem")
        elif not row.get("asset_path") or not asset.is_file():
            stage.reject(f"diagram asset missing: {row.get('asset_path')}")
        else:
            usage = (row.get("usage") or "").upper()
            key = f"{book}/{stage.external_id}"
            stage.status, stage.target_key = "VALID", key
            plan.diagrams[key] = {
                "source_diagram_id": stage.external_id,
                "problem": pid,
                "usage": usage,
                "visibility": "STUDENT_PROBLEM" if usage == "PROBLEM" else "SOLUTION_HIDDEN",
                "source_pdf_page": as_int(row.get("source_pdf_page")),
                "source_figure_number": row.get("source_figure_number") or None,
                "source_caption": row.get("source_caption") or None,
                "asset_path": row["asset_path"],
                "local_path": str(asset),
                "sha256": package.files.get(row["asset_path"], {}).get("sha256"),
                "extraction_method": row.get("extraction_method") or None,
                "validation_status": row.get("validation_status") or None,
            }
    flag_power_candidates(plan)
    return plan


def flag_power_candidates(plan: Plan) -> None:
    """Preserve staged proposals but withhold unsupported new canonical bridge tags."""
    for pid, enrichment in plan.enrichment.items():
        if POWER not in enrichment["technique_ids"]:
            continue
        steps = [{"solution_step_id": key, "step_text": step["step_text"]}
                 for key, step in plan.steps.items() if step["problem"] == pid]
        audit = power_structure(plan.problems[pid]["statement_text"], steps)
        if audit["status"] == "REVIEW_REQUIRED":
            enrichment["blocked_technique_ids"] = [POWER]
            plan.conflict("problem_enrichment", pid, "TECHNIQUE_EVIDENCE_MISSING", "WARNING",
                          technique_id=POWER, evidence=audit)


def _reject_cycles(plan: Plan) -> None:
    """Keep the step DAG acyclic: if a problem's graph has a cycle, drop its
    backward (by global index) edges, which always restores acyclicity."""
    by_problem: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for key in plan.dependencies:
        by_problem[plan.steps[key[0]]["problem"]].append(key)
    for pid, keys in by_problem.items():
        if not _has_cycle(keys):
            continue
        for key in keys:
            if plan.steps[key[1]]["global_step_index"] <= plan.steps[key[0]]["global_step_index"]:
                stage = plan.dependencies.pop(key)["stage"]
                stage.reject("edge participates in a dependency cycle")
                plan.conflict("step_dependency", stage.external_id, "CYCLE_EDGE_REJECTED", "WARNING", problem=pid)


def _has_cycle(keys: list[tuple[str, str, str]]) -> bool:
    outgoing: dict[str, set[str]] = defaultdict(set)
    indegree: Counter = Counter()
    nodes: set[str] = set()
    for start, end, _ in keys:
        nodes |= {start, end}
        if end not in outgoing[start]:
            outgoing[start].add(end)
            indegree[end] += 1
    ready = [n for n in nodes if indegree[n] == 0]
    seen = 0
    while ready:
        current = ready.pop()
        seen += 1
        for nxt in outgoing[current]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(nxt)
    return seen != len(nodes)


# ----------------------------------------------------------------------- db --
@dataclass
class Counts:
    created: int = 0
    updated: int = 0
    unchanged: int = 0

    def __iadd__(self, other: Counts) -> Counts:
        self.created += other.created
        self.updated += other.updated
        self.unchanged += other.unchanged
        return self


_TEMP = 0


def upsert(cur, table: str, columns: list[str], rows: list[tuple], key: list[str],
           update: list[str] | None = None, guard: str | None = None, touch: bool = False) -> Counts:
    """COPY rows into a temp table, then INSERT .. ON CONFLICT; unchanged rows are
    not rewritten, so created/updated/unchanged counts are exact."""
    global _TEMP
    if not rows:
        return Counts()
    _TEMP += 1
    temp = f"_upsert_{_TEMP}"
    cols = ", ".join(columns)
    cur.execute(f"CREATE TEMP TABLE {temp} ON COMMIT DROP AS SELECT {cols} FROM {table} WITH NO DATA")
    with cur.copy(f"COPY {temp} ({cols}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)
    update = [c for c in (update if update is not None else columns) if c not in key]
    if update:
        sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in update) + (", updated_at = now()" if touch else "")
        changed = f"({', '.join('t.' + c for c in update)}) IS DISTINCT FROM ({', '.join('EXCLUDED.' + c for c in update)})"
        where = changed + (f" AND {guard}" if guard else "")
        action = f"DO UPDATE SET {sets} WHERE {where}"
    else:
        action = "DO NOTHING"
    cur.execute(
        f"INSERT INTO {table} AS t ({cols}) SELECT {cols} FROM {temp} "
        f"ON CONFLICT ({', '.join(key)}) {action} RETURNING (xmax = 0)"
    )
    flags = [r[0] for r in cur.fetchall()]
    cur.execute(f"DROP TABLE {temp}")
    created = sum(flags)
    return Counts(created, len(flags) - created, len(rows) - len(flags))


def set_status(conn, package_id: str, status: str, scope: str, detail: str | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT status FROM ingest.content_package WHERE content_package_id=%s", (package_id,))
        previous = cur.fetchone()[0]
        cur.execute(
            "UPDATE ingest.content_package SET status=%s, status_detail=%s, last_scope=%s, updated_at=now(),"
            " imported_at=CASE WHEN %s='POSTGRES_COMPLETE' THEN now() ELSE imported_at END"
            " WHERE content_package_id=%s",
            (status, detail, scope, status, package_id),
        )
        cur.execute(
            "INSERT INTO ingest.package_status_event(content_package_id,from_status,to_status,scope,detail)"
            " VALUES (%s,%s,%s,%s,%s)",
            (package_id, previous, status, scope, detail),
        )
        if status == "POSTGRES_COMPLETE":  # runtime_extension/16: graph/embedding consumers pick this up
            cur.execute(
                "INSERT INTO pipeline.outbox_event(event_type,aggregate_type,aggregate_id,payload)"
                " SELECT 'CONTENT_PACKAGE_IMPORTED','content_package',%s::text,"
                "        jsonb_build_object('book_code',book_code,'package_name',package_name,'scope',%s::text)"
                "   FROM ingest.content_package WHERE content_package_id=%s",
                (package_id, scope, package_id),
            )
    conn.commit()


def register(conn, plan: Plan) -> str:
    package = plan.package
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO ingest.content_package(package_name,package_version,manifest_hash,book_code,source_root)"
            " VALUES (%s,%s,%s,%s,%s) ON CONFLICT (package_name,package_version,manifest_hash)"
            " DO UPDATE SET source_root=EXCLUDED.source_root RETURNING content_package_id, (xmax = 0)",
            (package.name, PACKAGE_VERSION, package.manifest_hash, plan.book_code, str(package.root)),
        )
        package_id, created = cur.fetchone()
        if created:
            cur.execute(
                "INSERT INTO ingest.package_status_event(content_package_id,to_status,scope,detail)"
                " VALUES (%s,'REGISTERED',%s,'package registered')", (package_id, plan.scope))
        upsert(cur, "ingest.package_file",
               ["content_package_id", "relative_path", "file_role", "sha256", "byte_size", "row_count"],
               [(package_id, rel, meta["role"], meta["sha256"], meta["size"], meta.get("rows"))
                for rel, meta in package.files.items()],
               ["content_package_id", "relative_path"])
    conn.commit()
    return str(package_id)


def stage_rows(conn, plan: Plan, package_id: str) -> None:
    from psycopg.types.json import Jsonb

    with conn.cursor() as cur:
        cur.execute("DELETE FROM ingest.staging_row WHERE content_package_id=%s", (package_id,))
        with cur.copy(
            "COPY ingest.staging_row(content_package_id,source_file,source_row_number,entity_type,external_id,"
            "source_row_json,validation_status,validation_errors,validation_warnings,target_key) FROM STDIN"
        ) as copy:
            for s in plan.staging:
                copy.write_row((package_id, s.source_file, s.row_number, s.entity_type, s.external_id,
                                Jsonb(s.row), s.status, Jsonb(s.errors), Jsonb(s.warnings), s.target_key))
        rows = [(package_id, e, x, k, c["severity"], Jsonb(c["detail"])) for (e, x, k), c in plan.conflicts.items()]
        upsert(cur, "ingest.import_conflict",
               ["content_package_id", "entity_type", "external_id", "conflict_type", "severity", "detail"],
               rows, ["content_package_id", "entity_type", "external_id", "conflict_type"],
               update=["severity", "detail"], touch=True)
    conn.commit()


def import_plan(conn, plan: Plan, package_id: str) -> dict[str, Counts]:
    from psycopg.types.json import Jsonb

    counts: dict[str, Counts] = defaultdict(Counts)
    book_row, book = plan.package.book, plan.book_code
    guard_human = "t.approval_method IS DISTINCT FROM 'human' AND t.review_status <> 'REJECTED'"

    # ---- taxonomy bridge into knowledge.* ---------------------------------
    with conn.cursor() as cur:
        cur.execute(KNOWLEDGE_LOCK)
        cur.execute("SELECT taxonomy_node_id, name FROM pedagogy.taxonomy_node WHERE taxonomy_node_id = ANY(%s)",
                    (list(plan.nodes),))
        for node_id, name in cur.fetchall():
            if name != plan.nodes[node_id]["name"]:
                plan.conflict("taxonomy_node", node_id, "NAME_CONFLICT", "INFO",
                              kept=name, incoming=plan.nodes[node_id]["name"])
                plan.nodes[node_id]["name"] = name
        concept_nodes = {k: v for k, v in plan.nodes.items() if v["node_type"] in CONCEPT_TYPES}
        reuse = [k.lower() for k, v in concept_nodes.items() if v["node_type"] == "DOMAIN"]
        counts["knowledge.concept"] += upsert(
            cur, "knowledge.concept", ["slug", "name", "description", "level"],
            [(k.lower(), v["name"], v["description"], CONCEPT_TYPES[v["node_type"]]) for k, v in concept_nodes.items()],
            ["slug"], guard=f"t.slug <> ALL(ARRAY{reuse!r}::text[])" if reuse else None)
        skills = {k: v for k, v in plan.nodes.items() if v["node_type"] == "SKILL"}
        counts["knowledge.skill"] += upsert(
            cur, "knowledge.skill", ["slug", "name", "objective", "source", "confidence"],
            [(k.lower(), v["name"], v["description"] or v["name"], SOURCE, 0.9) for k, v in skills.items()],
            ["slug"], guard=guard_human)
        techniques = {k: v for k, v in plan.nodes.items() if v["node_type"] == "TECHNIQUE"}
        counts["knowledge.technique"] += upsert(
            cur, "knowledge.technique", ["slug", "name", "description"],
            [(k.lower(), v["name"], v["description"]) for k, v in techniques.items()], ["slug"])
        ids: dict[str, tuple[str, str]] = {}
        for table, column, subset in (("concept", "concept_id", concept_nodes), ("skill", "skill_id", skills),
                                       ("technique", "technique_id", techniques)):
            cur.execute(f"SELECT slug, {column} FROM knowledge.{table} WHERE slug = ANY(%s)",
                        ([k.lower() for k in subset],))
            lookup = dict(cur.fetchall())
            for node_id in subset:
                ids[node_id] = (column, lookup[node_id.lower()])
        counts["taxonomy_node"] += upsert(
            cur, "pedagogy.taxonomy_node",
            ["taxonomy_node_id", "node_type", "name", "parent_node_id", "chapter_number", "section_number",
             "source_basis", "description", "concept_id", "skill_id", "technique_id", "content_package_id"],
            [(k, v["node_type"], v["name"], v["parent_node_id"], v["chapter_number"], v["section_number"],
              v["source_basis"], v["description"],
              *(ids[k][1] if ids[k][0] == c else None for c in ("concept_id", "skill_id", "technique_id")),
              package_id) for k, v in plan.nodes.items()],
            ["taxonomy_node_id"],
            update=["node_type", "name", "parent_node_id", "chapter_number", "section_number", "source_basis",
                    "description", "concept_id", "skill_id", "technique_id"], touch=True)
        counts["taxonomy_edge"] += upsert(
            cur, "pedagogy.taxonomy_edge",
            ["from_node_id", "to_node_id", "relationship_type", "source_basis", "confidence", "content_package_id"],
            [(*k, v["source_basis"], v["confidence"], package_id) for k, v in plan.edges.items()],
            ["from_node_id", "to_node_id", "relationship_type"], update=["source_basis", "confidence"])
        skill_concepts, concept_relations = {}, {}
        for (start, end, kind), edge in plan.edges.items():
            a, b = plan.nodes[start]["node_type"], plan.nodes[end]["node_type"]
            confidence = edge["confidence"] if edge["confidence"] is not None else 0.9
            if a == "SKILL" and b in CONCEPT_TYPES:
                skill_concepts[(ids[start][1], ids[end][1])] = confidence
            elif a in CONCEPT_TYPES and b in CONCEPT_TYPES and kind == "PART_OF":
                concept_relations[(ids[end][1], ids[start][1])] = confidence
        counts["knowledge.skill_concept"] += upsert(
            cur, "knowledge.skill_concept", ["skill_id", "concept_id", "source", "confidence"],
            [(*k, SOURCE, v) for k, v in skill_concepts.items()], ["skill_id", "concept_id"],
            update=["confidence"], guard=guard_human)
        counts["knowledge.concept_relation"] += upsert(
            cur, "knowledge.concept_relation",
            ["from_concept_id", "to_concept_id", "relation_type", "strength", "assertion_source"],
            [(*k, "HAS_SUBCONCEPT", v, SOURCE) for k, v in concept_relations.items()],
            ["from_concept_id", "to_concept_id", "relation_type"], update=["strength"], guard=guard_human)
    conn.commit()

    # ---- book, edition, chapters ------------------------------------------
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO core.competition(external_code,name,organization,level) VALUES (%s,%s,%s,'TEXTBOOK')"
            " ON CONFLICT (external_code) DO UPDATE SET name=EXCLUDED.name RETURNING competition_id",
            (book, book_row["title"], book_row.get("author") or None))
        competition_id = cur.fetchone()[0]
        label = f"English translation ({book_row.get('translator_editor') or 'unknown translator'})"
        cur.execute("SELECT edition_id FROM core.competition_edition WHERE competition_id=%s AND edition_label=%s",
                    (competition_id, label))
        found = cur.fetchone()
        if found:
            edition_id = found[0]
        else:
            cur.execute("INSERT INTO core.competition_edition(competition_id,year,edition_label) VALUES (%s,NULL,%s)"
                        " RETURNING edition_id", (competition_id, label))
            edition_id = cur.fetchone()[0]
        upsert(cur, "pedagogy.source_book",
               ["book_code", "external_book_id", "title", "author", "translator_editor", "source_file",
                "competition_id", "edition_id"],
               [(book, book_row["book_id"], book_row["title"], book_row.get("author") or None,
                 book_row.get("translator_editor") or None, book_row.get("source_file") or None,
                 competition_id, edition_id)], ["book_code"], touch=True)
        per_chapter = Counter(p["chapter"] for p in plan.problems.values())
        cur.execute(
            "SELECT p.paper_code, count(*) FROM core.paper p JOIN core.problem q USING(paper_id)"
            " WHERE p.edition_id=%s GROUP BY 1", (edition_id,))
        existing = dict(cur.fetchall())
        chapters = sorted({c for c, _ in plan.chapter_sections} | set(per_chapter))
        counts["paper"] += upsert(
            cur, "core.paper", ["edition_id", "external_code", "paper_code", "paper_type", "question_count", "official"],
            [(edition_id, f"{book}_CH{c:02d}", f"CH{c:02d}", "TEXTBOOK_CHAPTER",
              max(per_chapter[c], existing.get(f"CH{c:02d}", 0)), True) for c in chapters],
            ["external_code"], update=["paper_type", "question_count"])
        cur.execute("SELECT paper_code, paper_id FROM core.paper WHERE edition_id=%s", (edition_id,))
        papers = dict(cur.fetchall())
        counts["chapter_section"] += upsert(
            cur, "pedagogy.chapter_section",
            ["book_code", "chapter_number", "section_number", "chapter_title", "section_title", "paper_id",
             "content_package_id"],
            [(book, c, s, v["chapter_title"], v["section_title"], papers[f"CH{c:02d}"], package_id)
             for (c, s), v in plan.chapter_sections.items()],
            ["book_code", "chapter_number", "section_number"], update=["chapter_title", "section_title", "paper_id"])
    conn.commit()

    # ---- problems, solutions, metadata (one transaction: the enrichment
    # watcher never sees a Prasolov problem without skill+pedagogy rows) ------
    with conn.cursor() as cur:
        cur.execute(KNOWLEDGE_LOCK)
        counts["problem"] += upsert(
            cur, "core.problem",
            ["paper_id", "problem_number", "canonical_code", "statement_text", "content_hash", "difficulty_band",
             "classification_status", "source_url"],
            [(papers[f"CH{p['chapter']:02d}"], p["problem_number"], p["canonical_code"], p["statement_text"],
              p["content_hash"], p["difficulty_band"], "PACKAGE_MAPPED", None) for p in plan.problems.values()],
            ["canonical_code"], update=["statement_text", "content_hash", "difficulty_band", "classification_status"],
            touch=True)
        cur.execute("SELECT canonical_code, problem_id FROM core.problem WHERE canonical_code = ANY(%s)",
                    ([p["canonical_code"] for p in plan.problems.values()],))
        by_code = dict(cur.fetchall())
        pids = {pid: by_code[p["canonical_code"]] for pid, p in plan.problems.items()}
        counts["problem_source_ref"] += upsert(
            cur, "pedagogy.problem_source_ref",
            ["book_code", "source_problem_id", "problem_id", "chapter_number", "section_number", "section_title",
             "source_printed_problem_id", "source_editorial_marker", "source_numbering_note", "source_pdf",
             "source_page_start", "source_page_end", "problem_requires_diagram", "solution_requires_diagram",
             "difficulty_rank_in_section", "section_problem_count", "content_package_id"],
            [(book, pid, pids[pid], p["chapter"], p["row"].get("section_number") or None,
              p["row"].get("section_title") or None, p["row"].get("source_printed_problem_id") or None,
              p["row"].get("source_editorial_marker") or None, p["row"].get("source_numbering_note") or None,
              p["row"].get("source_pdf") or None, as_int(p["row"].get("source_page_start")),
              as_int(p["row"].get("source_page_end")), as_bool(p["row"].get("problem_requires_diagram")),
              as_bool(p["row"].get("solution_requires_diagram")),
              as_int(p["row"].get("difficulty_rank_in_section")), as_int(p["row"].get("section_problem_count")),
              package_id) for pid, p in plan.problems.items()],
            ["book_code", "source_problem_id"])
        counts["solution"] += upsert(
            cur, "core.solution", ["problem_id", "solution_kind", "revision", "body_markdown", "verification_status"],
            [(pids[pid], "TEXTBOOK", 1, s["row"]["solution_text"], "UNVERIFIED") for pid, s in plan.solutions.items()],
            ["problem_id", "solution_kind", "revision"], update=["body_markdown"])
        cur.execute("SELECT problem_id, solution_id FROM core.solution WHERE solution_kind='TEXTBOOK' AND revision=1"
                    " AND problem_id = ANY(%s)", (list(pids.values()),))
        sol_by_problem = dict(cur.fetchall())
        sids = {pid: sol_by_problem[pids[pid]] for pid in plan.solutions}
        counts["solution_source_ref"] += upsert(
            cur, "pedagogy.solution_source_ref",
            ["book_code", "source_solution_id", "solution_id", "problem_id", "solution_first_step", "source_page",
             "content_package_id"],
            [(book, s["source_solution_id"], sids[pid], pids[pid], s["row"].get("solution_first_step") or None,
              as_int(s["row"].get("source_page")), package_id) for pid, s in plan.solutions.items()],
            ["book_code", "source_solution_id"])
        node_id = lambda key: ids[key][1] if key and key in ids else None
        counts["problem_enrichment"] += upsert(
            cur, "pedagogy.problem_enrichment",
            ["problem_id", "concept_node_id", "subconcept_node_id", "primary_skill_node_id", "solution_step_skill_ids",
             "technique_ids", "problem_form", "difficulty_band_source_order", "solution_step_count",
             "taxonomy_mapping_basis", "taxonomy_confidence", "content_package_id"],
            [(pids[pid], e["concept_node_id"], e["subconcept_node_id"], e["primary_skill_node_id"],
              e["solution_step_skill_ids"], e["technique_ids"], e["problem_form"], e["difficulty_band_source_order"],
              e["solution_step_count"], e["taxonomy_mapping_basis"], e["taxonomy_confidence"], package_id)
             for pid, e in plan.enrichment.items()],
            ["problem_id"], touch=True,
            update=["concept_node_id", "subconcept_node_id", "primary_skill_node_id", "solution_step_skill_ids",
                    "technique_ids", "problem_form", "difficulty_band_source_order", "solution_step_count",
                    "taxonomy_mapping_basis", "taxonomy_confidence"])
        concepts, techs, skills_rows, pedagogy = {}, {}, {}, {}
        steps_per_problem = Counter(s["problem"] for s in plan.steps.values())
        for pid, e in plan.enrichment.items():
            problem, confidence = pids[pid], e["taxonomy_confidence"] if e["taxonomy_confidence"] is not None else 0.9
            if node_id(e["subconcept_node_id"]):
                concepts[(problem, node_id(e["subconcept_node_id"]), "PRIMARY")] = confidence
            if node_id(e["concept_node_id"]):
                concepts.setdefault((problem, node_id(e["concept_node_id"]), "CHAPTER_CONCEPT"), confidence)
            for i, tech in enumerate(e["technique_ids"]):
                if tech in e.get("blocked_technique_ids", []):
                    continue
                techs.setdefault((problem, node_id(tech)), ("PRIMARY" if i == 0 else "SECONDARY", confidence))
            primary = e["primary_skill_node_id"]
            if node_id(primary):
                skills_rows[(problem, node_id(primary), "REQUIRES", "primary")] = (1.0, confidence)
            for extra in e["solution_step_skill_ids"]:
                if extra != primary and node_id(extra):
                    skills_rows.setdefault((problem, node_id(extra), "REQUIRES", "supporting"), (0.6, confidence))
            pedagogy[problem] = (steps_per_problem.get(pid) or e["solution_step_count"], confidence)
        counts["knowledge.problem_concept"] += upsert(
            cur, "knowledge.problem_concept", ["problem_id", "concept_id", "role", "confidence", "assertion_source"],
            [(*k, v, SOURCE) for k, v in concepts.items()], ["problem_id", "concept_id", "role"],
            update=["confidence"], guard=guard_human)
        counts["knowledge.problem_technique"] += upsert(
            cur, "knowledge.problem_technique", ["problem_id", "technique_id", "role", "confidence", "assertion_source"],
            [(p, t, role, c, SOURCE) for (p, t), (role, c) in techs.items()], ["problem_id", "technique_id", "role"],
            update=["confidence"], guard=guard_human)
        counts["knowledge.problem_skill"] += upsert(
            cur, "knowledge.problem_skill",
            ["problem_id", "skill_id", "relation_type", "role", "importance", "source", "confidence"],
            [(*k, imp, SOURCE, c) for k, (imp, c) in skills_rows.items()],
            ["problem_id", "skill_id", "relation_type", "role"], update=["importance", "confidence"], guard=guard_human)
        counts["knowledge.problem_pedagogy"] += upsert(
            cur, "knowledge.problem_pedagogy", ["problem_id", "number_of_steps", "source", "confidence"],
            [(p, n, SOURCE, c) for p, (n, c) in pedagogy.items()], ["problem_id"],
            update=["number_of_steps", "confidence"], guard=f"{guard_human} AND t.source = '{SOURCE}'")
    conn.commit()

    # ---- solution DAG -------------------------------------------------------
    with conn.cursor() as cur:
        counts["solution_part"] += upsert(
            cur, "pedagogy.solution_part",
            ["solution_part_id", "source_part_id", "occurrence", "book_code", "solution_id", "problem_id", "part_label",
             "part_ordinal", "step_count", "source_step_count", "source_page", "part_text_normalized",
             "content_package_id"],
            [(k, v["source_part_id"], v["occurrence"], book, sids[v["problem"]], pids[v["problem"]], v["part_label"],
              v["part_ordinal"], v["step_count"], v["source_step_count"], v["source_page"],
              v["part_text_normalized"], package_id) for k, v in plan.parts.items()],
            ["solution_part_id"], touch=True,
            update=["part_label", "part_ordinal", "step_count", "source_step_count", "source_page",
                    "part_text_normalized"])
        counts["solution_step"] += upsert(
            cur, "pedagogy.solution_step",
            ["solution_step_id", "source_step_id", "occurrence", "book_code", "solution_part_id", "solution_id",
             "problem_id", "global_step_index", "step_index_in_part", "step_text", "step_type", "tutor_role",
             "concept_node_id", "subconcept_node_id", "skill_node_id", "skill_name", "hint_level", "is_checkpoint",
             "source_previous_step_id", "source_next_step_id", "source_page", "source_metadata", "content_package_id"],
            [(k, v["source_step_id"], v["occurrence"], book, v["part"], sids[v["problem"]], pids[v["problem"]],
              v["global_step_index"], v["step_index_in_part"], v["step_text"], v["step_type"], v["tutor_role"],
              v["concept_node_id"], v["subconcept_node_id"], v["skill_node_id"], v["skill_name"], v["hint_level"],
              v["is_checkpoint"], v["source_previous_step_id"], v["source_next_step_id"], v["source_page"],
              Jsonb(v["source_metadata"]), package_id) for k, v in plan.steps.items()],
            ["solution_step_id"], touch=True,
            update=["solution_part_id", "global_step_index", "step_index_in_part", "step_text", "step_type",
                    "tutor_role", "concept_node_id", "subconcept_node_id", "skill_node_id", "skill_name", "hint_level",
                    "is_checkpoint", "source_previous_step_id", "source_next_step_id", "source_page",
                    "source_metadata"],
            guard="t.admin_edited_at IS NULL")  # 019: admin skill/checkpoint edits survive re-import
        counts["step_dependency"] += upsert(
            cur, "pedagogy.solution_step_dependency",
            ["from_step_id", "to_step_id", "relationship_type", "logical_dependency", "confidence", "source_type",
             "review_status", "approval_method", "content_package_id"],
            [(*k, v["logical_dependency"], v["confidence"], "IMPORTED_PACKAGE", "REVIEWED", "automatic", package_id)
             for k, v in plan.dependencies.items()],
            ["from_step_id", "to_step_id", "relationship_type"], update=["logical_dependency", "confidence"],
            guard="t.approval_method IS DISTINCT FROM 'human'")
    conn.commit()

    # ---- learning items + diagrams ------------------------------------------
    with conn.cursor() as cur:
        counts["learning_item"] += upsert(
            cur, "pedagogy.learning_item",
            ["learning_item_id", "source_transformation_id", "occurrence", "book_code", "source_problem_id",
             "parent_learning_item_id", "transformation_type", "transformed_form", "target_concept_node_id",
             "target_subconcept_node_id", "target_skill_node_id", "difficulty_direction", "question_text", "choices",
             "correct_answer", "answer_or_solution_seed", "generation_mode", "solution_part_label",
             "requires_source_problem", "diagram_strategy", "no_proof", "review_status", "content_package_id"],
            [(k, v["source_transformation_id"], v["occurrence"], book, pids[v["problem"]], v["parent_learning_item_id"],
              v["transformation_type"], v["transformed_form"], v["target_concept_node_id"],
              v["target_subconcept_node_id"], v["target_skill_node_id"], v["difficulty_direction"],
              v["question_text"], Jsonb(v["choices"]) if v["choices"] is not None else None, v["correct_answer"],
              v["answer_or_solution_seed"], v["generation_mode"], v["solution_part_label"],
              v["requires_source_problem"], v["diagram_strategy"], True, v["review_status"], package_id)
             for k, v in plan.learning_items.items()],
            ["learning_item_id"], touch=True,
            # review_status is owned by admins after import; never overwrite it.
            update=["parent_learning_item_id", "transformation_type", "transformed_form", "target_concept_node_id",
                    "target_subconcept_node_id", "target_skill_node_id", "difficulty_direction", "question_text",
                    "choices", "correct_answer", "answer_or_solution_seed", "generation_mode", "solution_part_label",
                    "requires_source_problem", "diagram_strategy"],
            guard="t.review_status = 'PENDING_REVIEW'")
        counts["learning_item_anchor"] += upsert(
            cur, "pedagogy.learning_item_step_anchor", ["learning_item_id", "solution_step_id", "anchor_ordinal"],
            [(*k, v) for k, v in plan.anchors.items()], ["learning_item_id", "solution_step_id"])
        problem_diagrams: dict[str, list[str]] = defaultdict(list)
        for key, d in sorted(plan.diagrams.items()):
            if d["visibility"] == "STUDENT_PROBLEM":
                problem_diagrams[d["problem"]].append(key)
        image_rows = [(pids[pid], ordinal, plan.diagrams[key]["local_path"], "TEXTBOOK_PACKAGE")
                      for pid, keys in problem_diagrams.items() for ordinal, key in enumerate(keys, start=1)]
        counts["problem_image"] += upsert(cur, "core.problem_image", ["problem_id", "ordinal", "local_path", "source"],
                                          image_rows, ["problem_id", "ordinal"])
        cur.execute("SELECT problem_id, ordinal, problem_image_id FROM core.problem_image WHERE problem_id = ANY(%s)",
                    ([pids[pid] for pid in problem_diagrams],))
        images = {(str(p), o): i for p, o, i in cur.fetchall()}
        image_for = {key: images.get((str(pids[pid]), ordinal))
                     for pid, keys in problem_diagrams.items() for ordinal, key in enumerate(keys, start=1)}
        counts["diagram"] += upsert(
            cur, "pedagogy.diagram",
            ["diagram_id", "source_diagram_id", "book_code", "problem_id", "usage", "visibility", "source_pdf_page",
             "source_figure_number", "source_caption", "asset_path", "local_path", "sha256", "extraction_method",
             "validation_status", "problem_image_id", "content_package_id"],
            [(k, d["source_diagram_id"], book, pids[d["problem"]], d["usage"], d["visibility"], d["source_pdf_page"],
              d["source_figure_number"], d["source_caption"], d["asset_path"], d["local_path"], d["sha256"],
              d["extraction_method"], d["validation_status"], image_for.get(k), package_id)
             for k, d in plan.diagrams.items()],
            ["diagram_id"], touch=True,
            update=["usage", "visibility", "source_pdf_page", "source_figure_number", "source_caption", "asset_path",
                    "local_path", "sha256", "extraction_method", "validation_status", "problem_image_id"])
    conn.commit()
    return counts


RECONCILE_QUERIES = {
    "taxonomy_node": ("pedagogy.taxonomy_node", "taxonomy_node_id"),
    "problem": ("core.problem", "canonical_code"),
    "solution": ("pedagogy.solution_source_ref", "source_solution_id"),
    "problem_enrichment": ("pedagogy.problem_source_ref r JOIN pedagogy.problem_enrichment e USING(problem_id)",
                           "r.source_problem_id"),
    "solution_part": ("pedagogy.solution_part", "solution_part_id"),
    "solution_step": ("pedagogy.solution_step", "solution_step_id"),
    "step_dependency": ("pedagogy.solution_step_dependency",
                        "from_step_id || '|' || to_step_id || '|' || relationship_type"),
    "learning_item": ("pedagogy.learning_item", "learning_item_id"),
    "diagram": ("pedagogy.diagram", "diagram_id"),
    "taxonomy_edge": ("pedagogy.taxonomy_edge", "from_node_id || '->' || to_node_id || ':' || relationship_type"),
}


def reconcile(conn, plan: Plan, package_id: str, counts: dict[str, Counts]) -> bool:
    expected = {
        "taxonomy_node": list(plan.nodes),
        "taxonomy_edge": [f"{a}->{b}:{k}" for a, b, k in plan.edges],
        "problem": [p["canonical_code"] for p in plan.problems.values()],
        "solution": [s["source_solution_id"] for s in plan.solutions.values()],
        "problem_enrichment": list(plan.enrichment),
        "solution_part": list(plan.parts),
        "solution_step": list(plan.steps),
        "step_dependency": ["|".join(k) for k in plan.dependencies],
        "learning_item": list(plan.learning_items),
        "diagram": list(plan.diagrams),
    }
    stage_counts: dict[str, Counter] = defaultdict(Counter)
    for stage in plan.staging:
        in_scope = not any("outside import scope" in w for w in stage.warnings)
        if in_scope:
            stage_counts[stage.entity_type]["source"] += 1
            stage_counts[stage.entity_type][stage.status] += 1
    conflicts = Counter(entity for entity, _, _ in plan.conflicts)
    ok = True
    with conn.cursor() as cur:
        for entity, keys in expected.items():
            table, column = RECONCILE_QUERIES[entity]
            extra = " AND book_code = %s" if entity in {"solution"} else ""
            params: list[Any] = [keys] + ([plan.book_code] if extra else [])
            cur.execute(f"SELECT count(DISTINCT {column}) FROM {table} WHERE {column} = ANY(%s){extra}", params)
            present = cur.fetchone()[0]
            c = counts.get(entity, Counts())
            reconciled = present == len(keys)
            ok &= reconciled
            cur.execute(
                "INSERT INTO ingest.reconciliation(content_package_id,scope,entity_type,source_count,valid_count,"
                "imported_count,created_count,updated_count,unchanged_count,rejected_count,conflict_count,"
                "present_in_db,reconciled,reconciled_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())"
                " ON CONFLICT (content_package_id,scope,entity_type) DO UPDATE SET source_count=EXCLUDED.source_count,"
                " valid_count=EXCLUDED.valid_count, imported_count=EXCLUDED.imported_count,"
                " created_count=EXCLUDED.created_count, updated_count=EXCLUDED.updated_count,"
                " unchanged_count=EXCLUDED.unchanged_count, rejected_count=EXCLUDED.rejected_count,"
                " conflict_count=EXCLUDED.conflict_count, present_in_db=EXCLUDED.present_in_db,"
                " reconciled=EXCLUDED.reconciled, reconciled_at=now()",
                (package_id, plan.scope, entity, stage_counts[entity]["source"], len(keys), present, c.created,
                 c.updated, c.unchanged, stage_counts[entity]["REJECTED"], conflicts[entity], present, reconciled))
        cur.execute(
            "UPDATE ingest.staging_row SET validation_status='IMPORTED', updated_at=now()"
            " WHERE content_package_id=%s AND validation_status='VALID'", (package_id,))
        from psycopg.types.json import Jsonb

        cur.execute("UPDATE ingest.content_package SET report=%s WHERE content_package_id=%s",
                    (Jsonb({**plan.summary(), "upserts": {k: vars(v) for k, v in counts.items()}}), package_id))
    conn.commit()
    return ok


def run(conn, plan: Plan) -> bool:
    package_id = register(conn, plan)
    try:
        set_status(conn, package_id, "VALIDATING", plan.scope, "staging rows + validation")
        stage_rows(conn, plan, package_id)
        set_status(conn, package_id, "IMPORTING", plan.scope, "taxonomy, problems, solution DAG, learning items")
        counts = import_plan(conn, plan, package_id)
        stage_rows(conn, plan, package_id)  # persists conflicts discovered against the database
        set_status(conn, package_id, "RECONCILING", plan.scope)
        ok = reconcile(conn, plan, package_id, counts)
    except Exception as exc:
        conn.rollback()
        set_status(conn, package_id, "FAILED", plan.scope, f"{type(exc).__name__}: {exc}"[:900])
        raise
    set_status(conn, package_id, "POSTGRES_COMPLETE" if ok else "FAILED", plan.scope,
               "reconciled" if ok else "reconciliation mismatch; see ingest.reconciliation")
    return ok


STATUS_SQL = """
SELECT p.package_name, p.status, p.last_scope, p.imported_at, p.updated_at,
       r.entity_type, r.source_count, r.valid_count, r.present_in_db, r.created_count, r.updated_count,
       r.unchanged_count, r.rejected_count, r.conflict_count, r.reconciled
FROM ingest.content_package p
LEFT JOIN ingest.reconciliation r ON r.content_package_id = p.content_package_id AND r.scope = p.last_scope
ORDER BY p.package_name, r.entity_type
"""


def print_status(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(STATUS_SQL)
        current = None
        for row in cur.fetchall():
            if row[0] != current:
                current = row[0]
                print(f"\n{row[0]}  status={row[1]}  scope={row[2]}  imported_at={row[3]}  updated_at={row[4]}")
                print(f"  {'entity':<20}{'source':>8}{'valid':>8}{'in_db':>8}{'new':>8}{'upd':>8}{'same':>8}"
                      f"{'rej':>6}{'confl':>7}  ok")
            if row[5]:
                print(f"  {row[5]:<20}" + "".join(f"{v:>8}" for v in row[6:12]) + f"{row[12]:>6}{row[13]:>7}  "
                      + ("yes" if row[14] else "NO"))
        cur.execute("SELECT severity, conflict_type, count(*) FROM ingest.import_conflict GROUP BY 1,2 ORDER BY 1,2")
        print("\nconflicts:", ", ".join(f"{s}/{k}={n}" for s, k, n in cur.fetchall()) or "none")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("packages", nargs="*", type=Path, help="corpus folders containing csv/ and pedagogy_v3/")
    parser.add_argument("--chapter", type=int, action="append", help="pilot scope; repeatable")
    parser.add_argument("--dry-run", action="store_true", help="validate and plan only; no database access")
    parser.add_argument("--status", action="store_true", help="print package/reconciliation status and exit")
    args = parser.parse_args(argv)
    if not args.packages and not args.status:
        parser.error("give at least one package directory or --status")
    plans = []
    for root in args.packages:
        plan = build_plan(load_package(root), args.chapter)
        if not plan.problems and args.chapter:
            print(f"{root.name}: no problems in scope {plan.scope}; skipped")
            continue
        plans.append(plan)
        print(json.dumps(plan.summary(), indent=2))
    if args.dry_run:
        return 0
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from pdf_pipeline import _connect

    with _connect(direct=True) as conn:
        ok = True
        for plan in plans:
            result = run(conn, plan)
            print(f"{plan.package.name}: {'POSTGRES_COMPLETE' if result else 'FAILED'} ({plan.scope})")
            ok &= result
        if args.status or plans:
            print_status(conn)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
