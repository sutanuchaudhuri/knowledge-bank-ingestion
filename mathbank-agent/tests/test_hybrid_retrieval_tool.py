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
