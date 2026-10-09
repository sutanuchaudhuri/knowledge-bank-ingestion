import os
import threading
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_route_contracts import program
from test_route_critic import accepted_metadata

from mathbank_rest import route_batch
from mathbank_rest.db.postgres import engine
from mathbank_rest.route_contracts import RouteProgram
from mathbank_rest.route_ollama import OllamaProvider
from mathbank_rest.route_resources import GIB, Resources, capacity


def test_capacity_accounts_for_model_context_available_ram_and_cpu():
    resources = Resources("Darwin", 10, 16 * GIB, 12 * GIB)
    plan = capacity(resources, 4 * GIB, 16384)
    assert plan["workers"] == 2
    assert plan["num_thread"] == 5
    assert capacity(resources, 4 * GIB, 32768)["workers"] == 1
    assert capacity(resources, 4 * GIB, 16384, 1)["workers"] == 1
    with pytest.raises(ValueError, match="safe ceiling"):
        capacity(resources, 4 * GIB, 16384, 3)


def test_insufficient_memory_never_defaults_to_one_worker():
    with pytest.raises(ValueError, match="Insufficient"):
        capacity(Resources("Darwin", 10, 16 * GIB, 5 * GIB), 4 * GIB, 16384)


def test_gpu_memory_is_an_additional_ceiling():
    plan = capacity(Resources("Linux", 32, 64 * GIB, 60 * GIB, 8 * GIB), 4 * GIB, 16384)
    assert plan["workers"] == 1 and plan["num_thread"] == 10


def test_large_machine_is_not_arbitrarily_capped_at_eight_workers():
    plan = capacity(Resources("Darwin", 24, 160 * GIB, 144 * GIB), 4 * GIB, 16384)
    assert plan["workers"] == 24 and plan["num_thread"] == 1


def test_stale_worker_refused_before_persistence():
    conn = MagicMock()
    conn.execute.return_value.first.return_value = None
    with pytest.raises(route_batch.LeaseLost):
        route_batch.check_owner(conn, {"task_id": uuid4(), "owner_token": uuid4()})
    assert "FOR UPDATE" in str(conn.execute.call_args.args[0])


def test_claim_is_atomic_skip_locked_and_has_no_global_lease(monkeypatch):
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None
    monkeypatch.setattr(route_batch, "engine", SimpleNamespace(begin=lambda: nullcontext(conn)))
    assert route_batch.claim(str(uuid4())) is None
    query = str(conn.execute.call_args.args[0])
    assert "SKIP LOCKED" in query and "owner_token" in query and "lease_until" in query
    assert "pg_advisory" not in query


def test_database_retry_classification_does_not_retry_constraints():
    def failure(code):
        return DBAPIError("sql", {}, SimpleNamespace(sqlstate=code), False)

    assert route_batch.transient_database_error(failure("40001"))
    assert route_batch.transient_database_error(failure("08006"))
    assert not route_batch.transient_database_error(failure("23505"))


def test_missing_model_installed_before_preflight(monkeypatch, tmp_path):
    client = MagicMock()
    client.__enter__.return_value = client
    client.get.return_value.json.return_value = {"models": []}
    stream = MagicMock()
    stream.__enter__.return_value = stream
    stream.iter_lines.return_value = ['{"status":"pulling"}', '{"status":"success"}']
    client.stream.return_value = stream
    monkeypatch.setattr(route_batch.httpx, "Client", lambda **kwargs: client)
    preflight = MagicMock()
    monkeypatch.setattr(route_batch.OllamaProvider, "preflight", preflight)
    route_batch.ensure_model("http://127.0.0.1:1", "test:7b", tmp_path)
    assert client.stream.call_args.args == ("POST", "http://127.0.0.1:1/api/pull")
    preflight.assert_called_once()
    assert "success" in (tmp_path / "model-install.log").read_text()


def test_installed_model_not_downloaded_again(monkeypatch, tmp_path):
    client = MagicMock()
    client.__enter__.return_value = client
    client.get.return_value.json.return_value = {"models": [{"name": "test:7b"}]}
    monkeypatch.setattr(route_batch.httpx, "Client", lambda **kwargs: client)
    route_batch.ensure_model("http://127.0.0.1:1", "test:7b", tmp_path)
    client.stream.assert_not_called()


def test_failed_model_download_prevents_inference(monkeypatch, tmp_path):
    client = MagicMock()
    client.__enter__.return_value = client
    client.get.return_value.json.return_value = {"models": []}
    stream = MagicMock()
    stream.__enter__.return_value = stream
    stream.iter_lines.return_value = ['{"error":"not found"}']
    client.stream.return_value = stream
    monkeypatch.setattr(route_batch.httpx, "Client", lambda **kwargs: client)
    with pytest.raises(route_batch.OllamaError, match="download failed"):
        route_batch.ensure_model("http://127.0.0.1:1", "test:7b", tmp_path)


@pytest.mark.parametrize("eventual_pass", [False, True])
def test_critic_feedback_controls_retry_and_persistence(monkeypatch, eventual_pass):
    source = {
        "solution_id": str(uuid4()),
        "problem_id": str(uuid4()),
        "statement_text": "Problem",
        "source": "Given three right angles. Use the sum.",
        "canonical_code": "TEST",
        "verification_status": "UNVERIFIED",
    }
    task = {
        "task_id": uuid4(),
        "owner_token": uuid4(),
        "solution_id": source["solution_id"],
        "source_hash": route_batch.route_compiler.source_hash(source),
    }
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.one.return_value = source
    monkeypatch.setattr(
        route_batch,
        "engine",
        SimpleNamespace(
            connect=lambda: nullcontext(conn),
            begin=lambda: nullcontext(conn),
        ),
    )
    monkeypatch.setattr(route_batch, "heartbeat", lambda *args: nullcontext())
    value = RouteProgram.model_validate(program())
    feedback = []

    def generate(current, nodes, provider):
        feedback.append(current.get("_critic_feedback"))
        current["_generation_metadata"] = accepted_metadata(value)
        return value

    monkeypatch.setattr(route_batch.route_compiler, "generate", generate)
    rejected = {"accepted": False, "evaluations": [{"step_index": 1, "issues": ["Wrong sum"]}]}
    critic = MagicMock(
        side_effect=[
            rejected,
            rejected,
            accepted_metadata(value)["critic"] if eventual_pass else rejected,
        ]
    )
    monkeypatch.setattr(route_batch, "evaluate", critic)
    store = MagicMock(return_value=str(uuid4()))
    monkeypatch.setattr(route_batch, "store", store)
    result = route_batch.process(
        task,
        str(uuid4()),
        [],
        OllamaProvider(model="gen", digest="gen"),
        OllamaProvider(model="critic", digest="critic"),
        None,
        threading.Event(),
    )
    assert critic.call_count == 3 and feedback[0] is None and feedback[1]
    if eventual_pass:
        assert result["status"] == "DONE" and store.call_count == 1
        assert len(store.call_args.args[1]["_generation_metadata"]["critic_attempt_history"]) == 3
    else:
        assert result["status"] == "FAILED" and result["error_code"] == "CriticRejected"
        store.assert_not_called()


def test_store_retries_transient_errors_twice_without_regeneration(monkeypatch):
    conn = MagicMock()
    conn.execute.return_value.scalar.return_value = None
    monkeypatch.setattr(route_batch, "engine", SimpleNamespace(begin=lambda: nullcontext(conn)))
    monkeypatch.setattr(route_batch, "check_owner", lambda *args: None)
    monkeypatch.setattr(route_batch.time, "sleep", lambda seconds: None)
    failure = DBAPIError("sql", {}, SimpleNamespace(sqlstate="40001"), False)
    persist = MagicMock(side_effect=[failure, failure, "release"])
    monkeypatch.setattr(route_batch.route_compiler, "persist", persist)
    result = route_batch.store(
        {"task_id": uuid4(), "owner_token": uuid4()},
        {"solution_id": str(uuid4()), "_generation_metadata": {}},
        RouteProgram.model_validate(program()),
        str(uuid4()),
        None,
    )
    assert result == "release" and persist.call_count == 3


def test_store_never_retries_permanent_constraint_errors(monkeypatch):
    conn = MagicMock()
    conn.execute.return_value.scalar.return_value = None
    monkeypatch.setattr(route_batch, "engine", SimpleNamespace(begin=lambda: nullcontext(conn)))
    monkeypatch.setattr(route_batch, "check_owner", lambda *args: None)
    failure = DBAPIError("sql", {}, SimpleNamespace(sqlstate="23505"), False)
    persist = MagicMock(side_effect=failure)
    monkeypatch.setattr(route_batch.route_compiler, "persist", persist)
    with pytest.raises(DBAPIError):
        route_batch.store(
            {"task_id": uuid4(), "owner_token": uuid4()},
            {},
            RouteProgram.model_validate(program()),
            str(uuid4()),
            None,
        )
    assert persist.call_count == 1


def test_live_two_connections_skip_locked_and_fence_expired_owner(monkeypatch):
    if os.environ.get("ROUTE_DB_TESTS") != "1":
        pytest.skip("Opt-in distributed queue integration")
    version = "test-queue-" + str(uuid4())
    runs = [str(uuid4()), str(uuid4())]
    try:
        with engine.begin() as conn:
            sources = (
                conn.execute(text("SELECT solution_id FROM core.solution LIMIT 2")).scalars().all()
            )
            assert len(sources) == 2
            for run in runs:
                conn.execute(
                    text("""
                    INSERT INTO pedagogy.route_compiler_run
                        (run_id,generator_version,requested_limit,status)
                    VALUES (:run,:v,2,'RUNNING')
                """),
                    {"run": run, "v": version},
                )
            for sid in sources:
                conn.execute(
                    text("""
                    INSERT INTO pedagogy.route_compile_task(generator_version,solution_id,source_hash)
                    VALUES (:v,:sid,'test')
                """),
                    {"v": version, "sid": sid},
                )
        monkeypatch.setattr(route_batch.route_compiler, "VERSION", version)
        with engine.connect() as one, engine.connect() as two:
            tx1, tx2 = one.begin(), two.begin()
            try:
                monkeypatch.setattr(
                    route_batch, "engine", SimpleNamespace(begin=lambda: nullcontext(one))
                )
                first = route_batch.claim(runs[0])
                monkeypatch.setattr(
                    route_batch, "engine", SimpleNamespace(begin=lambda: nullcontext(two))
                )
                second = route_batch.claim(runs[1])
                assert first["task_id"] != second["task_id"]
                tx1.commit()
                tx2.commit()
            finally:
                if tx1.is_active:
                    tx1.rollback()
                if tx2.is_active:
                    tx2.rollback()
        with engine.begin() as conn:
            conn.execute(
                text("""
                UPDATE pedagogy.route_compile_task SET lease_until=now()-interval '1 second'
                WHERE task_id=:id
            """),
                {"id": first["task_id"]},
            )
        monkeypatch.setattr(route_batch, "engine", engine)
        reclaimed = route_batch.claim(runs[1])
        assert reclaimed["task_id"] == first["task_id"]
        assert reclaimed["owner_token"] != first["owner_token"]
        with engine.begin() as conn:
            with pytest.raises(route_batch.LeaseLost):
                route_batch.check_owner(conn, first)
            route_batch.check_owner(conn, reclaimed)
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM pedagogy.route_compile_task WHERE generator_version=:v"),
                {"v": version},
            )
            conn.execute(
                text("DELETE FROM pedagogy.route_compiler_job WHERE run_id IN (:one,:two)"),
                {"one": runs[0], "two": runs[1]},
            )
            conn.execute(
                text("DELETE FROM pedagogy.route_compiler_run WHERE run_id IN (:one,:two)"),
                {"one": runs[0], "two": runs[1]},
            )
