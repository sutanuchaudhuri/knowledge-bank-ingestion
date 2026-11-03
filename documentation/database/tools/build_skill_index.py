"""Build the lookup indexes used by the mathbank-db skill from generated/catalog.json and the
hand-verified schemas/*.md files. Writes .github/skills/mathbank-db/references/{TABLE_INDEX,
ENDPOINT_INDEX,MIGRATION_INDEX}.md. Run after editing schemas/*.md or regenerating the catalog:
    python3 documentation/database/tools/build_skill_index.py
"""
import collections, glob, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.normpath(os.path.join(DOCS, "../.."))
OUT = os.path.join(ROOT, ".github/skills/mathbank-db/references")
REL = "../../../../documentation/database/schemas/"  # from references/ to schemas/
cat = json.load(open(os.path.join(DOCS, "generated/catalog.json")))

TYPES = [  # guide §4 table types, matched case-insensitively against the table's own section
    ("Catalogue entity", r"catalog(ue)? entity"),
    ("Revisioned authoring", r"revisioned authoring"),
    ("Release / snapshot", r"release ?/ ?snapshot"),
    ("Junction / link", r"junction ?/ ?link"),
    ("Learner event (append-only)", r"learner event|append-only evidence|event ?/ ?evidence"),
    ("Learner working state", r"learner working state"),
    ("Queue / job / run", r"queue ?/ ?job"),
    ("Derived / cache", r"derived ?/ ?cache|derived, rebuildable|derived/cache"),
    ("Audit", r"\baudit\b table type|type[^.\n]{0,20}\baudit\b"),
]
# Types for tables whose schema doc has no explicit "Table type" line; shown with "*" (inferred).
_T = {"Catalogue entity": "core.competition core.competition_edition core.paper core.problem core.problem_image core.solution core.solution_step",
      "Revisioned authoring": "authoring.plan_topic authoring.presentation_plan authoring.proposed_patch ingest.corpus_draft orchestration.socratic_workflow orchestration.socratic_strategy",
      "Release / snapshot": "orchestration.socratic_revision pedagogy.route_asset pedagogy.route_asset_link pedagogy.route_step pedagogy.route_step_hint pedagogy.solution_step_instruction pedagogy.solution_step_requirement quiz.question quiz.solution",
      "Junction / link": "quiz.question_concept quiz.question_skill quiz.question_technique quiz.question_source",
      "Learner event (append-only)": "attempt_media.approval attempt_media.event attempt_media.evidence_region attempt_media.media_asset attempt_media.step_assessment attempt_media.step_candidate attempt_media.step_candidate_evidence attempt_media.submission attempt_media.transcription_candidate learner.misconception_evidence pedagogy.gap_diagnosis pedagogy.knowledge_gap quiz.response quiz.response_event",
      "Append-only event / log": "authoring.chat_message ingest.admin_review_action ingest.package_status_event orchestration.socratic_command orchestration.socratic_preview_event pedagogy.micro_course_review quiz.generation_event",
      "Learner working state": "authoring.chat_session live.participant notification.event quiz.paper quiz.response_draft tutor.micro_course_runtime tutor.runtime_state",
      "Queue / job / run": "ingest.content_package ingest.package_file ingest.import_conflict ingest.reconciliation ingest.staging_row live.recommendation live.topic_run orchestration.socratic_preview pipeline.outbox_event pipeline.outbox_consumption studio.scene_research_job studio.video_render_job",
      "Derived / cache": "analytics.learner_daily_activity artifact_runtime.validation_result attempt_media.approved_step attempt_media.approved_step_evidence attempt_media.step_alignment attempt_media.visual_explanation live.command_receipt geometry_scene.receipts quiz.exam_diagnosis quiz.question_pool",
      "Audit": "audit.action_log"}
TYPE_OVERRIDES = {k: t for t, ks in _T.items() for k in ks.split()}
VERB = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/[^\s;,`|]*)")


_EP = json.load(open(os.path.join(DOCS, "generated/endpoints.json")))
REAL = [(e["method"], e["path"]) for e in _EP]
EPS = {(e["method"], e["path"]): e for e in _EP}
FILE_PREFIX = {"attempt_media.md": "/v1/attempt-media"}
# Schemas whose DDL lives outside mathbank-db/sql (not in catalog.json); indexed from their schema doc.
EXTERNAL_MIGRATIONS = {"geometry_scene": "mathbank-rest/src/mathbank_rest/migrations/026_geometry_scenes.sql"}
SHORTHAND = [("/admin/mc", "/v1/admin/micro-courses"), ("/mc", "/v1/micro-courses")]  # pedagogy-micro-courses.md legend
TOKEN = re.compile(r"^`?(?:(GET|POST|PUT|PATCH|DELETE)\s+)?`?(\u2026?/[^\s`()]*)")


def norm(p):
    return re.sub(r"\{[^}]*\}", "{}", p).rstrip("/")


def _seg_eq(a, b):
    return a == b or a.startswith("{") or b.startswith("{")


def match_real(verb, p, prefix=None):
    """Segment-wise match ({param} matches any literal); prefer exact length, then a unique suffix match."""
    d = p.lstrip("\u2026").strip("/").split("/")
    exact, suf = set(), set()
    for v, r in REAL:
        if v != verb or (prefix and not r.startswith(prefix)):
            continue
        rs = r.strip("/").split("/")
        if len(rs) == len(d) and all(_seg_eq(x, y) for x, y in zip(rs, d)):
            exact.add(r)
        elif len(rs) > len(d) and all(_seg_eq(x, y) for x, y in zip(rs[-len(d):], d)):
            suf.add(r)
    lit = [r for r in exact if norm(r) == norm(p)]
    if lit:
        return lit[0]
    if exact:
        return min(exact, key=lambda r: (r.count("{"), r))
    if len(suf) == 1:
        return suf.pop()
    return suf or None  # ambiguous: caller disambiguates with file context


def _common(a, b):
    n = 0
    for x, y in zip(a.split("/"), b.split("/")):
        if x != y:
            break
        n += 1
    return n


def pick(cands, ctx):
    scored = sorted(((max((_common(c, x) for x in ctx), default=0), c) for c in cands), reverse=True)
    if scored and scored[0][0] >= 3 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        return scored[0][1]
    return None


def resolve_cell(cell, fname, ctx):
    """Expand doc shorthand ("/admin/mc", "queue · POST /review · /edit", "\u2026/assets") to real routes."""
    ok, bad, verb, base = [], [], None, None
    prefix = FILE_PREFIX.get(fname)
    for tok in re.split(r"\s*(?:;|\u00b7|,|\band\b)\s*", cell):
        m = TOKEN.match(tok.strip())
        if not m:
            continue
        verb = m.group(1) or verb
        raw = m.group(2).split("?")[0]
        opt = re.search(r"\[(/[^\]]*)\]", raw)  # "/attempts/{id}[/runtime]" documents two routes
        variants = [raw.replace(opt.group(0), ""), raw.replace(opt.group(0), opt.group(1))] if opt else [raw]
        for p in variants:
            p = p.replace("[", "").replace("]", "").rstrip(".)\u2026:")
            if not verb or p in ("", "/", "\u2026"):
                continue
            if fname == "pedagogy-micro-courses.md":
                for a, b in SHORTHAND:
                    if p == a or p.startswith(a + "/"):
                        p = b + p[len(a):]
                        break
            cands = [p] if p.startswith("/v1/") else [c for c in (base and base + p.lstrip("\u2026"), prefix and prefix + p.lstrip("\u2026"), p) if c]
            real = None
            for c in cands:
                r = match_real(verb, c, None if c.startswith("/v1/") else prefix)
                real = pick(r, ctx) if isinstance(r, set) else r
                if real:
                    break
            if real:
                ok.append((verb, real))
                ctx.append(real)
                base = real.rsplit("/", 1)[0]
            elif p.startswith("/v1/"):
                ok.append((verb, p))  # documented, but not in the mathbank-rest route table (e.g. manim-studio)
                base = p.rsplit("/", 1)[0]
            else:
                bad.append(f"{verb} {p}")
    return {"ok": ok, "bad": bad}


def slug(heading):
    s = heading.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


def cells(row):
    return [c.strip() for c in row.strip().strip("|").split("|")]


tables = {}  # key -> dict(file, anchor, type, routes[], other[])
for path in sorted(glob.glob(os.path.join(DOCS, "schemas/*.md"))):
    fname = os.path.basename(path)
    text = open(path).read()
    # context for disambiguating "…/publish"-style suffixes: every full route literally named in this file
    file_ctx = []
    scan = text
    if fname == "pedagogy-micro-courses.md":
        scan = re.sub(r"(?<=[\s`])/admin/mc(?=[/\s`;,|]|$)", "/v1/admin/micro-courses", scan)
        scan = re.sub(r"(?<=[\s`])/mc(?=[/\s`;,|]|$)", "/v1/micro-courses", scan)
    for v_, p_ in re.findall(r"\b(GET|POST|PUT|PATCH|DELETE)\s+`?(/v1/[^\s`;,|()?]*)", scan):
        r_ = match_real(v_, p_.rstrip(".:"))
        if isinstance(r_, str):
            file_ctx.append(r_)
    sec4 = text.split("\n## 4.", 1)[1] if "\n## 4." in text else ""
    sec3 = text.split("\n## 3.", 1)[1].split("\n## 4.", 1)[0] if "\n## 3." in text else text
    parts = re.split(r"^(### (?:View )?`([a-z_]+\.[a-z_0-9]+)`.*)$", sec3, flags=re.M)
    for i in range(1, len(parts), 3):
        heading, key, body = parts[i], parts[i + 1], parts[i + 2].split("\n## ", 1)[0]
        if key not in cat:  # schema created outside mathbank-db/sql (e.g. geometry_scene): stub from the doc
            ncols = 0
            if "| Column |" in body:
                rows = body.split("| Column |", 1)[1].split("\n\n", 1)[0].splitlines()[2:]
                ncols = sum(1 for r in rows if r.startswith("|"))
            cat[key] = dict(schema=key.split(".")[0], kind="view" if heading.startswith("### View") else "table",
                            migration=EXTERNAL_MIGRATIONS.get(key.split(".")[0], "see doc"), columns=[None] * ncols,
                            columns_added_by={})
        ttype = "—"
        short = key.split(".", 1)[1]
        matrix_rows = [l for l in sec4.splitlines() if l.startswith("|") and re.search(rf"`?(\b{re.escape(key)}\b|\b{re.escape(short)}\b)`?", l.split("|")[1] if l.count("|") > 1 else "")]
        for scope in (body[:1500], " ".join(matrix_rows)):
            hit = next((n for n, p in TYPES if re.search(p, scope, re.I)), None)
            if hit:
                ttype = hit
                break
        routes, other = [], []
        m = re.search(r"\*\*REST operations today\.?\*\*(.*?)(?=\n\*\*|\n### |\Z)", body, re.S)
        if m:
            for line in m.group(1).splitlines():
                if not line.startswith("|") or set(line) <= set("|- :") or "Method & path" in line:
                    continue
                c = cells(line)
                if len(c) < 3:
                    continue
                op, mp, auth = c[0], c[1], c[2]
                handler = c[3] if len(c) > 3 else ""
                found = resolve_cell(mp, fname, file_ctx)
                for verb, rp in found["ok"]:
                    routes.append((verb, rp, op, auth, handler))
                for frag in found["bad"]:
                    other.append(f"{op}: {frag} (unresolved, see doc)")
                if found["ok"] or found["bad"]:
                    continue
                if mp and mp.lower() not in ("none", "none.", "—"):
                    other.append(re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", f"{op}: {mp}")[:160])
        if ttype == "—" and key in TYPE_OVERRIDES:
            ttype = TYPE_OVERRIDES[key] + " *"
        tables[key] = dict(file=fname, anchor=slug(heading[4:]), type=ttype, routes=routes, other=other)

os.makedirs(OUT, exist_ok=True)
md = lambda s: s.replace("|", "\\|")

# TABLE_INDEX.md
by_schema = collections.defaultdict(list)
for k in sorted(cat):
    by_schema[cat[k]["schema"]].append(k)
L = ["# Table index — every PostgreSQL table/view → doc section, migration, type, REST callers", "",
     "Generated by [build_skill_index.py](../../../../documentation/database/tools/build_skill_index.py) "
     "from `generated/catalog.json` and the verified \"REST operations today\" tables in "
     "[documentation/database/schemas/](../../../../documentation/database/schemas/). "
     "Type = REST_CRUD_DESIGN_GUIDE §4 table type (matched from the doc; `*` = inferred because the doc has no explicit type line). "
     "Routes are deduplicated `VERB path` (ops C/R/U/D); open the doc section for auth, handler and notes.", ""]
for s in sorted(by_schema):
    L += [f"## `{s}`", "", "| Table | Doc | Created in | Cols | Type | REST callers (verified) | Non-REST readers/writers |", "|---|---|---|---:|---|---|---|"]
    for k in by_schema[s]:
        v, t = cat[k], tables.get(k)
        kind = " (view)" if v["kind"] != "table" else ""
        mig = v.get("migration") or "?"
        added = sorted(set((v.get("columns_added_by") or {}).values()) - {mig})
        mig_s = (f"[external]({'../../../../' + mig})" if "/" in mig else mig.split("_")[0]) + (" +" + ",".join(a.split("_")[0] for a in added) if added else "")
        if t:
            doc = f"[{t['file']}]({REL}{t['file']}#{t['anchor']})"
            seen, rs = set(), []
            for verb, p, op, auth, _ in t["routes"]:
                if (verb, p) not in seen:
                    seen.add((verb, p))
                    rs.append(f"{op} `{verb} {p}`")
            rest = "<br>".join(rs) or "none"
            oth = "<br>".join(md(o) for o in t["other"][:4]) or "—"
            ttype = t["type"]
        else:
            doc, rest, oth, ttype = "(undocumented)", "?", "?", "?"
        L.append(f"| `{k}`{kind} | {doc} | {mig_s} | {len(v['columns'])} | {ttype} | {md(rest).replace(chr(92)+'|','|')} | {oth} |")
    L.append("")
open(os.path.join(OUT, "TABLE_INDEX.md"), "w").write("\n".join(L))

# ENDPOINT_INDEX.md
ep = collections.defaultdict(lambda: dict(tables=collections.defaultdict(set), auth=set(), handler=set()))
for k, t in tables.items():
    for verb, p, op, auth, handler in t["routes"]:
        e = ep[(p, verb)]
        for o in re.findall(r"[CRUD]", op) or ["?"]:
            e["tables"][k].add(o)
        if auth:
            e["auth"].add(auth)
        if handler:
            e["handler"].add(handler.split("→")[0].strip()[:60])
import ast
AUTHMAP = {"require_admin_api_key": "Admin key", "get_current_student_id": "Learner JWT", "require_staff": "Staff cookie"}


def _lit(x):
    try:
        return ast.literal_eval(x) if isinstance(x, str) else (x or [])
    except Exception:
        return []


L = ["# Endpoint index — every REST route → tables it touches", "",
     "One row per `mathbank-rest` route (from the static route table `generated/endpoints.json`) plus any "
     "documented `/v1/` route served elsewhere (⚠). **Verified** tables come from the hand-checked "
     "\"REST operations today\" sections of [documentation/database/schemas/](../../../../documentation/database/schemas/) "
     "(reverse of [TABLE_INDEX.md](TABLE_INDEX.md)). **Static trace only** lists tables the call-graph trace found "
     "that no doc attributes to the route — usually transitive reads, occasionally dynamic SQL or a doc gap; "
     "confirm in code before relying on it. Ops: C=insert R=select U=update/upsert D=delete. "
     "Auth = FastAPI dependency found by the trace (`anonymous*` = none found at route level; check router-level dependencies).", ""]
keys = {(e["path"], e["method"]) for e in _EP} | set(ep)
groups = collections.defaultdict(list)
for (p, verb) in keys:
    parts_ = p.split("/")
    seg = parts_[2] if p.startswith("/v1/") and len(parts_) > 2 else (parts_[1] or "/")
    if seg == "admin" and len(parts_) > 3:
        seg = "admin/" + parts_[3]
    groups[seg].append((p, verb))
order = {"GET": 0, "POST": 1, "PUT": 2, "PATCH": 3, "DELETE": 4}
for g in sorted(groups):
    L += [f"## `{g}`", "", "| Route | Auth | Tables — verified | Static trace only | Handler |", "|---|---|---|---|---|"]
    for p, verb in sorted(groups[g], key=lambda x: (x[0], order.get(x[1], 9))):
        e, real = ep.get((p, verb)), EPS.get((verb, p))
        ver = e["tables"] if e else {}
        tbl = ", ".join(f"`{k}` {''.join(sorted(o))}" for k, o in sorted(ver.items())) or "—"
        static = collections.defaultdict(set)
        for k, o in _lit(real["ops"]) if real else []:
            if k not in ver:
                static[k].add(o)
        st = ", ".join(f"`{k}` {''.join(sorted(o))}" for k, o in sorted(static.items())) or "—"
        if real:
            auth = ", ".join(AUTHMAP.get(a, a) for a in _lit(real["auth"])) or "anonymous*"
            handler = f"`{real['module'].replace('mathbank_rest.', '')}.{real['function']}`"
        else:
            auth = md("; ".join(sorted(e["auth"]))) if e else ""
            handler = "⚠ not in mathbank-rest route table — " + md("; ".join(sorted(e["handler"]))) if e else ""
        L.append(f"| `{verb} {p}` | {auth} | {tbl} | {st} | {handler} |")
    L.append("")
open(os.path.join(OUT, "ENDPOINT_INDEX.md"), "w").write("\n".join(L))

# MIGRATION_INDEX.md
created, altered = collections.defaultdict(list), collections.defaultdict(set)
for k, v in cat.items():
    created[v.get("migration") or "?"].append(k)
    for col, mig in (v.get("columns_added_by") or {}).items():
        if mig != v.get("migration"):
            altered[mig].add(f"{k}.{col}")
L = ["# Migration index — mathbank-db/sql/NNN → tables created / columns added", "",
     "Generated from `generated/catalog.json`. Constraint/trigger/index-only migrations show no rows; "
     "read the SQL file for those.", "", "| Migration | Tables/views created | Columns added to existing tables |", "|---|---|---|"]
for mig in sorted(set(created) | set(altered) | {os.path.basename(f) for f in glob.glob(os.path.join(ROOT, "mathbank-db/sql/0*.sql"))}):
    c = ", ".join(f"`{k}`" for k in sorted(created.get(mig, []))) or "—"
    a = ", ".join(f"`{x}`" for x in sorted(altered.get(mig, []))) or "—"
    link = f"../../../../{mig}" if "/" in mig else f"../../../../mathbank-db/sql/{mig}"
    L.append(f"| [{mig}]({link}) | {c} | {a} |")
open(os.path.join(OUT, "MIGRATION_INDEX.md"), "w").write("\n".join(L) + "\n")

n_routes = len(ep)
undoc = sorted(set(cat) - set(tables))
real_keys = {(e["path"], e["method"]) for e in _EP}
print(f"tables={len(cat)} documented={len(tables)} doc_routes={n_routes} real_routes={len(real_keys)} "
      f"real_routes_with_verified_tables={len(real_keys & set(ep))} doc_routes_outside_rest={sorted(set(ep) - real_keys)}")
print("unresolved fragments:", sum(1 for t in tables.values() for o in t["other"] if "unresolved" in o))
print("undocumented tables:", undoc, "| untyped:", sorted(k for k, t in tables.items() if t["type"] == "—"))
