"""Reviewed-release selection and current-step assets, never on-demand decomposition."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text

from mathbank_rest.db.postgres import engine
from mathbank_rest.route_contracts import RouteProgram, program_digest, validate_source
from mathbank_rest.step_runtime import InvalidTransition, NotFound, StateVersionConflict


def select_published(conn, code: str) -> dict | None:
    row = (
        conn.execute(
            text("""
        SELECT r.*, p.canonical_code, s.verification_status
        FROM pedagogy.solution_route_release r JOIN core.problem p USING(problem_id)
        JOIN core.solution s ON s.solution_id=r.solution_id
        WHERE p.canonical_code=:code AND r.status='PUBLISHED'
        ORDER BY r.preferred_for_tutoring DESC, r.route_quality DESC NULLS LAST,
                 r.difficulty_level, r.release_version DESC, r.route_release_id LIMIT 1
    """),
            {"code": code},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def load_program(conn, release_id: str) -> RouteProgram:
    release = (
        conn.execute(
            text("""
        SELECT * FROM pedagogy.solution_route_release WHERE route_release_id=:id
    """),
            {"id": release_id},
        )
        .mappings()
        .one()
    )
    steps = []
    for row in conn.execute(
        text("""
        SELECT s.*, i.content AS instruction FROM pedagogy.route_step s
        JOIN pedagogy.solution_step_instruction i USING(route_release_id,step_index)
        WHERE s.route_release_id=:id ORDER BY step_index
    """),
        {"id": release_id},
    ).mappings():
        index = row["step_index"]
        params = {"id": release_id, "i": index}
        requirements = [
            dict(item)
            for item in conn.execute(
                text("""
            SELECT taxonomy_node_id,role,required_level,importance,blocking
            FROM pedagogy.solution_step_requirement WHERE route_release_id=:id AND step_index=:i
            ORDER BY taxonomy_node_id,role
        """),
                params,
            ).mappings()
        ]
        links = [
            dict(item)
            for item in conn.execute(
                text("""
            SELECT asset_key,role FROM pedagogy.route_asset_link
            WHERE route_release_id=:id AND step_index=:i ORDER BY asset_key,role
        """),
                params,
            ).mappings()
        ]
        hints = list(
            conn.execute(
                text("""
            SELECT hint_text FROM pedagogy.route_step_hint
            WHERE route_release_id=:id AND step_index=:i AND hint_level<=4
              AND hint_variant='default' AND misconception_key='' ORDER BY hint_level
        """),
                params,
            ).scalars()
        )
        steps.append(
            {
                key: row[key]
                for key in (
                    "mathematical_result",
                    "source_quote",
                    "depends_on",
                    "produces",
                    "uses_claims",
                )
            }
            | {
                "instruction": row["instruction"],
                "requirements": requirements,
                "asset_links": links,
                "hints": hints,
            }
        )
    assets = list(
        conn.execute(
            text("""
        SELECT content FROM pedagogy.route_asset WHERE route_release_id=:id ORDER BY asset_key
    """),
            {"id": release_id},
        ).scalars()
    )
    return RouteProgram.model_validate(
        {
            **{
                key: release[key]
                for key in (
                    "approach_name",
                    "approach_summary",
                    "difficulty_level",
                    "conceptual_load",
                    "algebraic_load",
                    "insight_load",
                )
            },
            "steps": steps,
            "assets": assets,
        }
    )


def plan(code: str) -> dict | None:
    with engine.connect() as conn:
        release = select_published(conn, code)
        if not release:
            return None
        steps = list(
            conn.execute(
                text("""
            SELECT content FROM pedagogy.solution_step_instruction
            WHERE route_release_id=:r ORDER BY step_index
        """),
                {"r": release["route_release_id"]},
            ).scalars()
        )
    return {
        "problem_code": code,
        "status": "ready",
        "route_release_id": str(release["route_release_id"]),
        "selected_solution_id": str(release["solution_id"]),
        "rationale": release["approach_summary"],
        "stages": [item["goal_text"] for item in steps],
        "first_checkpoint": steps[0]["student_prompt"],
        "solution_evidence": {
            "status": "available",
            "references_considered": 1,
            "total_records": 1,
            "sources": [
                {
                    "solution_id": str(release["solution_id"]),
                    "verification_status": release["verification_status"],
                }
            ],
        },
        "provenance": {
            "source": "published-route",
            "review_status": "REVIEWED",
            "release_version": release["release_version"],
        },
        "warnings": [],
    }


def coaching(code: str, level: int) -> dict | None:
    """Anonymous compatibility coach is restricted to the opening checkpoint."""
    with engine.connect() as conn:
        release = select_published(conn, code)
        if not release:
            return None
        instruction = conn.execute(
            text("""
            SELECT content FROM pedagogy.solution_step_instruction
            WHERE route_release_id=:r AND step_index=1
        """),
            {"r": release["route_release_id"]},
        ).scalar_one()
        hint = conn.execute(
            text("""
            SELECT hint_text FROM pedagogy.route_step_hint
            WHERE route_release_id=:r AND step_index=1 AND hint_level=:level
              AND hint_variant='default' AND misconception_key=''
        """),
            {"r": release["route_release_id"], "level": level},
        ).scalar_one()
    return {
        "problem_code": code,
        "hint_level": level,
        "hint": hint,
        "micro_lesson": instruction["prerequisite_recap"] or instruction["recognition_cue"],
        "return_prompt": instruction["student_prompt"],
        "route_release_id": str(release["route_release_id"]),
        "current_step": 1,
        "provenance": {"source": "published-hint-library", "review_status": "REVIEWED"},
        "warnings": [],
    }


def review(conn, release_id: UUID, reviewer: str, expected_hash: str) -> dict:
    release = (
        conn.execute(
            text("""
        SELECT r.*, coalesce(nullif(trim(s.body_markdown),''),s.body_latex) AS source,
               p.statement_text,s.verification_status FROM pedagogy.solution_route_release r
        JOIN core.solution s ON s.solution_id=r.solution_id
        JOIN core.problem p ON p.problem_id=r.problem_id
        WHERE r.route_release_id=:id FOR UPDATE OF r FOR SHARE OF s,p
    """),
            {"id": release_id},
        )
        .mappings()
        .first()
    )
    if not release:
        raise NotFound("Route release not found.")
    if release["status"] != "DRAFT" or release["content_hash"] != expected_hash:
        raise StateVersionConflict("Draft status/hash changed; reload before review.")
    program = load_program(conn, str(release_id))
    if program_digest(program) != release["content_hash"]:
        raise StateVersionConflict(
            "Draft content changed without a matching release hash; recompile."
        )
    ids = set(conn.execute(text("SELECT taxonomy_node_id FROM pedagogy.taxonomy_node")).scalars())
    validate_source(program, release["source"], ids)
    from mathbank_rest.route_compiler import source_hash

    if (
        source_hash(dict(release) | {"solution_id": str(release["solution_id"])})
        != release["source_hash"]
    ):
        raise StateVersionConflict("Canonical source changed; recompile before review.")
    conn.execute(
        text("""
        UPDATE pedagogy.solution_route_release SET status='REVIEWED',reviewed_by=:who,reviewed_at=now()
        WHERE route_release_id=:id
    """),
        {"id": release_id, "who": reviewer},
    )
    return {"route_release_id": str(release_id), "status": "REVIEWED"}


def publish(conn, release_id: UUID) -> dict:
    row = conn.execute(
        text("""
        UPDATE pedagogy.solution_route_release SET status='PUBLISHED',published_at=now()
        WHERE route_release_id=:id AND status='REVIEWED' RETURNING route_release_id
    """),
        {"id": release_id},
    ).first()
    if not row:
        raise InvalidTransition("Only a reviewed release can be published.")
    return {
        "route_release_id": str(release_id),
        "status": "PUBLISHED",
        "graph_status": "refresh_required",
    }


def edit(conn, release_id: UUID, expected_hash: str, program: RouteProgram) -> dict:
    from mathbank_rest.route_compiler import write_program

    release = (
        conn.execute(
            text("""
        SELECT r.*,coalesce(nullif(trim(s.body_markdown),''),s.body_latex) AS source
        FROM pedagogy.solution_route_release r JOIN core.solution s ON s.solution_id=r.solution_id
        WHERE r.route_release_id=:id FOR UPDATE OF r
    """),
            {"id": release_id},
        )
        .mappings()
        .first()
    )
    if not release:
        raise NotFound("Route release not found.")
    if release["status"] != "DRAFT" or release["content_hash"] != expected_hash:
        raise StateVersionConflict("Only the current unchanged draft can be edited.")
    ids = set(conn.execute(text("SELECT taxonomy_node_id FROM pedagogy.taxonomy_node")).scalars())
    validate_source(program, release["source"], ids)
    for table in (
        "route_asset_link",
        "solution_step_requirement",
        "route_step_hint",
        "solution_step_instruction",
        "route_step",
        "route_asset",
    ):
        conn.execute(
            text(f"DELETE FROM pedagogy.{table} WHERE route_release_id=:id"), {"id": release_id}
        )
    write_program(conn, str(release_id), program)
    conn.execute(
        text("""
        UPDATE pedagogy.solution_route_release
        SET content_hash=:hash,approach_name=:approach_name,approach_summary=:approach_summary,
            difficulty_level=:difficulty_level,conceptual_load=:conceptual_load,
            algebraic_load=:algebraic_load,insight_load=:insight_load
        WHERE route_release_id=:id
    """),
        {**program.model_dump(), "hash": program_digest(program), "id": release_id},
    )
    return {
        "route_release_id": str(release_id),
        "status": "DRAFT",
        "content_hash": program_digest(program),
    }


def start_attempt(conn, student_id: UUID, code: str, release_id: UUID | None = None) -> dict:
    release = select_published(conn, code)
    if release_id:
        release = (
            conn.execute(
                text("""
            SELECT r.* FROM pedagogy.solution_route_release r JOIN core.problem p USING(problem_id)
            WHERE r.route_release_id=:id AND p.canonical_code=:code AND r.status='PUBLISHED'
        """),
                {"id": release_id, "code": code},
            )
            .mappings()
            .first()
        )
    if not release:
        raise NotFound("No reviewed published route is available for this problem.")
    attempt = (
        conn.execute(
            text("""
        INSERT INTO learner.route_attempt(student_id,route_release_id)
        VALUES (:s,:r) RETURNING *
    """),
            {"s": student_id, "r": release["route_release_id"]},
        )
        .mappings()
        .one()
    )
    return current_view(conn, dict(attempt))


def owned_attempt(conn, student_id: UUID, attempt_id: UUID) -> dict:
    row = (
        conn.execute(
            text("""
        SELECT * FROM learner.route_attempt WHERE route_attempt_id=:id AND student_id=:s FOR UPDATE
    """),
            {"id": attempt_id, "s": student_id},
        )
        .mappings()
        .first()
    )
    if not row:
        raise NotFound("Route attempt not found.")
    return dict(row)


def current_view(conn, attempt: dict) -> dict:
    params = {"r": attempt["route_release_id"], "i": attempt["current_step"]}
    instruction = conn.execute(
        text("""
        SELECT content FROM pedagogy.solution_step_instruction WHERE route_release_id=:r AND step_index=:i
    """),
        params,
    ).scalar()
    return {
        "route_attempt_id": str(attempt["route_attempt_id"]),
        "route_release_id": str(attempt["route_release_id"]),
        "version": attempt["version"],
        "current_step": attempt["current_step"],
        "status": "active" if instruction else "finished",
        "goal": instruction["goal_text"] if instruction else None,
        "student_prompt": instruction["student_prompt"] if instruction else None,
        "tutor_explained_steps": attempt["tutor_explained_steps"],
        "mastery_recorded": False,
    }


def assist(
    conn, student_id: UUID, attempt_id: UUID, version: int, level: int, advance: bool
) -> dict:
    attempt = owned_attempt(conn, student_id, attempt_id)
    if attempt["version"] != version:
        raise StateVersionConflict("Checkpoint changed; reload the route attempt.")
    if advance and level != 5:
        raise InvalidTransition("Explain the current step before moving forward.")
    hint = conn.execute(
        text("""
        SELECT hint_text FROM pedagogy.route_step_hint
        WHERE route_release_id=:r AND step_index=:i AND hint_level=:level
          AND hint_variant='default' AND misconception_key=''
    """),
        {"r": attempt["route_release_id"], "i": attempt["current_step"], "level": level},
    ).scalar()
    if not hint:
        raise NotFound("No reviewed asset is available for this current step.")
    conn.execute(
        text("""
        UPDATE learner.route_attempt SET version=version+1,updated_at=now(),
          tutor_explained_steps=CASE WHEN :advance THEN array_append(tutor_explained_steps,current_step)
                                    ELSE tutor_explained_steps END,
          current_step=current_step+CASE WHEN :advance THEN 1 ELSE 0 END
        WHERE route_attempt_id=:id
    """),
        {"id": attempt_id, "advance": advance},
    )
    updated = owned_attempt(conn, student_id, attempt_id)
    return {
        **current_view(conn, updated),
        "hint": hint,
        "hint_level": level,
        "source": "published-hint-library",
    }
