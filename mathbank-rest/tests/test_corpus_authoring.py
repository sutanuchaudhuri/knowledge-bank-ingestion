import base64
import struct
from uuid import UUID

import fitz
import pytest
from fastapi.testclient import TestClient

from mathbank_rest import corpus_authoring as author
from mathbank_rest import security
from mathbank_rest.db.problem_images import STUDENT_IMAGE_FILTER
from mathbank_rest.main import app

ID = UUID(int=12)


class Result:
    def __init__(self, row=None, scalar=None, rows=None):
        self.row, self.value, self.rows = row, scalar, rows

    def mappings(self):
        return self

    def first(self):
        return self.row

    def one(self):
        return self.row

    def scalar(self):
        return self.value

    def scalar_one(self):
        return self.value

    def all(self):
        return self.rows or []


class Connection:
    def __init__(self, draft=None, statement="Original question", rows=None):
        self.draft, self.statement, self.rows = draft, statement, rows
        self.calls = []

    def execute(self, sql, params=None):
        sql = str(sql)
        self.calls.append((sql, params))
        if "SELECT * FROM ingest.corpus_draft" in sql:
            return Result(self.draft)
        if "SELECT * FROM core.problem" in sql or "SELECT problem_id,canonical_code" in sql:
            return Result({"problem_id": ID, "canonical_code": "AIME_1985_Q04", "statement_text": self.statement})
        if "SELECT canonical_code" in sql:
            return Result(scalar="GENERATED_TEST_Q01")
        if "INSERT INTO ingest.corpus_draft" in sql:
            return Result({"draft_id": ID, "state": "DRAFT", "kind": params["kind"]})
        if "RETURNING" in sql:
            return Result(scalar=ID)
        if "max(ordinal)" in sql:
            return Result(scalar=4)
        return Result(rows=self.rows)


def draft(kind="TEXT_EDIT", **changes):
    return {"draft_id": ID, "kind": kind, "state": "DRAFT", "problem_id": ID, "revision": 1,
            "base_hash": author.digest("Original question"), "origin": "ADMIN",
            "payload": {"statement": "A reviewed replacement question"}, "object_key": "example.png",
            "review_note": None, **changes}


def test_admin_authorization_required_for_every_surface():
    client = TestClient(app)
    routes = [
        ("get", "/problems"), ("get", "/problems/AIME_1985_Q04"), ("get", "/drafts"),
        ("post", "/drafts"), ("put", f"/drafts/{ID}"), ("post", "/images"),
        ("post", "/generate"), ("get", f"/drafts/{ID}/image"), ("post", f"/drafts/{ID}/review"),
    ]
    for method, path in routes:
        assert getattr(client, method)("/v1/admin/corpus" + path).status_code in (401, 403)


def test_conflicting_edit_cannot_be_saved():
    conn = Connection()
    with pytest.raises(author.AuthoringError, match="changed") as error:
        author.save_draft(conn, "TEXT_EDIT", "AIME_1985_Q04", {"statement": "Replacement"},
                          "Source repair", expected_hash="0" * 64)
    assert error.value.status == 409
    assert len(conn.calls) == 1


def test_image_upload_is_bound_to_the_source_question_version():
    conn = Connection()
    with pytest.raises(author.AuthoringError, match="changed"):
        author.save_draft(conn, "IMAGE", "AIME_1985_Q04", {"side": "problem"}, "Source repair",
                          object_key="example.png", expected_hash="0" * 64)
    assert len(conn.calls) == 1


def test_text_draft_retains_original_and_is_not_published():
    conn = Connection()
    author.save_draft(conn, "TEXT_EDIT", "AIME_1985_Q04", {"statement": "Replacement"},
                      "Source repair", expected_hash=author.digest("Original question"))
    assert '"before_statement": "Original question"' in conn.calls[-1][1]["payload"]
    assert not any("UPDATE core.problem" in sql for sql, _ in conn.calls)


def test_review_detects_concurrent_source_change_before_publication():
    conn = Connection(draft(), statement="Changed since draft")
    with pytest.raises(author.AuthoringError, match="changed") as error:
        author.review(conn, ID, "APPROVED", "Checked original")
    assert error.value.status == 409
    assert not any("UPDATE core.problem" in sql for sql, _ in conn.calls)


def test_text_approval_clears_latex_marks_index_stale_and_records_review():
    conn = Connection(draft())
    result = author.review(conn, ID, "APPROVED", "Checked original")
    assert result["canonical_code"] == "AIME_1985_Q04"
    sql = "\n".join(sql for sql, _ in conn.calls)
    assert "statement_latex=NULL" in sql
    assert "admin_edited_at=clock_timestamp()" in sql
    assert "status='STALE'" in sql
    assert "reviewed_at=now()" in sql


def test_repeated_identical_approval_does_not_publish_twice():
    conn = Connection(draft(state="APPROVED", review_note="Checked original"))
    assert author.review(conn, ID, "APPROVED", "Checked original")["state"] == "APPROVED"
    assert not any(sql.strip().startswith(("INSERT", "UPDATE")) for sql, _ in conn.calls)
    with pytest.raises(author.AuthoringError):
        author.review(conn, ID, "REJECTED", "Different decision")


def test_repeated_rejection_never_reports_successful_publication():
    conn = Connection(draft(state="REJECTED", review_note="Wrong source"))
    result = author.review(conn, ID, "REJECTED", "Wrong source")
    assert result["state"] == "REJECTED"
    assert result["canonical_code"] is None
    assert len(conn.calls) == 1


def test_rejection_has_no_corpus_mutation():
    conn = Connection(draft())
    assert author.review(conn, ID, "REJECTED", "Wrong source")["state"] == "REJECTED"
    assert not any("core.problem" in sql or "core.solution" in sql for sql, _ in conn.calls)


def test_review_requires_the_content_version_the_admin_actually_saw():
    conn = Connection(draft(revision=2))
    with pytest.raises(author.AuthoringError, match="Draft changed"):
        author.review(conn, ID, "APPROVED", "Review version one", expected_revision=1)
    assert len(conn.calls) == 1


@pytest.mark.parametrize("side,source", [
    ("problem", "ADMIN_SOURCE_DIAGRAM"), ("solution", "ADMIN_SOLUTION_DIAGRAM"),
])
def test_approved_images_preserve_side_and_use_private_object_key(side, source):
    conn = Connection(draft("IMAGE", payload={"side": side}))
    author.review(conn, ID, "APPROVED", "Checked figure")
    image = next(params for sql, params in conn.calls if "INSERT INTO core.problem_image" in sql)
    assert image["source"] == source
    assert image["path"] == "object-store:example.png"
    assert "'ADMIN_SOLUTION_DIAGRAM'" in STUDENT_IMAGE_FILTER


def test_generated_problem_cannot_become_an_official_competition_question():
    conn = Connection(draft("NEW_PROBLEM", origin="AI", payload={
        "statement": "Find the number of ways to arrange three distinct objects.",
        "solution": "There are six arrangements.", "answer": "6", "diagram_required": False,
    }))
    result = author.review(conn, ID, "APPROVED", "Manual mathematical review")
    assert result["canonical_code"].startswith("GENERATED_")
    sql = "\n".join(sql for sql, _ in conn.calls)
    assert "'MATHBANK_GENERATED'" in sql
    assert "false) RETURNING paper_id" in sql
    assert "'UNVERIFIED'" in sql
    assert "UPDATE core.problem SET" not in sql


def test_new_problem_with_missing_diagram_cannot_publish():
    conn = Connection(draft("NEW_PROBLEM", payload={
        "statement": "Calculate the angle in the diagram below.", "solution": "A solution",
        "diagram_required": True,
    }))
    with pytest.raises(author.AuthoringError, match="needs a diagram"):
        author.review(conn, ID, "APPROVED", "Review")
    assert not any("INSERT" in sql for sql, _ in conn.calls)


def test_real_image_is_decoded_normalized_and_bad_types_rejected():
    with fitz.open() as document:
        page = document.new_page(width=10, height=10)
        data = page.get_pixmap().tobytes("png")
    normalized = author.image_bytes(base64.b64encode(data).decode(), "image/png")
    assert normalized.startswith(b"\x89PNG\r\n\x1a\n")
    for encoded, mime in [("not-base64", "image/png"), (base64.b64encode(b"<svg/>").decode(), "image/png"),
                          (base64.b64encode(data).decode(), "image/svg+xml")]:
        with pytest.raises(author.AuthoringError):
            author.image_bytes(encoded, mime)


@pytest.mark.parametrize("format,mime", [("png", "image/png"), ("jpeg", "image/jpeg")])
def test_source_upload_preserves_high_resolution_pixel_dimensions(format, mime):
    with fitz.open() as document:
        page = document.new_page(width=72, height=72)
        pixmap = page.get_pixmap(dpi=300)
        data = pixmap.tobytes(format)
    normalized = author.image_bytes(base64.b64encode(data).decode(), mime)
    decoded = fitz.Pixmap(normalized)
    assert (decoded.width, decoded.height) == (300, 300)


def test_oversized_image_header_is_rejected_before_decode():
    data = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + struct.pack(">II", 100000, 100000)
    with pytest.raises(author.AuthoringError, match="16 megapixels"):
        author.image_bytes(base64.b64encode(data).decode(), "image/png")


def test_inventory_uses_only_student_safe_diagrams_and_parameterized_filters():
    conn = Connection(rows=[{"canonical_code": "ONE"}, {"canonical_code": "TWO"}])
    result = author.inventory(conn, "AMC10", 2011, "A", 1, "'unsafe", True, 1, 0)
    assert result["hasMore"] and len(result["items"]) == 1
    sql, params = conn.calls[0]
    assert "'unsafe" not in sql and params["query"] == "'unsafe"
    assert "ADMIN_SOLUTION_DIAGRAM" in sql
    assert result["warnings"]


def test_paid_consent_required_and_official_identity_for_new_problem_forbidden(monkeypatch):
    app.dependency_overrides[security.require_admin_api_key] = lambda: None
    try:
        client = TestClient(app)
        assert client.post("/v1/admin/corpus/generate", json={"theme": "Number theory", "confirm_paid": False}).status_code == 422
        assert client.post("/v1/admin/corpus/drafts", json={
            "kind": "NEW_PROBLEM", "statement": "A new question", "note": "My authored work",
            "problem_code": "AMC10_2011A_Q01",
        }).status_code == 422
        assert client.post("/v1/admin/corpus/images", json={
            "problem_code": "TEST", "side": "problem", "mime_type": "image/png",
            "data_base64": "image", "note": "Source note", "rights_confirmed": False,
        }).status_code == 422
    finally:
        app.dependency_overrides.pop(security.require_admin_api_key, None)


def test_generation_invalid_provider_output_is_an_explicit_failure(monkeypatch):
    class Client:
        chat = None

        def __init__(self):
            self.chat = self
            self.completions = self

        def create(self, **kwargs):
            class Response:
                choices = ()
            return Response()

    monkeypatch.setattr(author.runtime_ai, "client", Client)
    with pytest.raises(author.AuthoringError, match="invalid problem"):
        author.generate_problem("Number theory")
