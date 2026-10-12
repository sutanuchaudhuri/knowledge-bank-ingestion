import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etl"))
import embed_corpus as embedder


def test_budget_refuses_before_embedding_provider_request(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(embedder, "OpenAI", lambda: client)
    cur, conn = MagicMock(), MagicMock()
    cur.fetchone.return_value = ("run",)
    cur.fetchall.return_value = [
        ("chunk", "A source problem with some text", "hash", "rep")
    ]
    with pytest.raises(RuntimeError, match="exceeds"):
        embedder.embed_pending_chunks(
            cur, conn, "model", None, max_cost_usd=0.000000001
        )
    client.embeddings.create.assert_not_called()
    query = cur.execute.call_args_list[1].args[0]
    assert "current_rep.status='ACTIVE'" in query and "e.status='ACTIVE'" in query


def test_no_pending_chunks_makes_no_paid_requests(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(embedder, "OpenAI", lambda: client)
    cur, conn = MagicMock(), MagicMock()
    cur.fetchone.return_value = ("run",)
    cur.fetchall.return_value = []
    assert embedder.embed_pending_chunks(
        cur, conn, "model", None, ["AIME_1983"], max_cost_usd=20
    ) == (0, 0)
    client.embeddings.create.assert_not_called()
