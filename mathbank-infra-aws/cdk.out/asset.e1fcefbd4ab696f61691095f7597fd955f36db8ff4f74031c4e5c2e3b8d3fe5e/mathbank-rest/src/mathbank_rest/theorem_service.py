"""Theorem/Axiom/Lemma/Proposition/Corollary/Identity/Definition catalog service
(requirements/61). A dedicated module, not an extension of `taxonomy_service.py`'s
generic concept/technique/skill/misconception CRUD — deliberate deviation, documented
here the same way `taxonomy_service.py`'s own docstring explains its deviation from doc
45: a theorem has several rich fields (kind, field, statement_text/_latex, proof_sketch,
a three-state review_status with no separate active/inactive toggle, a prerequisite DAG,
taxonomy links, sources, diagrams) that do not fit the generic name/description/level
CRUD config those four kinds share. `review_status` here is the only lifecycle — there is
no `knowledge.theorem.is_active`/`status` column to layer a second one on top of.

Every relationship below is HAS-A (a join table with a role), never IS-A, per
documentation/requirements/61_THEOREM_AXIOM_LEMMA_CATALOG.md §3 — `kind` is the one true
IS-A in this design, and it lives on the `knowledge.theorem` row itself, not as a
relationship to another table.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from mathbank_rest.math_format import check_latex
from mathbank_rest.micro_course_service import record_audit_event

_KIND_VALUES = {"AXIOM", "THEOREM", "LEMMA", "PROPOSITION", "COROLLARY", "IDENTITY", "DEFINITION"}
_FIELD_VALUES = {
    "ALGEBRA", "GEOMETRY", "NUMBER_THEORY", "COMBINATORICS", "PROBABILITY",
    "ANALYSIS", "LOGIC_AND_SET_THEORY", "OTHER",
}
_RELATION_TYPES = {"DEPENDS_ON", "GENERALIZES", "SPECIAL_CASE_OF", "EQUIVALENT_TO", "COROLLARY_OF"}
# Of these, only DEPENDS_ON and COROLLARY_OF are lineage edges that must stay acyclic and
# must never originate from an AXIOM (doc 61 §7) — GENERALIZES/SPECIAL_CASE_OF/EQUIVALENT_TO
# are cross-references, not prerequisite edges, so they are exempt from both checks.
_LINEAGE_RELATION_TYPES = {"DEPENDS_ON", "COROLLARY_OF"}
_SOURCE_TYPES = {"REFERENCE", "FORMAL_PROOF", "VIDEO", "TEXTBOOK", "OTHER"}
_TAXONOMY_LINK_ROLES = {"PRIMARY", "RELATED"}


class TheoremNotFound(ValueError):
    pass


class TheoremConflict(RuntimeError):
    pass


class TheoremCycle(ValueError):
    """Raised when a proposed theorem_relation edge would create a dependency cycle, or
    would give an AXIOM an outgoing DEPENDS_ON/COROLLARY_OF edge (doc 61 §7)."""


def _required_text(value: str, field: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError(f"{field} is required")
    return value


def _check_latex_fields(**fields: str | None) -> None:
    """Runs the same light structural LaTeX validator already shared with the student
    composer (mathbank_rest.math_format.check_latex) against every text field that may
    contain inline LaTeX. A validation gate, not a renderer (doc 61 §4.1)."""
    problems: list[str] = []
    for field_name, value in fields.items():
        if not value:
            continue
        issues = check_latex(value)
        if issues:
            problems.append(f"{field_name}: {', '.join(issues)}")
    if problems:
        raise ValueError("LaTeX validation failed — " + "; ".join(problems))


def _row_to_dict(row: Any) -> dict:
    result = dict(row)
    for key, value in result.items():
        if key.endswith("_id") and value is not None:
            result[key] = str(value)
    return result


# --------------------------------------------------------------------------- catalog ---

def create_theorem(
    conn,
    *,
    slug: str,
    name: str,
    kind: str,
    field: str,
    statement_text: str,
    statement_latex: str | None = None,
    description: str | None = None,
    proof_sketch: str | None = None,
    source: str = "HUMAN",
    actor: str,
    auto_approve: bool = False,
) -> dict:
    """Creates a PENDING_REVIEW theorem row (or APPROVED immediately if `auto_approve`,
    for the admin-self-authoring UX in doc 61 §8.2 — never set by an agent, see
    approve_theorem's own guardrail)."""
    slug = _required_text(slug, "slug")
    name = _required_text(name, "name")
    statement_text = _required_text(statement_text, "statement_text")
    if kind not in _KIND_VALUES:
        raise ValueError(f"kind must be one of {sorted(_KIND_VALUES)}")
    if field not in _FIELD_VALUES:
        raise ValueError(f"field must be one of {sorted(_FIELD_VALUES)}")
    if source not in {"HUMAN", "LLM_DRAFT", "LLM_REVIEWED"}:
        raise ValueError("source must be HUMAN, LLM_DRAFT, or LLM_REVIEWED")
    _check_latex_fields(
        statement_text=statement_text, statement_latex=statement_latex,
        description=description, proof_sketch=proof_sketch,
    )
    existing = conn.execute(
        text("SELECT 1 FROM knowledge.theorem WHERE slug=:slug"), {"slug": slug}
    ).first()
    if existing is not None:
        raise TheoremConflict(f"a theorem with slug '{slug}' already exists")
    review_status = "APPROVED" if auto_approve else "PENDING_REVIEW"
    approval_method = "human" if auto_approve else None
    row = conn.execute(
        text("""
            INSERT INTO knowledge.theorem
                (slug, name, kind, field, statement_text, statement_latex, description,
                 proof_sketch, source, review_status, approval_method, approved_at)
            VALUES
                (:slug, :name, :kind, :field, :statement_text, :statement_latex, :description,
                 :proof_sketch, :source, :review_status, :approval_method,
                 CASE WHEN :auto_approve THEN now() ELSE NULL END)
            RETURNING *
        """),
        {
            "slug": slug, "name": name, "kind": kind, "field": field,
            "statement_text": statement_text, "statement_latex": statement_latex,
            "description": description, "proof_sketch": proof_sketch, "source": source,
            "review_status": review_status, "approval_method": approval_method,
            "auto_approve": auto_approve,
        },
    ).mappings().one()
    result = _row_to_dict(row)
    record_audit_event(
        conn, "ADMIN", actor, "CREATE", "theorem", result["theorem_id"], after_state=result,
    )
    return result


def update_theorem(conn, slug: str, *, actor: str, **fields: Any) -> dict:
    """Updates mutable fields; `kind`/`slug` are intentionally not updatable here (changing
    a theorem's fundamental kind after creation is a modeling decision significant enough
    to warrant a new row + a theorem_relation edge, not a silent PATCH)."""
    allowed = {
        "name", "field", "statement_text", "statement_latex", "description", "proof_sketch",
    }
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        raise ValueError("no updatable fields supplied")
    if "field" in updates and updates["field"] not in _FIELD_VALUES:
        raise ValueError(f"field must be one of {sorted(_FIELD_VALUES)}")
    _check_latex_fields(**{k: v for k, v in updates.items() if k in (
        "statement_text", "statement_latex", "description", "proof_sketch")})
    existing = get_theorem(conn, slug, include_unapproved=True)
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    row = conn.execute(
        text(f"UPDATE knowledge.theorem SET {set_clause}, updated_at = now() "
             "WHERE slug = :slug RETURNING *"),
        {**updates, "slug": slug},
    ).mappings().one()
    result = _row_to_dict(row)
    record_audit_event(
        conn, "ADMIN", actor, "UPDATE", "theorem", result["theorem_id"],
        before_state=existing, after_state=result,
    )
    return result


def approve_theorem(conn, slug: str, *, actor: str) -> dict:
    """Flips PENDING_REVIEW -> APPROVED. Always a human admin action — never called by
    the Theorem Curator agent itself (doc 61 §10 guardrails)."""
    row = conn.execute(
        text("""
            UPDATE knowledge.theorem
            SET review_status = 'APPROVED', approval_method = 'human', approved_at = now()
            WHERE slug = :slug AND review_status = 'PENDING_REVIEW'
            RETURNING *
        """),
        {"slug": slug},
    ).mappings().one_or_none()
    if row is None:
        existing = conn.execute(
            text("SELECT 1 FROM knowledge.theorem WHERE slug=:slug"), {"slug": slug}
        ).first()
        if existing is None:
            raise TheoremNotFound(f"theorem '{slug}' not found")
        raise TheoremConflict(f"theorem '{slug}' is not PENDING_REVIEW")
    result = _row_to_dict(row)
    record_audit_event(conn, "ADMIN", actor, "APPROVE", "theorem", result["theorem_id"], after_state=result)
    return result


def reject_theorem(conn, slug: str, *, actor: str, reason: str | None = None) -> dict:
    row = conn.execute(
        text("""
            UPDATE knowledge.theorem SET review_status = 'REJECTED'
            WHERE slug = :slug AND review_status = 'PENDING_REVIEW'
            RETURNING *
        """),
        {"slug": slug},
    ).mappings().one_or_none()
    if row is None:
        raise TheoremNotFound(f"theorem '{slug}' not found or not PENDING_REVIEW")
    result = _row_to_dict(row)
    record_audit_event(
        conn, "ADMIN", actor, "REJECT", "theorem", result["theorem_id"],
        after_state={**result, "reason": reason},
    )
    return result


def get_theorem(conn, slug: str, *, include_unapproved: bool = False) -> dict:
    """Full detail: the theorem row plus its sources, diagrams and taxonomy links.
    `include_unapproved=False` (the default, used by every student-facing/agent-facing
    read) restricts both the theorem row itself and every nested source/asset row to
    APPROVED only — a PENDING_REVIEW theorem is invisible to students regardless of how
    it is reached (doc 61 §12.1)."""
    where = "slug = :slug" if include_unapproved else "slug = :slug AND review_status = 'APPROVED'"
    row = conn.execute(
        text(f"SELECT * FROM knowledge.theorem WHERE {where}"), {"slug": slug}
    ).mappings().one_or_none()
    if row is None:
        raise TheoremNotFound(f"theorem '{slug}' not found")
    result = _row_to_dict(row)
    source_filter = "" if include_unapproved else "AND review_status = 'APPROVED'"
    sources = conn.execute(
        text(f"""
            SELECT theorem_source_id, url, label, source_type, ordinal, review_status
            FROM knowledge.theorem_source
            WHERE theorem_id = :tid {source_filter}
            ORDER BY ordinal, created_at
        """),
        {"tid": result["theorem_id"]},
    ).mappings()
    result["sources"] = [_row_to_dict(s) for s in sources]
    assets = conn.execute(
        text("""
            SELECT ta.asset_id, ta.ordinal, ta.caption, a.uri, a.mime_type
            FROM knowledge.theorem_asset ta JOIN visual.asset a ON a.asset_id = ta.asset_id
            WHERE ta.theorem_id = :tid
            ORDER BY ta.ordinal
        """),
        {"tid": result["theorem_id"]},
    ).mappings()
    result["assets"] = [_row_to_dict(a) for a in assets]
    links = conn.execute(
        text("""
            SELECT tl.taxonomy_node_id, tl.role, tn.node_type, tn.name
            FROM knowledge.theorem_taxonomy_link tl JOIN pedagogy.taxonomy_node tn
                ON tn.taxonomy_node_id = tl.taxonomy_node_id
            WHERE tl.theorem_id = :tid
            ORDER BY tl.role, tn.name
        """),
        {"tid": result["theorem_id"]},
    ).mappings()
    result["taxonomy_links"] = [dict(link) for link in links]
    return result


def list_theorems(
    conn, *, q: str = "", kind: str = "", field: str = "", review_status: str = "ALL",
    limit: int = 50, offset: int = 0,
) -> dict:
    if limit < 1 or limit > 200 or offset < 0:
        raise ValueError("limit must be 1..200 and offset must be non-negative")
    where = ["1=1"]
    params: dict[str, Any] = {"q": f"%{q}%", "limit": limit, "offset": offset}
    if q:
        where.append("(name ILIKE :q OR statement_text ILIKE :q OR description ILIKE :q)")
    if kind:
        if kind not in _KIND_VALUES:
            raise ValueError(f"kind must be one of {sorted(_KIND_VALUES)}")
        where.append("kind = :kind")
        params["kind"] = kind
    if field:
        if field not in _FIELD_VALUES:
            raise ValueError(f"field must be one of {sorted(_FIELD_VALUES)}")
        where.append("field = :field")
        params["field"] = field
    if review_status != "ALL":
        where.append("review_status = :review_status")
        params["review_status"] = review_status
    rows = conn.execute(
        text(f"""
            SELECT theorem_id, slug, name, kind, field, review_status, created_at
            FROM knowledge.theorem
            WHERE {" AND ".join(where)}
            ORDER BY name
            LIMIT :limit OFFSET :offset
        """),
        params,
    ).mappings()
    return {"items": [_row_to_dict(r) for r in rows]}


# -------------------------------------------------------------------- lineage / DAG ---

def _lineage_path_exists(conn, start_id: str, target_id: str) -> bool:
    """True if `target_id` is reachable from `start_id` by walking existing
    DEPENDS_ON/COROLLARY_OF edges — used to reject an edge that would create a cycle
    before it is ever written (doc 61 §7)."""
    row = conn.execute(
        text("""
            WITH RECURSIVE walk(theorem_id) AS (
                SELECT to_theorem_id FROM knowledge.theorem_relation
                WHERE from_theorem_id = :start_id
                  AND relation_type = ANY(:lineage_types)
                UNION
                SELECT tr.to_theorem_id FROM knowledge.theorem_relation tr
                JOIN walk w ON tr.from_theorem_id = w.theorem_id
                WHERE tr.relation_type = ANY(:lineage_types)
            )
            SELECT 1 FROM walk WHERE theorem_id = :target_id
        """),
        {"start_id": start_id, "target_id": target_id, "lineage_types": list(_LINEAGE_RELATION_TYPES)},
    ).first()
    return row is not None


def add_theorem_relation(
    conn, *, from_slug: str, to_slug: str, relation_type: str,
    assertion_source: str, confidence: float | None = None, actor: str,
) -> dict:
    if relation_type not in _RELATION_TYPES:
        raise ValueError(f"relation_type must be one of {sorted(_RELATION_TYPES)}")
    from_row = get_theorem(conn, from_slug, include_unapproved=True)
    to_row = get_theorem(conn, to_slug, include_unapproved=True)
    if from_row["theorem_id"] == to_row["theorem_id"]:
        raise ValueError("a theorem cannot relate to itself")
    if relation_type in _LINEAGE_RELATION_TYPES:
        if from_row["kind"] == "AXIOM":
            raise TheoremCycle(
                f"'{from_slug}' is an AXIOM and cannot depend on anything — "
                "axioms are roots of the lineage DAG (doc 61 §7)"
            )
        # Reversing the direction we are about to add: would walking forward from
        # to_row already reach from_row? If so, adding from_row -> to_row closes a cycle.
        if _lineage_path_exists(conn, to_row["theorem_id"], from_row["theorem_id"]):
            raise TheoremCycle(
                f"adding '{from_slug}' {relation_type} '{to_slug}' would create a "
                "dependency cycle"
            )
    row = conn.execute(
        text("""
            INSERT INTO knowledge.theorem_relation
                (from_theorem_id, to_theorem_id, relation_type, assertion_source, confidence)
            VALUES (:from_id, :to_id, :relation_type, :assertion_source, :confidence)
            ON CONFLICT (from_theorem_id, to_theorem_id, relation_type) DO NOTHING
            RETURNING *
        """),
        {
            "from_id": from_row["theorem_id"], "to_id": to_row["theorem_id"],
            "relation_type": relation_type, "assertion_source": assertion_source,
            "confidence": confidence,
        },
    ).mappings().one_or_none()
    if row is None:
        raise TheoremConflict(f"this relation already exists ({from_slug} {relation_type} {to_slug})")
    result = _row_to_dict(row)
    record_audit_event(conn, "ADMIN", actor, "CREATE", "theorem_relation", result["relation_id"], after_state=result)
    return result


def get_theorem_prerequisites(conn, slug: str, *, max_depth: int = 4, include_unapproved: bool = True) -> dict:
    """Walks DEPENDS_ON/COROLLARY_OF edges back toward axioms, up to max_depth hops —
    the lineage chain for "why is this actually true" (doc 61 §7/§11). The student-facing
    router (doc 61 §12.1) passes `include_unapproved=False` so a PENDING_REVIEW
    prerequisite never leaks into a student's view, even nested inside an otherwise
    APPROVED theorem's lineage."""
    if max_depth < 1 or max_depth > 10:
        raise ValueError("max_depth must be 1..10")
    theorem = get_theorem(conn, slug, include_unapproved=include_unapproved)
    review_filter = "" if include_unapproved else "AND t.review_status = 'APPROVED'"
    rows = conn.execute(
        text(f"""
            WITH RECURSIVE walk(theorem_id, depth, path) AS (
                SELECT tr.to_theorem_id, 1, ARRAY[tr.from_theorem_id, tr.to_theorem_id]
                FROM knowledge.theorem_relation tr
                WHERE tr.from_theorem_id = :start_id
                  AND tr.relation_type = ANY(:lineage_types)
                UNION ALL
                SELECT tr.to_theorem_id, w.depth + 1, w.path || tr.to_theorem_id
                FROM knowledge.theorem_relation tr
                JOIN walk w ON tr.from_theorem_id = w.theorem_id
                WHERE tr.relation_type = ANY(:lineage_types)
                  AND w.depth < :max_depth
                  AND NOT tr.to_theorem_id = ANY(w.path)
            )
            SELECT DISTINCT w.depth, t.theorem_id, t.slug, t.name, t.kind
            FROM walk w JOIN knowledge.theorem t ON t.theorem_id = w.theorem_id
            WHERE 1=1 {review_filter}
            ORDER BY w.depth, t.name
        """),
        {"start_id": theorem["theorem_id"], "lineage_types": list(_LINEAGE_RELATION_TYPES), "max_depth": max_depth},
    ).mappings()
    return {"theorem": {"slug": theorem["slug"], "name": theorem["name"]}, "prerequisites": [_row_to_dict(r) for r in rows]}


def list_theorem_relations(conn, slug: str) -> dict:
    theorem = get_theorem(conn, slug, include_unapproved=True)
    rows = conn.execute(
        text("""
            SELECT tr.relation_type, tr.review_status, tr.confidence,
                   t.slug AS to_slug, t.name AS to_name, t.kind AS to_kind
            FROM knowledge.theorem_relation tr JOIN knowledge.theorem t ON t.theorem_id = tr.to_theorem_id
            WHERE tr.from_theorem_id = :tid
            ORDER BY tr.relation_type, t.name
        """),
        {"tid": theorem["theorem_id"]},
    ).mappings()
    return {"items": [dict(r) for r in rows]}


# ---------------------------------------------------------------- technique linkage ---

def add_technique_theorem(
    conn, *, technique_slug: str, theorem_slug: str, role: str = "JUSTIFIES",
    assertion_source: str, confidence: float | None = None, actor: str,
) -> dict:
    if role not in {"JUSTIFIES", "APPLIES"}:
        raise ValueError("role must be JUSTIFIES or APPLIES")
    technique = conn.execute(
        text("SELECT technique_id FROM knowledge.technique WHERE slug=:slug"), {"slug": technique_slug}
    ).mappings().one_or_none()
    if technique is None:
        raise TheoremNotFound(f"technique '{technique_slug}' not found")
    theorem = get_theorem(conn, theorem_slug, include_unapproved=True)
    row = conn.execute(
        text("""
            INSERT INTO knowledge.technique_theorem (technique_id, theorem_id, role, assertion_source, confidence)
            VALUES (:technique_id, :theorem_id, :role, :assertion_source, :confidence)
            ON CONFLICT (technique_id, theorem_id, role) DO NOTHING
            RETURNING *
        """),
        {
            "technique_id": technique["technique_id"], "theorem_id": theorem["theorem_id"],
            "role": role, "assertion_source": assertion_source, "confidence": confidence,
        },
    ).mappings().one_or_none()
    if row is None:
        raise TheoremConflict(f"'{technique_slug}' already {role} '{theorem_slug}'")
    result = _row_to_dict(row)
    record_audit_event(conn, "ADMIN", actor, "CREATE", "technique_theorem",
                        f"{result['technique_id']}:{result['theorem_id']}", after_state=result)
    return result


def get_theorems_for_technique(conn, technique_slug: str) -> dict:
    """Theorems a technique relies on — the HAS-A edge consumed transitively by step/hint
    grounding (doc 61 §11/§13.3) without needing a direct per-step citation."""
    rows = conn.execute(
        text("""
            SELECT t.slug, t.name, t.kind, tt.role
            FROM knowledge.technique_theorem tt
            JOIN knowledge.technique tc ON tc.technique_id = tt.technique_id
            JOIN knowledge.theorem t ON t.theorem_id = tt.theorem_id
            WHERE tc.slug = :slug AND t.review_status = 'APPROVED'
            ORDER BY tt.role, t.name
        """),
        {"slug": technique_slug},
    ).mappings()
    return {"items": [dict(r) for r in rows]}


# ----------------------------------------------------------------- taxonomy linkage ---

def add_theorem_taxonomy_link(
    conn, *, theorem_slug: str, taxonomy_node_id: str, role: str = "PRIMARY", actor: str,
) -> dict:
    if role not in _TAXONOMY_LINK_ROLES:
        raise ValueError(f"role must be one of {sorted(_TAXONOMY_LINK_ROLES)}")
    theorem = get_theorem(conn, theorem_slug, include_unapproved=True)
    node = conn.execute(
        text("SELECT 1 FROM pedagogy.taxonomy_node WHERE taxonomy_node_id=:id"), {"id": taxonomy_node_id}
    ).first()
    if node is None:
        raise TheoremNotFound(f"taxonomy node '{taxonomy_node_id}' not found")
    row = conn.execute(
        text("""
            INSERT INTO knowledge.theorem_taxonomy_link (theorem_id, taxonomy_node_id, role)
            VALUES (:theorem_id, :node_id, :role)
            ON CONFLICT (theorem_id, taxonomy_node_id) DO UPDATE SET role = EXCLUDED.role
            RETURNING *
        """),
        {"theorem_id": theorem["theorem_id"], "node_id": taxonomy_node_id, "role": role},
    ).mappings().one()
    result = _row_to_dict(row)
    record_audit_event(conn, "ADMIN", actor, "LINK", "theorem_taxonomy_link",
                        f"{result['theorem_id']}:{taxonomy_node_id}", after_state=result)
    return result


def list_theorems_for_taxonomy_node(conn, taxonomy_node_id: str) -> dict:
    """Theorems linked to one concept/subconcept/domain/skill/technique, PRIMARY first
    — the browsing entry point for doc 61 §12.1's `GET /v1/taxonomy/{kind}/{code}/theorems`."""
    rows = conn.execute(
        text("""
            SELECT t.slug, t.name, t.kind, t.field, tl.role
            FROM knowledge.theorem_taxonomy_link tl JOIN knowledge.theorem t ON t.theorem_id = tl.theorem_id
            WHERE tl.taxonomy_node_id = :node_id AND t.review_status = 'APPROVED'
            ORDER BY CASE tl.role WHEN 'PRIMARY' THEN 0 ELSE 1 END, t.name
        """),
        {"node_id": taxonomy_node_id},
    ).mappings()
    return {"items": [dict(r) for r in rows]}


# --------------------------------------------------------------------------- sources ---

def add_theorem_source(
    conn, *, theorem_slug: str, url: str, label: str, source_type: str = "REFERENCE",
    added_by: str, review_status: str = "PENDING_REVIEW", ordinal: int | None = None,
) -> dict:
    """Any number of source links per theorem (doc 61 §4.9) — citation URL + a short
    admin-entered label only, never the source's full text (documentation/CREDITS.md)."""
    if source_type not in _SOURCE_TYPES:
        raise ValueError(f"source_type must be one of {sorted(_SOURCE_TYPES)}")
    if review_status not in {"PENDING_REVIEW", "APPROVED", "REJECTED"}:
        raise ValueError("review_status must be PENDING_REVIEW, APPROVED, or REJECTED")
    url = _required_text(url, "url")
    label = _required_text(label, "label")
    theorem = get_theorem(conn, theorem_slug, include_unapproved=True)
    if ordinal is None:
        ordinal = conn.execute(
            text("SELECT COALESCE(MAX(ordinal), 0) + 1 FROM knowledge.theorem_source WHERE theorem_id=:tid"),
            {"tid": theorem["theorem_id"]},
        ).scalar_one()
    row = conn.execute(
        text("""
            INSERT INTO knowledge.theorem_source
                (theorem_id, url, label, source_type, ordinal, added_by, review_status)
            VALUES (:theorem_id, :url, :label, :source_type, :ordinal, :added_by, :review_status)
            ON CONFLICT (theorem_id, url) DO NOTHING
            RETURNING *
        """),
        {
            "theorem_id": theorem["theorem_id"], "url": url, "label": label,
            "source_type": source_type, "ordinal": ordinal, "added_by": added_by,
            "review_status": review_status,
        },
    ).mappings().one_or_none()
    if row is None:
        raise TheoremConflict(f"source '{url}' is already attached to '{theorem_slug}'")
    return _row_to_dict(row)


def approve_theorem_source(conn, theorem_source_id: str, *, actor: str) -> dict:
    row = conn.execute(
        text("""
            UPDATE knowledge.theorem_source SET review_status = 'APPROVED'
            WHERE theorem_source_id = :id AND review_status = 'PENDING_REVIEW'
            RETURNING *
        """),
        {"id": theorem_source_id},
    ).mappings().one_or_none()
    if row is None:
        raise TheoremNotFound(f"source '{theorem_source_id}' not found or not PENDING_REVIEW")
    result = _row_to_dict(row)
    record_audit_event(conn, "ADMIN", actor, "APPROVE", "theorem_source", result["theorem_source_id"], after_state=result)
    return result


# -------------------------------------------------------------------------- diagrams ---

def add_theorem_asset(
    conn, *, theorem_slug: str, asset_id: str, caption: str | None = None, ordinal: int | None = None,
) -> dict:
    """Attaches an already-uploaded/rendered visual.asset row as a diagram (doc 61 §4.5)
    — the asset itself (upload, geometry-scene render, or Manim render) is created
    through its own existing pipeline; this just links it to the theorem."""
    theorem = get_theorem(conn, theorem_slug, include_unapproved=True)
    asset = conn.execute(text("SELECT 1 FROM visual.asset WHERE asset_id=:id"), {"id": asset_id}).first()
    if asset is None:
        raise TheoremNotFound(f"asset '{asset_id}' not found")
    if ordinal is None:
        ordinal = conn.execute(
            text("SELECT COALESCE(MAX(ordinal), 0) + 1 FROM knowledge.theorem_asset WHERE theorem_id=:tid"),
            {"tid": theorem["theorem_id"]},
        ).scalar_one()
    row = conn.execute(
        text("""
            INSERT INTO knowledge.theorem_asset (theorem_id, asset_id, ordinal, caption)
            VALUES (:theorem_id, :asset_id, :ordinal, :caption)
            ON CONFLICT (theorem_id, asset_id) DO UPDATE SET caption = EXCLUDED.caption
            RETURNING *
        """),
        {"theorem_id": theorem["theorem_id"], "asset_id": asset_id, "ordinal": ordinal, "caption": caption},
    ).mappings().one()
    return _row_to_dict(row)


# ----------------------------------------------------------------- dedup / search ---

def search_theorems(
    conn, q: str, *, field: str = "", kind: str = "", limit: int = 10, include_unapproved: bool = False,
) -> dict:
    """Lexical hybrid-search-before-insertion candidate list (doc 61 §9): full-text rank
    on statement_text/name/description, blended with a trigram-style ILIKE fallback so a
    short or oddly-phrased query still surfaces candidates. Semantic (pgvector) ranking
    is a deliberate follow-up (THM-2's embedding half) — this lexical pass alone is
    already what the mandatory dedup gate (doc 61 §8.3) needs to catch the common case of
    a near-identical name/statement."""
    q = _required_text(q, "q")
    where = ["1=1"] if include_unapproved else ["review_status = 'APPROVED'"]
    params: dict[str, Any] = {"q": q, "ilike_q": f"%{q}%", "limit": limit}
    if field:
        if field not in _FIELD_VALUES:
            raise ValueError(f"field must be one of {sorted(_FIELD_VALUES)}")
        where.append("field = :field")
        params["field"] = field
    if kind:
        if kind not in _KIND_VALUES:
            raise ValueError(f"kind must be one of {sorted(_KIND_VALUES)}")
        where.append("kind = :kind")
        params["kind"] = kind
    rows = conn.execute(
        text(f"""
            SELECT theorem_id, slug, name, kind, field, review_status,
                   ts_rank_cd(
                       to_tsvector('english', name || ' ' || statement_text || ' ' || coalesce(description, '')),
                       websearch_to_tsquery('english', :q)
                   ) AS lexical_rank
            FROM knowledge.theorem
            WHERE {" AND ".join(where)}
              AND (
                    to_tsvector('english', name || ' ' || statement_text || ' ' || coalesce(description, ''))
                        @@ websearch_to_tsquery('english', :q)
                    OR name ILIKE :ilike_q
              )
            ORDER BY lexical_rank DESC, name
            LIMIT :limit
        """),
        params,
    ).mappings()
    return {"items": [_row_to_dict(r) for r in rows]}
