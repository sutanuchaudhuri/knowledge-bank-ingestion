"""Validate explicit version-1 authoring JSON; import atomically only on request."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

import psycopg

REVIEW = {"PENDING", "REVIEWED", "REJECTED"}
SKILL_RELATIONS = {"PREREQUISITE_OF", "PART_OF", "BUILDS_ON"}
PROBLEM_RELATIONS = {"REQUIRES", "PRACTICES", "TESTS"}
PROVENANCE = {"source", "confidence", "review_status"}
AXES = {"conceptual_depth", "technical_load", "algebraic_load", "insight_required"}
FORMATS = {
    "skills": ({"slug", "name", "objective"}, {"level"}, ("slug",)),
    "skill_concepts": ({"skill_slug", "concept_slug"}, set(), ("skill_slug", "concept_slug")),
    "skill_relations": (
        {"from_skill_slug", "to_skill_slug", "relation_type"},
        set(),
        ("from_skill_slug", "to_skill_slug", "relation_type"),
    ),
    "problem_skills": (
        {"problem_code", "skill_slug", "relation_type", "role", "importance"},
        {"required_level"},
        ("problem_code", "skill_slug", "relation_type", "role"),
    ),
    "problem_pedagogy": (
        {"problem_code"},
        AXES | {"number_of_steps", "prerequisite_depth", "estimated_contest_level"},
        ("problem_code",),
    ),
}
TABLES = ("skill", "skill_concept", "skill_relation", "problem_skill", "problem_pedagogy")


class ManifestError(ValueError):
    """Actionable authoring or database consistency failure."""


def validate_manifest(document: object) -> dict:
    if (
        not isinstance(document, dict)
        or type(document.get("version")) is not int
        or document["version"] != 1
    ):
        raise ManifestError("Manifest must be an object with version: 1")
    if set(document) - ({"version"} | set(FORMATS)):
        raise ManifestError("Unknown manifest sections")
    result = {"version": 1}
    for section, (required, optional, keys) in FORMATS.items():
        rows = document.get(section, [])
        if not isinstance(rows, list):
            raise ManifestError(f"{section} must be an array")
        seen = set()
        result[section] = []
        for index, row in enumerate(rows):
            where = f"{section}[{index}]"
            if not isinstance(row, dict) or (required | PROVENANCE) - set(row):
                raise ManifestError(f"{where}: missing required fields")
            if set(row) - (required | optional | PROVENANCE):
                raise ManifestError(f"{where}: unknown fields")
            for field in required | {"source", "review_status"}:
                if field in {"importance"}:
                    continue
                if (
                    not isinstance(row[field], str)
                    or not row[field].strip()
                    or row[field] != row[field].strip()
                ):
                    raise ManifestError(f"{where}.{field}: expected nonempty trimmed string")
            if row["review_status"] not in REVIEW:
                raise ManifestError(f"{where}: invalid review_status")
            for field in {"confidence", "importance"} & set(row):
                value = row[field]
                if (
                    type(value) not in (int, float)
                    or not math.isfinite(value)
                    or not 0 <= value <= 1
                ):
                    raise ManifestError(f"{where}.{field}: expected finite number in 0..1")
            for field in (
                AXES | {"level", "required_level", "number_of_steps", "prerequisite_depth"}
            ) & set(row):
                value = row[field]
                lower, upper = (
                    (0, None) if field in {"number_of_steps", "prerequisite_depth"} else (1, 5)
                )
                if value is not None and (
                    type(value) is not int or value < lower or (upper is not None and value > upper)
                ):
                    raise ManifestError(f"{where}.{field}: invalid integer bounds")
            contest = row.get("estimated_contest_level")
            if contest is not None and (
                not isinstance(contest, str) or not contest.strip() or contest != contest.strip()
            ):
                raise ManifestError(f"{where}: invalid estimated_contest_level")
            if section == "skill_relations" and (
                row["relation_type"] not in SKILL_RELATIONS
                or row["from_skill_slug"] == row["to_skill_slug"]
            ):
                raise ManifestError(f"{where}: invalid skill relation")
            if section == "problem_skills" and (
                row["relation_type"] not in PROBLEM_RELATIONS
                or row["role"] not in {"primary", "supporting"}
            ):
                raise ManifestError(f"{where}: invalid relation_type or role")
            key = tuple(row[k] for k in keys)
            if key in seen:
                raise ManifestError(f"{where}: duplicate natural key {key}")
            seen.add(key)
            result[section].append(dict(row))
    validate_cycles(result["skill_relations"], [])
    return result


def assert_acyclic(edges: list[tuple[str, str]], label: str) -> None:
    adjacency: dict[str, set[str]] = {}
    indegree: dict[str, int] = {}
    for start, end in set(edges):
        adjacency.setdefault(start, set()).add(end)
        indegree.setdefault(start, 0)
        indegree[end] = indegree.get(end, 0) + 1
    ready = [node for node, count in indegree.items() if count == 0]
    visited = 0
    while ready:
        node = ready.pop()
        visited += 1
        for end in adjacency.get(node, ()):
            indegree[end] -= 1
            if indegree[end] == 0:
                ready.append(end)
    if visited != len(indegree):
        remaining = {node for node, count in indegree.items() if count > 0}
        predecessors = {
            end: start
            for start, end in sorted(set(edges))
            if start in remaining and end in remaining
        }
        path: list[str] = []
        positions: dict[str, int] = {}
        node = min(remaining)
        while node not in positions:
            positions[node] = len(path)
            path.append(node)
            node = predecessors[node]
        cycle = list(reversed(path[positions[node] :] + [node]))
        raise ManifestError(
            f"Reviewed {label} cycle: {' -> '.join(cycle)}; "
            "correct proposed relationships without deleting existing prerequisites"
        )


def validate_cycles(skill_relations: list[dict], concept_relations: list[dict]) -> None:
    for relations, prefix, start, end in (
        (skill_relations, "skill", "from_skill_slug", "to_skill_slug"),
        (concept_relations, "concept", "from_slug", "to_slug"),
    ):
        for kind in ("PREREQUISITE_OF", "PART_OF"):
            edges = []
            for row in relations:
                if row["review_status"] != "REVIEWED":
                    continue
                relation_type = row["relation_type"]
                if relation_type == kind:
                    edges.append((row[start], row[end]))
                elif kind == "PART_OF" and relation_type == "HAS_SUBCONCEPT":
                    edges.append((row[end], row[start]))
            assert_acyclic(edges, f"{prefix} {kind}")


def require_schema(cur) -> None:
    for table in TABLES:
        cur.execute("SELECT to_regclass(%s)", (f"knowledge.{table}",))
        if cur.fetchone()[0] is None:
            raise ManifestError(
                "Pedagogy schema missing: apply mathbank-db/sql/006_pedagogy.sql explicitly first"
            )


def resolve_manifest(cur, manifest: dict) -> dict[str, list[dict]]:
    require_schema(cur)
    lookup = {}
    for name, query in (
        ("skill", "SELECT slug, skill_id FROM knowledge.skill"),
        ("concept", "SELECT slug, concept_id FROM knowledge.concept"),
        ("problem", "SELECT canonical_code, problem_id FROM core.problem"),
    ):
        cur.execute(query)
        lookup[name] = dict(cur.fetchall())
    for row in manifest["skills"]:
        lookup["skill"].setdefault(row["slug"], None)
    cur.execute("""
        SELECT a.slug, b.slug, r.relation_type, r.review_status
        FROM knowledge.skill_relation r
        JOIN knowledge.skill a ON a.skill_id = r.from_skill_id
        JOIN knowledge.skill b ON b.skill_id = r.to_skill_id
    """)
    existing = {
        (a, b, kind): {
            "from_skill_slug": a,
            "to_skill_slug": b,
            "relation_type": kind,
            "review_status": status,
        }
        for a, b, kind, status in cur.fetchall()
    }
    for row in manifest["skill_relations"]:
        existing[(row["from_skill_slug"], row["to_skill_slug"], row["relation_type"])] = row
    cur.execute("""
        SELECT a.slug, b.slug, r.relation_type, r.review_status
        FROM knowledge.concept_relation r
        JOIN knowledge.concept a ON a.concept_id = r.from_concept_id
        JOIN knowledge.concept b ON b.concept_id = r.to_concept_id
    """)
    concepts = [
        {"from_slug": a, "to_slug": b, "relation_type": kind, "review_status": status}
        for a, b, kind, status in cur.fetchall()
    ]
    validate_cycles(list(existing.values()), concepts)
    for section, rows in manifest.items():
        if section == "version":
            continue
        for row in rows:
            for field, kind in (
                ("skill_slug", "skill"),
                ("from_skill_slug", "skill"),
                ("to_skill_slug", "skill"),
                ("concept_slug", "concept"),
                ("problem_code", "problem"),
            ):
                if field in row and row[field] not in lookup[kind]:
                    raise ManifestError(f"{section}: unknown {field} {row[field]!r}")
    return lookup


def upsert_sql(table: str, columns: list[str], keys: tuple[str, ...]) -> str:
    if table not in TABLES:
        raise ManifestError("Unsupported table")
    # Column names are fixed by the importer, never taken from unvalidated JSON.
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c not in keys)
    return (
        f"INSERT INTO knowledge.{table} ({', '.join(columns)}) "
        f"VALUES ({', '.join(['%s'] * len(columns))}) "
        f"ON CONFLICT ({', '.join(keys)}) DO UPDATE SET {updates}"
    )


def import_manifest(cur, manifest: dict) -> None:
    # Serialize authoring against concurrent writers while checking existing edges.
    cur.execute(
        "LOCK TABLE knowledge.skill, knowledge.skill_relation, knowledge.skill_concept, "
        "knowledge.problem_skill, knowledge.problem_pedagogy, knowledge.concept_relation, "
        "knowledge.concept, core.problem IN SHARE ROW EXCLUSIVE MODE"
    )
    lookup = resolve_manifest(cur, manifest)
    for row in manifest["skills"]:
        columns = ["slug", "name", "objective", "level", "source", "confidence", "review_status"]
        cur.execute(
            upsert_sql("skill", columns, ("slug",)) + " RETURNING skill_id",
            [row.get(c) for c in columns],
        )
        lookup["skill"][row["slug"]] = cur.fetchone()[0]
    specs = (
        (
            "skill_concepts",
            "skill_concept",
            (("skill_slug", "skill_id", "skill"), ("concept_slug", "concept_id", "concept")),
            ("skill_id", "concept_id"),
            [],
        ),
        (
            "skill_relations",
            "skill_relation",
            (
                ("from_skill_slug", "from_skill_id", "skill"),
                ("to_skill_slug", "to_skill_id", "skill"),
            ),
            ("from_skill_id", "to_skill_id", "relation_type"),
            ["relation_type"],
        ),
        (
            "problem_skills",
            "problem_skill",
            (("problem_code", "problem_id", "problem"), ("skill_slug", "skill_id", "skill")),
            ("problem_id", "skill_id", "relation_type", "role"),
            ["relation_type", "role", "required_level", "importance"],
        ),
        (
            "problem_pedagogy",
            "problem_pedagogy",
            (("problem_code", "problem_id", "problem"),),
            ("problem_id",),
            sorted(AXES) + ["number_of_steps", "prerequisite_depth", "estimated_contest_level"],
        ),
    )
    for section, table, references, keys, attributes in specs:
        columns = (
            [column for _, column, _ in references]
            + attributes
            + ["source", "confidence", "review_status"]
        )
        for row in manifest[section]:
            values = [lookup[kind][row[field]] for field, _, kind in references]
            values += [row.get(c) for c in attributes + ["source", "confidence", "review_status"]]
            cur.execute(upsert_sql(table, columns, keys), values)


def connection_options() -> dict:
    env_path = Path(os.environ.get("PG_ENV_FILE") or Path(__file__).resolve().parents[1] / ".env")
    env = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    env.update(os.environ)
    return {
        "host": env.get("NEON_PG_HOST", "127.0.0.1"),
        "port": env.get("NEON_PG_PORT") or env.get("PG_PORT", "5433"),
        "dbname": env.get("NEON_PG_DATABASE") or env.get("APP_DB", "mathbank"),
        "user": env.get("NEON_PG_USER") or env.get("APP_USER", "mathbank_app"),
        "password": env.get("NEON_PG_PASSWORD") or env.get("APP_DB_PASSWORD", ""),
        "sslmode": env.get("NEON_PG_SSLMODE", "prefer"),
    }


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ManifestError(f"Duplicate JSON field {key!r}")
        result[key] = value
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "import"])
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--dry-run", action="store_true", help="Read-only DB FK/cycle validation; no mutations"
    )
    args = parser.parse_args()
    try:
        manifest = validate_manifest(
            json.loads(args.manifest.read_text(), object_pairs_hook=unique_object)
        )
        if args.command == "import":
            with psycopg.connect(**connection_options()) as conn, conn.cursor() as cur:
                if args.dry_run:
                    cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                    resolve_manifest(cur, manifest)
                else:
                    require_schema(cur)
                    import_manifest(cur, manifest)
        print(
            json.dumps(
                {
                    "status": "validated"
                    if args.command == "validate" or args.dry_run
                    else "imported",
                    "counts": {key: len(manifest[key]) for key in FORMATS},
                }
            )
        )
    except (ManifestError, json.JSONDecodeError, OSError) as exc:
        parser.exit(2, f"Pedagogy authoring error: {exc}\n")


if __name__ == "__main__":
    main()
