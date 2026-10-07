import httpx
from agents.mathbank_tutor.tools import rest_tools


def client_for(monkeypatch, statement, diagrams=None, image_status=200):
    def handle(request):
        if request.url.path.endswith("/diagrams"):
            return httpx.Response(200, json=diagrams or [])
        if "/problem-images/" in request.url.path:
            return httpx.Response(
                image_status,
                content=b"synthetic-image",
                headers={"content-type": "image/png"},
            )
        if request.url.path.endswith("/source"):
            return httpx.Response(200, json={"url": "https://example.test/exam.pdf"})
        return httpx.Response(
            200,
            json={
                "statement_text": statement,
                "competition": "SMT",
                "year": 2010,
                "official_answer": "hidden",
                "solutions": [{"answer": "hidden"}],
            },
        )

    monkeypatch.setattr(
        rest_tools,
        "_client",
        lambda: httpx.Client(
            base_url="http://rest", transport=httpx.MockTransport(handle)
        ),
    )


def test_missing_required_diagram_is_not_a_recommendation(monkeypatch):
    client_for(monkeypatch, "In the diagram below, find MD.")
    result = rest_tools.get_practice_problem("PAPER_SMT_2010_GEOM_Q06")
    assert result["eligible"] is False
    assert "statement_text" not in result and "markdown_block" not in result


def test_registered_but_unreadable_diagram_is_not_eligible(monkeypatch):
    client_for(
        monkeypatch,
        "In the diagram below, find MD.",
        [
            {
                "problem_image_id": "synthetic",
                "markdown": "![source](/api/rest/solve/images/synthetic)",
            }
        ],
        image_status=404,
    )
    assert rest_tools.get_practice_problem("CODE")["eligible"] is False
    client_for(monkeypatch, "Find MD.", [{
        "problem_image_id": "synthetic", "markdown": "![source](/api/rest/solve/images/synthetic)",
    }], image_status=404)
    assert rest_tools.get_practice_problem("CODE")["eligible"] is False


def test_working_diagram_and_direct_source_are_present_without_answers(monkeypatch):
    client_for(
        monkeypatch,
        "In the diagram below, find MD.",
        [
            {
                "problem_image_id": "synthetic",
                "markdown": "![source](/api/rest/solve/images/synthetic)",
            }
        ],
    )
    result = rest_tools.get_practice_problem("PAPER_SMT_2010_GEOM_Q06")
    assert result["eligible"] is True
    assert "![source]" in result["markdown_block"]
    assert "https://example.test/exam.pdf" in result["markdown_block"]
    assert "hidden" not in str(result)


def test_self_contained_problem_needs_no_diagram(monkeypatch):
    client_for(monkeypatch, "Prove that every square is a rectangle.")
    assert rest_tools.get_practice_problem("CODE")["eligible"] is True


def test_unparsed_asymptote_is_skipped_unless_source_image_is_ready(monkeypatch):
    client_for(monkeypatch, "Find h. [asy] import bsp; [/asy]")
    assert rest_tools.get_practice_problem("CODE")["eligible"] is False
    client_for(
        monkeypatch,
        "Find h. [asy] import bsp; [/asy]",
        [
            {
                "problem_image_id": "synthetic",
                "markdown": "![source](/api/rest/solve/images/synthetic)",
            }
        ],
    )
    result = rest_tools.get_practice_problem("CODE")
    assert result["eligible"] is True and "[asy]" not in result["statement_text"]


def test_practice_search_never_returns_rejected_statements(monkeypatch):
    monkeypatch.setattr(
        rest_tools,
        "search_problems",
        lambda *args, **kwargs: {
            "results": [{"canonical_code": "BROKEN"}, {"canonical_code": "COMPLETE"}],
            "warnings": ["Graph unavailable"],
        },
    )
    monkeypatch.setattr(
        rest_tools,
        "get_practice_problem",
        lambda code: {
            "canonical_code": code,
            "eligible": code == "COMPLETE",
            "statement_text": "missing diagram" if code == "BROKEN" else "complete",
        },
    )
    result = rest_tools.search_practice_problems("geometry")
    assert [p["canonical_code"] for p in result["results"]] == ["COMPLETE"]
    assert "missing diagram" not in str(result)
    assert result["skipped_incomplete"] == 1
    assert result["warnings"] == ["Graph unavailable"]


def test_verified_practice_tools_are_registered_on_the_real_tutor():
    from agents.mathbank_tutor.agent import root_agent

    assert rest_tools.get_practice_problem in root_agent.tools
    assert rest_tools.search_practice_problems in root_agent.tools
    assert "paste its markdown_block unchanged" in root_agent.instruction
