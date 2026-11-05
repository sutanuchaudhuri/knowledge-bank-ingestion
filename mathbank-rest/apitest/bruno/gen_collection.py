"""Generate the Bruno collection (https://www.usebruno.com) for the runtime API from its live OpenAPI document.

    .venv/bin/python apitest/bruno/gen_collection.py            # rewrites apitest/bruno/collection/
    .venv/bin/python apitest/bruno/gen_collection.py --check    # exits 1 when the committed collection is stale

The source of truth is `app.openapi()` of `apitest.app:app`; the output is deterministic (no timestamps, stable ordering), so a
regeneration only produces a diff when the API changed. Never edit the generated files by hand: change this script.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

OUT = Path(__file__).resolve().parent / "collection"
METHODS = ("get", "post", "put", "patch", "delete")
COLLECTION_NAME = "MathBank REST (runtime profile)"
BOOTSTRAP = "00-bootstrap"

# Folder order = run order: public reads first, learner/admin flows after, the service-to-service integration API last.
TAG_ORDER = ("ops", "corpus", "taxonomy", "analytics", "search", "theorems", "micro-courses", "learner", "step-runtime",
             "tutoring-routes", "notifications", "quiz", "quiz-integration")

# POST operations that only read (everything else that is not a GET is a [WRITE]). Login stamps last-login, so it writes.
READ_ONLY_POSTS = {"/v1/search/concepts", "/v1/search/problems", "/v1/quiz-integration/question-pool/match"}

# Environment variables. Secret ones are never written with a value; `learnerToken` is filled by register/login. Chaining scripts
# use runtime variables (`bru.setVar`): `bru.setEnvVar` makes the CLI rewrite the committed environment files after a run.
SECRET_VARS = ("adminKey", "learnerToken")
ENV_DEFAULTS = {
    "baseUrl": "http://127.0.0.1:8000", "learnerEmail": "bruno-learner@example.com", "learnerPassword": "Bruno-learner-1",
    # public reference data present in dev: lets the public GET folders run before (or without) the bootstrap lists
    "canonicalCode": "AIME_1983_Q01", "conceptSlug": "alg", "techniqueSlug": "tech-3d-coordinate",
    "microCourseCode": "MC-MARKOV-STREAKS",
}
ENV_ORDER = ("baseUrl", "adminKey", "learnerToken", "learnerEmail", "learnerPassword", "studentId", "canonicalCode", "conceptSlug",
             "techniqueSlug", "microCourseCode", "theoremSlug", "attemptId", "outcomeAttemptId", "routeAttemptId", "stepId",
             "itemId", "planId", "quizId", "questionId", "enrollmentId", "feedbackId", "notificationId", "assetId", "imageId",
             "taxonomyNodeId", "cognitoSub")
PUBLIC_DEFAULTED = {"canonicalCode", "conceptSlug", "techniqueSlug", "microCourseCode"}

PATH_PARAM_VARS = {
    "attempt_id": "attemptId", "step_id": "stepId", "quiz_id": "quizId", "question_id": "questionId",
    "enrollment_id": "enrollmentId", "plan_id": "planId", "item_id": "itemId", "feedback_id": "feedbackId",
    "notification_id": "notificationId", "student_id": "studentId", "problem_ref": "canonicalCode", "code": "canonicalCode",
    "canonical_code": "canonicalCode", "asset_id": "assetId", "image_id": "imageId", "taxonomy_node_id": "taxonomyNodeId",
    "cognito_sub": "cognitoSub", "technique_slug": "techniqueSlug",
}
# Body fields and query parameters that name the same thing as an environment variable.
FIELD_VARS = {
    "student_id": "studentId", "student": "studentId", "quiz_id": "quizId", "question_id": "questionId",
    "attempt_id": "attemptId", "step_id": "stepId", "enrollment_id": "enrollmentId", "plan_id": "planId", "item_id": "itemId",
    "problem_code": "canonicalCode", "canonical_code": "canonicalCode", "concept_slug": "conceptSlug", "concept": "conceptSlug",
    "technique_slug": "techniqueSlug", "technique": "techniqueSlug", "cognito_sub": "cognitoSub", "asset_id": "assetId",
}
STRING_HINTS = {"submitted_answer": "42", "answer": "42", "q": "triangle", "query": "triangle", "competition": "AIME",
                "first_name": "Bruno", "last_name": "Learner", "display_name": "Bruno Learner", "new_password": "Bruno-learner-2",
                "current_password": "{{learnerPassword}}", "style": "AIME", "question_type": "MCQ", "phase": "INTAKE",
                "status": "STARTED", "generated_by": "bruno", "title": "Bruno practice paper", "error_message": "generation failed"}
EXAMPLE_UUID = "3f2b8c1e-6d4a-4b7e-9a15-2c0d5e8f1a73"

# (method, path) -> [(env var, candidate keys of the first item)]; response bodies are an array or `{items: [...]}`.
SEED_FIRST_ITEM = {
    ("get", "/v1/problems"): [("canonicalCode", ["canonical_code"])],
    ("get", "/v1/concepts"): [("conceptSlug", ["slug"])],
    ("get", "/v1/techniques"): [("techniqueSlug", ["slug"])],
    ("get", "/v1/micro-courses"): [("microCourseCode", ["canonical_code"])],
    ("get", "/v1/theorems/search"): [("theoremSlug", ["slug"])],
    ("get", "/v1/learner/attempts"): [("outcomeAttemptId", ["attempt_id"])],
    ("get", "/v1/learner/solve-attempts"): [("attemptId", ["attempt_id"])],
    ("get", "/v1/learner/route-attempts"): [("routeAttemptId", ["route_attempt_id", "attempt_id"])],
    ("get", "/v1/learner/micro-course-enrollments"): [("enrollmentId", ["enrollment_id"])],
    ("get", "/v1/learner/feedback"): [("feedbackId", ["feedback_id"])],
    ("get", "/v1/quiz/mine"): [("quizId", ["quiz_id"])],
    ("get", "/v1/quiz-integration/papers/mine"): [("quizId", ["quiz_id"])],
    ("get", "/v1/notifications/me"): [("notificationId", ["notification_id", "id"])],
    ("get", "/v1/attempts/{attempt_id}/recovery-plans"): [("planId", ["plan_id"])],
}
AUTH_SCRIPT = (
    "const body = res.body || {};\n"
    "if (body.access_token) bru.setVar(\"learnerToken\", body.access_token);\n"
    "if (body.student_id) bru.setVar(\"studentId\", body.student_id);"
)
CUSTOM_SCRIPTS = {
    ("post", "/v1/learner/register"): AUTH_SCRIPT,
    ("post", "/v1/learner/login"): AUTH_SCRIPT,
    ("get", "/v1/quiz/{quiz_id}"): (
        "const questions = (res.body && res.body.questions) || [];\n"
        "const first = questions[0] || {};\n"
        "if (first.question_id || first.id) bru.setVar(\"questionId\", String(first.question_id || first.id));"
    ),
    ("get", "/v1/attempts/{attempt_id}/runtime"): (
        "const body = res.body || {};\n"
        "const first = (body.steps || [])[0] || {};\n"
        "const stepId = body.current_step_id || first.step_id || first.solution_step_id;\n"
        "if (stepId) bru.setVar(\"stepId\", String(stepId));"
    ),
}

BOOTSTRAP_OPS = [("get", "/health"), ("get", "/health/stores"), ("post", "/v1/learner/register"), ("post", "/v1/learner/login"),
                 ("get", "/v1/problems"), ("get", "/v1/concepts"), ("get", "/v1/techniques"), ("get", "/v1/micro-courses"),
                 ("get", "/v1/learner/attempts"), ("get", "/v1/learner/solve-attempts"), ("get", "/v1/quiz/mine"),
                 ("get", "/v1/learner/micro-course-enrollments")]


class Schemas:
    def __init__(self, spec: dict):
        self.spec = spec

    def resolve(self, schema: dict) -> dict:
        while "$ref" in schema:
            node = self.spec
            for part in schema["$ref"].lstrip("#/").split("/"):
                node = node[part]
            schema = {**node, **{k: v for k, v in schema.items() if k != "$ref"}}
        return schema

    def example(self, schema: dict, name: str = "", *, placeholders: bool = True, depth: int = 0):
        """A realistic value: schema example/default first, then enum, then a format-aware value for the type."""
        s = self.resolve(schema)
        if depth > 6:
            return None
        if "example" in s:
            return s["example"]
        if s.get("examples"):
            return s["examples"][0]
        if "const" in s:
            return s["const"]
        if s.get("default") is not None:
            return s["default"]
        for key in ("allOf", "oneOf", "anyOf"):
            if key in s:
                options = [o for o in s[key] if self.resolve(o).get("type") != "null"]
                if key == "allOf":
                    merged: dict = {}
                    for o in options:
                        r = self.resolve(o)
                        merged = {**merged, **r, "properties": {**merged.get("properties", {}), **r.get("properties", {})},
                                  "required": [*merged.get("required", []), *r.get("required", [])]}
                    return self.example(merged, name, placeholders=placeholders, depth=depth + 1)
                return self.example(options[0], name, placeholders=placeholders, depth=depth + 1) if options else None
        if s.get("enum"):
            return s["enum"][0]
        kind = s.get("type")
        if isinstance(kind, list):
            kind = next((k for k in kind if k != "null"), None)
        if kind is None and "properties" in s:
            kind = "object"
        if kind == "object":
            return self._object(s, placeholders, depth)
        if kind == "array":
            item = self.example(s.get("items", {}), name, placeholders=placeholders, depth=depth + 1)
            return [item] * max(1, s.get("minItems", 0)) if item is not None else []
        if kind == "integer":
            return self._number(s, int)
        if kind == "number":
            return self._number(s, float)
        if kind == "boolean":
            return True
        if kind == "string":
            return self._string(s, name, placeholders)
        return None

    def _object(self, s: dict, placeholders: bool, depth: int) -> dict:
        props = s.get("properties", {})
        required = [p for p in props if p in s.get("required", [])]
        optional = [p for p in props if p not in required and self._worth_including(props[p])]
        if not required and not optional:
            optional = list(props)[:3]
        out = {}
        for p in props:
            if p in required or p in optional:
                value = self.example(props[p], p, placeholders=placeholders, depth=depth + 1)
                if value is not None or p in required:
                    out[p] = value
        return out

    def _worth_including(self, schema: dict) -> bool:
        s = self.resolve(schema)
        return s.get("default") is not None or "example" in s or bool(s.get("examples"))

    def _is_nullable(self, schema: dict) -> bool:
        s = self.resolve(schema)
        return ("default" in s and s["default"] is None) or any(self.resolve(o).get("type") == "null" for o in s.get("anyOf", []))

    @staticmethod
    def _number(s: dict, cast):
        low = s.get("minimum")
        if low is None and "exclusiveMinimum" in s:
            low = s["exclusiveMinimum"] + 1
        value = 1 if low is None else max(low, 1)
        if "maximum" in s:
            value = min(value, s["maximum"])
        return cast(value)

    def _string(self, s: dict, name: str, placeholders: bool) -> str:
        fmt = s.get("format")
        if name in STRING_HINTS:
            value = STRING_HINTS[name]
            if value.startswith("{{") and not placeholders:
                value = "Bruno-learner-1"
        elif name in FIELD_VARS and fmt != "uuid" and not placeholders:
            value = ENV_DEFAULTS.get(FIELD_VARS[name], "example")
        elif name in FIELD_VARS and placeholders:
            return "{{%s}}" % FIELD_VARS[name]
        elif fmt == "uuid":
            value = EXAMPLE_UUID
        elif fmt == "date-time":
            value = "2026-01-15T12:00:00Z"
        elif fmt == "date":
            value = "2026-01-15"
        elif fmt == "email":
            value = "learner@example.com"
        elif fmt in ("uri", "url"):
            value = "https://example.com/"
        else:
            value = "example"
        if s.get("minLength") and len(value) < s["minLength"]:
            value = (value + "x" * s["minLength"])[: s["minLength"]]
        if s.get("maxLength"):
            value = value[: s["maxLength"]]
        return value


def camel(name: str) -> str:
    head, *rest = re.split(r"[_\-]", name)
    return head + "".join(p.title() for p in rest)


def path_var(path: str, param: str) -> str:
    if param == "slug":
        for prefix, var in (("/v1/concepts", "conceptSlug"), ("/v1/techniques", "techniqueSlug"), ("/v1/theorems", "theoremSlug")):
            if path.startswith(prefix):
                return var
    if param == "canonical_code" and path.startswith("/v1/micro-courses"):
        return "microCourseCode"
    if param == "attempt_id" and path.startswith("/v1/tutor/route-attempts"):
        return "routeAttemptId"
    return PATH_PARAM_VARS.get(param, camel(param))


def auth_of(op: dict) -> tuple[bool, bool]:
    schemes = {name for req in op.get("security", []) for name in req}
    return "APIKeyHeader" in schemes, "HTTPBearer" in schemes


def is_write(method: str, path: str) -> bool:
    return method != "get" and path not in READ_ONLY_POSTS


def slugify(path: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", path.lower().replace("{", "").replace("}", "")).strip("-")


def indent(text: str, pad: str = "  ") -> str:
    return "\n".join(pad + line if line else "" for line in text.split("\n"))


def block(name: str, body: str) -> str:
    return f"{name} {{\n{indent(body)}\n}}\n"


def dict_block(name: str, rows: list[tuple[str, str, bool]]) -> str:
    return block(name, "\n".join(f"{'' if on else '~'}{k}: {v}" for k, v, on in rows))


class Request:
    """One OpenAPI operation rendered as a `.bru` file."""

    def __init__(self, schemas: Schemas, path: str, method: str, op: dict):
        self.schemas, self.path, self.method, self.op = schemas, path, method, op
        self.admin, self.bearer = auth_of(op)
        self.write = is_write(method, path)
        self.params = [schemas.resolve(p) for p in op.get("parameters", [])]

    @property
    def name(self) -> str:
        return f"{'[WRITE] ' if self.write else ''}{self.method.upper()} {self.path}"

    def url_path(self) -> str:
        return re.sub(r"{(\w+)}", lambda m: "{{%s}}" % path_var(self.path, m.group(1)), self.path)

    def query_rows(self) -> list[tuple[str, str, bool]]:
        """Required parameters and `limit` (kept small against real DynamoDB) are enabled; every other optional one is `~`."""
        rows = []
        for p in self.params:
            if p["in"] != "query":
                continue
            value = self.schemas.example(self.schemas.resolve(p.get("schema", {})), p["name"])
            if p["name"] in FIELD_VARS and isinstance(value, str):
                value = "{{%s}}" % FIELD_VARS[p["name"]]
            if p["name"] == "limit" and isinstance(value, int):
                value = min(value, 20)
            if p["name"] == "deep":
                value = "true"
            if isinstance(value, bool):
                value = str(value).lower()
            enabled = bool(p.get("required")) or p["name"] in ("limit", "deep")
            rows.append((p["name"], str(value), enabled))
        return rows

    def body_json(self) -> str | None:
        content = (self.op.get("requestBody") or {}).get("content", {}).get("application/json")
        if not content:
            return None
        text = json.dumps(self.schemas.example(content["schema"]), indent=2, ensure_ascii=False)
        if self.path.startswith("/v1/quiz"):
            text = text.replace('"event_type": "example"', '"event_type": "VIEW"')
        if self.path in ("/v1/learner/register", "/v1/learner/login"):
            text = text.replace('"learner@example.com"', '"{{learnerEmail}}"')
            text = re.sub(r'("password": )"[^"]*"', r'\1"{{learnerPassword}}"', text)
        return text

    def assertion(self) -> str:
        public = not (self.admin or self.bearer)
        seeded = all(path_var(self.path, m) in PUBLIC_DEFAULTED for m in re.findall(r"{(\w+)}", self.path))
        return "eq 200" if self.method == "get" and public and seeded else "lt 500"

    def script(self) -> str | None:
        key = (self.method, self.path)
        if key in CUSTOM_SCRIPTS:
            return CUSTOM_SCRIPTS[key]
        if key in SEED_FIRST_ITEM:
            lines = ["const body = res.body;",
                     "const rows = Array.isArray(body) ? body : (body && Array.isArray(body.items) ? body.items : []);",
                     "const first = rows[0] || {};"]
            for var, keys in SEED_FIRST_ITEM[key]:
                expr = " || ".join(f"first.{k}" for k in keys)
                lines.append(f"if ({expr}) bru.setVar(\"{var}\", String({expr}));")
            return "\n".join(lines)
        return None

    def docs(self) -> str:
        who = ["learner bearer token (`{{learnerToken}}`)"] * self.bearer + ["admin key (`{{adminKey}}`)"] * self.admin
        lines = [f"**{self.op.get('summary', self.name)}**", "", f"`{self.method.upper()} {self.path}`", ""]
        if self.op.get("description"):
            lines += [self.op["description"].strip(), ""]
        lines.append(f"Auth: {' and '.join(who) if who else 'none (public)'}.")
        if self.write:
            lines += ["", "**[WRITE]** changes server state. `dev-readonly` answers 423 (AWS_READONLY); `test-writable` writes "
                          "only to the `-test` resources."]
        if self.op.get("deprecated"):
            lines += ["", "Deprecated."]
        return "\n".join(lines)

    def tags(self) -> list[str]:
        audience = "public" if not (self.admin or self.bearer) else ("learner" if self.bearer and not self.admin else "admin")
        return ["write" if self.write else "read", audience]

    def render(self, seq: int) -> str:
        url = "{{baseUrl}}" + self.url_path()
        query = self.query_rows()
        enabled = [f"{k}={v}" for k, v, on in query if on]
        if enabled:
            url += "?" + "&".join(enabled)
        body = self.body_json()
        tags = "tags: [\n" + "\n".join(f"  {t}" for t in self.tags()) + "\n]"
        parts = [block("meta", f"name: {self.name}\ntype: http\nseq: {seq}\n{tags}"),
                 block(self.method, f"url: {url}\nbody: {'json' if body is not None else 'none'}\n"
                                    f"auth: {'bearer' if self.bearer else 'none'}")]
        if query:
            parts.append(dict_block("params:query", query))
        headers = [(p["name"], "{{$guid}}", False) for p in self.params if p["in"] == "header"]
        if self.admin:
            headers.insert(0, ("X-Admin-Api-Key", "{{adminKey}}", True))
        if headers:
            parts.append(dict_block("headers", headers))
        if self.bearer:
            parts.append(block("auth:bearer", "token: {{learnerToken}}"))
        if body is not None:
            parts.append(block("body:json", body))
        parts.append(block("assert", f"res.status: {self.assertion()}"))
        script = self.script()
        if script:
            parts.append(block("script:post-response", script))
        parts.append(block("docs", self.docs()))
        return "\n".join(parts)


def collect(spec: dict) -> dict[str, list[Request]]:
    schemas = Schemas(spec)
    by_tag: dict[str, list[Request]] = {}
    for path, item in spec["paths"].items():
        for method in METHODS:
            if method in item:
                op = item[method]
                by_tag.setdefault((op.get("tags") or ["untagged"])[0], []).append(Request(schemas, path, method, op))
    return by_tag


def tag_sort(tag: str) -> tuple[int, str]:
    return (TAG_ORDER.index(tag), tag) if tag in TAG_ORDER else (len(TAG_ORDER), tag)


def environment(email: str) -> str:
    values = {**ENV_DEFAULTS, "learnerEmail": email}
    rows = "\n".join(f"{k}: {values.get(k, '')}" for k in ENV_ORDER if k not in SECRET_VARS)
    secrets = ",\n".join(f"  {k}" for k in SECRET_VARS)
    return f"{block('vars', rows)}\nvars:secret [\n{secrets}\n]\n"


def collection_docs(count: int) -> str:
    return "\n".join([
        f"# {COLLECTION_NAME}", "",
        f"{count} operations generated from the OpenAPI document of `apitest.app:app`; see `apitest/bruno/README.md`.", "",
        "- Run `00-bootstrap` first: it checks health, registers/logs in a learner and seeds the id variables.",
        "- Fill the secret `adminKey` environment variable from `mathbank-rest/.env` (`ADMIN_API_KEY`).",
        "- `[WRITE]` requests change state: `dev-readonly` refuses them (423), `test-writable` writes only to `-test` resources.",
        "- Headless without writes: `bru run --env local-dev-readonly --exclude-tags=write`."])


def build(spec: dict) -> dict[str, str]:
    """Relative path -> file content for the whole collection."""
    by_tag = collect(spec)
    index = {(r.method, r.path): r for reqs in by_tag.values() for r in reqs}
    count = sum(len(v) for v in by_tag.values())
    files = {
        "bruno.json": json.dumps({"version": "1", "name": COLLECTION_NAME, "type": "collection", "ignore": ["node_modules", ".git"]},
                                 indent=2) + "\n",
        "collection.bru": block("auth", "mode: none") + "\n" + block("docs", collection_docs(count)),
        "environments/local-dev-readonly.bru": environment(ENV_DEFAULTS["learnerEmail"]),
        "environments/local-test.bru": environment("bruno-test@example.com"),
    }
    folders = [(BOOTSTRAP, [index[k] for k in BOOTSTRAP_OPS])]
    for i, tag in enumerate(sorted(by_tag, key=tag_sort), start=1):
        reqs = by_tag[tag]
        folders.append((f"{i:02d}-{tag}", [r for r in reqs if not r.write] + [r for r in reqs if r.write]))
    for folder_seq, (folder, reqs) in enumerate(folders, start=1):
        files[f"{folder}/folder.bru"] = block("meta", f"name: {folder}\nseq: {folder_seq}")
        for seq, req in enumerate(reqs, start=1):
            files[f"{folder}/{seq:02d}-{req.method}-{slugify(req.path)}.bru"] = req.render(seq)
    return files


def inline_refs(schema, spec, depth=0):
    """Resolve `$ref`s so jsonschema needs no registry (recursive models are cut off after a few levels)."""
    if isinstance(schema, dict):
        if "$ref" in schema:
            if depth > 6:
                return {}
            node = spec
            for part in schema["$ref"].lstrip("#/").split("/"):
                node = node[part]
            return inline_refs(node, spec, depth + 1)
        return {k: inline_refs(v, spec, depth) for k, v in schema.items()}
    if isinstance(schema, list):
        return [inline_refs(v, spec, depth) for v in schema]
    return schema


def validate_bodies(spec: dict) -> list[str]:
    """Every generated JSON body must satisfy its request schema (placeholders replaced by real values)."""
    try:
        import jsonschema
    except ImportError:
        return []
    schemas, problems = Schemas(spec), []
    for reqs in collect(spec).values():
        for req in reqs:
            content = (req.op.get("requestBody") or {}).get("content", {}).get("application/json")
            if content:
                try:
                    jsonschema.validate(schemas.example(content["schema"], placeholders=False), inline_refs(content["schema"], spec))
                except jsonschema.ValidationError as exc:
                    problems.append(f"{req.name}: {exc.message}")
    return problems


def write(files: dict[str, str]) -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    for rel, content in files.items():
        target = OUT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def check(files: dict[str, str]) -> int:
    existing = {p.relative_to(OUT).as_posix() for p in OUT.rglob("*") if p.is_file()} if OUT.exists() else set()
    stale = sorted(existing ^ set(files))
    for rel, content in files.items():
        path = OUT / rel
        if path.exists() and path.read_text(encoding="utf-8") != content:
            stale.append(rel)
            sys.stdout.writelines(difflib.unified_diff(path.read_text(encoding="utf-8").splitlines(True), content.splitlines(True),
                                                       f"a/{rel}", f"b/{rel}"))
    print("collection is up to date" if not stale else f"stale: {len(stale)} file(s): {stale[:5]}")
    return 1 if stale else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="do not write; exit 1 if the committed collection differs")
    args = parser.parse_args()
    from apitest.app import app

    spec = app.openapi()
    for problem in validate_bodies(spec):
        print(f"warning: example body does not validate: {problem}", file=sys.stderr)
    files = build(spec)
    if args.check:
        return check(files)
    write(files)
    requests = [f for f in files if f.count("/") == 1 and f.endswith(".bru") and not f.startswith("environments/")
                and not f.endswith("folder.bru")]
    print(f"wrote {len(requests)} requests in {len({f.split('/')[0] for f in requests})} folders to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
