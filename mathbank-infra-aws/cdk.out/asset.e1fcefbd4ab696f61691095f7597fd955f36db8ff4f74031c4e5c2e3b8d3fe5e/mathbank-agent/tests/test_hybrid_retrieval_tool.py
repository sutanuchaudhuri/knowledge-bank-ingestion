from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import MagicMock

path = Path(__file__).resolve().parents[1] / "agents/mathbank_tutor/tools/rest_tools.py"
spec = spec_from_file_location("retrieval_tools", path)
tools = module_from_spec(spec)
spec.loader.exec_module(tools)


def test_tutor_explicitly_requests_graph_vector_lexical_and_preserves_warnings(monkeypatch):
    client = MagicMock()
    client.__enter__.return_value = client
    payload = {"results": [], "warnings": ["Graph unavailable"], "retrieval": {"graph": "unavailable"}}
    client.post.return_value.json.return_value = payload
    monkeypatch.setattr(tools, "_client", lambda: client)
    assert tools.search_problems("similar circles", competition="SMT", year_min=2020) == payload
    body = client.post.call_args.kwargs["json"]
    assert body["retrieval"] == {"semantic": True, "lexical": True, "graph": True}
    assert body["filters"] == {"competition": "SMT", "year_min": 2020}
    client.post.return_value.raise_for_status.assert_called_once()


def test_search_concepts_posts_taxonomy_query_with_parsed_filters(monkeypatch):
    client = MagicMock()
    client.__enter__.return_value = client
    payload = {"results": [{"taxonomy_node_id": "TECH.GEO.POWER_OF_A_POINT", "slug_kind": "technique"}],
               "warnings": []}
    client.post.return_value.json.return_value = payload
    monkeypatch.setattr(tools, "_client", lambda: client)
    assert tools.search_concepts("power of a point", node_types=" technique, subconcept ", chapter_number=3,
                                 limit=99) == payload
    path, = client.post.call_args.args
    assert path == "/v1/search/concepts"
    assert client.post.call_args.kwargs["json"] == {
        "query": "power of a point", "limit": 50, "node_types": ["TECHNIQUE", "SUBCONCEPT"], "chapter_number": 3}
    client.post.return_value.raise_for_status.assert_called_once()


def test_search_concepts_omits_empty_filters_and_technique_follow_up_quotes_slug(monkeypatch):
    client = MagicMock()
    client.__enter__.return_value = client
    monkeypatch.setattr(tools, "_client", lambda: client)
    tools.search_concepts("inversion")
    assert client.post.call_args.kwargs["json"] == {"query": "inversion", "limit": 8}
    tools.get_problems_for_technique("tech.geo/odd", limit=500)
    assert client.get.call_args.args == ("/v1/techniques/tech.geo%2Fodd/problems",)
    assert client.get.call_args.kwargs["params"] == {"limit": 200}


def test_problem_diagrams_use_answer_free_endpoint(monkeypatch):
    client = MagicMock()
    client.__enter__.return_value = client
    payload = [{"problem_image_id": "image", "markdown": "![diagram](/api/rest/solve/images/image)"}]
    client.get.return_value.json.return_value = payload
    monkeypatch.setattr(tools, "_client", lambda: client)
    assert tools.get_problem_diagrams("PAPER_SMT_2010_GEOM_Q06") == payload
    assert client.get.call_args.args == ("/v1/problems/by-code/PAPER_SMT_2010_GEOM_Q06/diagrams",)
    client.get.return_value.raise_for_status.assert_called_once()
