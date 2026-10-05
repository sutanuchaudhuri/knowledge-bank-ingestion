"""Generation and publication failures have independent bounded recovery."""

from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from neo4j.exceptions import AuthError, ServiceUnavailable, SessionExpired, TransientError

from mathbank_rest import publication
from scripts import enrich_corpus as worker


@pytest.mark.parametrize(
    "failure",
    [
        SessionExpired("disconnect"),
        ServiceUnavailable("routing"),
        TransientError("retry"),
        publication.ReviewConflict("stale fingerprint"),
    ],
)
def test_publication_retries_refresh_fingerprint_without_model_calls(monkeypatch, failure):
    calls = []
    sleeps = []
    monkeypatch.setattr(publication, "engine", SimpleNamespace(connect=lambda: nullcontext(None)))
    fingerprints = iter(["first", "second", "third"])
    monkeypatch.setattr(publication, "fingerprint", lambda conn: next(fingerprints))
    monkeypatch.setattr(publication.time, "sleep", sleeps.append)

    def publish(current, codes):
        calls.append((current, codes))
        if len(calls) < 3:
            raise failure

    monkeypatch.setattr(publication, "publish", publish)
    publication.publish_current(["ONE", "ONE"])
    assert calls == [("first", ["ONE"]), ("second", ["ONE"]), ("third", ["ONE"])]
    assert sleeps == [2, 4]


@pytest.mark.parametrize(
    "failure, attempts",
    [
        (SessionExpired("disconnect"), 3),
        (AuthError("credentials"), 1),
        (ValueError("cycle"), 1),
    ],
)
def test_publication_exhaustion_or_terminal_failure_is_explicit(monkeypatch, failure, attempts):
    calls = []
    monkeypatch.setattr(publication, "engine", SimpleNamespace(connect=lambda: nullcontext(None)))
    monkeypatch.setattr(publication, "fingerprint", lambda conn: "fresh")
    monkeypatch.setattr(publication.time, "sleep", lambda seconds: None)

    def publish(*args):
        calls.append(args)
        raise failure

    monkeypatch.setattr(publication, "publish", publish)
    with pytest.raises(type(failure)):
        publication.publish_current(["ONE"])
    assert len(calls) == attempts


def setup_worker(monkeypatch, selections):
    from concurrent.futures import Future

    class InlineExecutor:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def submit(self, operation, code):
            future = Future()
            try:
                future.set_result(operation(code))
            except worker.EnrichmentUnavailable as exc:
                future.set_exception(exc)
            return future

    monkeypatch.setattr(worker, "ThreadPoolExecutor", InlineExecutor)
    monkeypatch.setattr(worker, "engine", SimpleNamespace(connect=lambda: nullcontext(None)))
    selections = iter(selections)
    selected = []

    def select(conn, limit, excluded=None):
        selected.append(limit)
        pending, codes = next(selections)
        return pending, codes[:limit]

    monkeypatch.setattr(worker, "select_work", select)
    monkeypatch.setattr(worker.time, "monotonic", lambda: 100)
    return selected


def test_reselects_due_failed_job_before_more_fresh_work(monkeypatch):
    selected = setup_worker(
        monkeypatch,
        [
            ([], ["FRESH"]),
            (["FRESH"], ["DUE_RETRY"]),
            (["DUE_RETRY"], ["NEXT_FRESH"]),
            ([], []),
        ],
    )
    generated = []
    published = []
    monkeypatch.setattr(
        worker,
        "enrich_problem",
        lambda code: generated.append(code) or {"status": "automatically_approved"},
    )
    monkeypatch.setattr(worker, "publish_current", published.append)
    worker.run_worker(False, 2)
    assert selected == [1, 1, 0, 0]
    assert generated == ["FRESH", "DUE_RETRY"]
    assert published == [["FRESH"], ["DUE_RETRY"]]


def test_watch_replays_graph_failure_without_regeneration_or_misleading_error(monkeypatch, caplog):
    setup_worker(
        monkeypatch,
        [
            (["SAVED"], ["NEW"]),
            (["SAVED", "NEW"], []),
            (["SAVED", "NEW"], []),
            ([], []),
        ],
    )
    clock = [100.0]
    monkeypatch.setattr(worker.time, "monotonic", lambda: clock[0])
    generated = []
    published = []

    def publish(codes):
        published.append(list(codes))
        if len(published) == 1:
            raise SessionExpired("disconnect")

    def sleep(seconds):
        clock[0] += seconds

    monkeypatch.setattr(worker.time, "sleep", sleep)
    monkeypatch.setattr(worker, "publish_current", publish)
    monkeypatch.setattr(
        worker,
        "enrich_problem",
        lambda code: generated.append(code) or {"status": "automatically_approved"},
    )
    with pytest.raises(StopIteration):
        worker.run_worker(True, 100, stop=SimpleNamespace(is_set=lambda: False, wait=sleep))
    assert generated == ["NEW"]
    assert published == [["SAVED"], ["SAVED", "NEW"]]
    assert "stage=publication" in caplog.text
    assert "COMPLETED Postgres metadata retained" in caplog.text
    assert "stage=generation" not in caplog.text


def test_generation_failure_is_not_publication_failure(monkeypatch, caplog):
    setup_worker(monkeypatch, [([], ["BAD"]), ([], [])])

    def generate(code):
        raise worker.EnrichmentUnavailable("cycle path")

    monkeypatch.setattr(worker, "enrich_problem", generate)
    worker.run_worker(False, 1)
    assert "stage=generation problem=BAD failed" in caplog.text
    assert "stage=publication" not in caplog.text


def test_four_jobs_overlap_without_duplicate_dispatch_and_publish_on_coordinator(monkeypatch):
    import threading

    lock = threading.Lock()
    barrier = threading.Barrier(4)
    generated = []
    completed = []
    published = []
    codes = ["ONE", "TWO", "THREE", "FOUR", "FIVE"]
    coordinator = threading.get_ident()
    monkeypatch.setattr(worker, "engine", SimpleNamespace(connect=lambda: nullcontext(None)))

    def select(conn, limit, excluded=None):
        with lock:
            available = [
                code for code in codes if code not in generated and code not in (excluded or [])
            ]
            return list(completed), available[:limit]

    def generate(code):
        with lock:
            generated.append(code)
        if code != "FIVE":
            barrier.wait(timeout=5)
        with lock:
            completed.append(code)
        return {"status": "automatically_approved"}

    def publish(batch):
        assert threading.get_ident() == coordinator
        with lock:
            published.extend(batch)
            for code in batch:
                completed.remove(code)

    monkeypatch.setattr(worker, "select_work", select)
    monkeypatch.setattr(worker, "enrich_problem", generate)
    monkeypatch.setattr(worker, "publish_current", publish)
    worker.run_worker(False, 5, workers=4)
    assert sorted(generated) == sorted(codes)
    assert sorted(published) == sorted(codes)


def test_graceful_stop_drains_claimed_jobs_without_dispatching_more(monkeypatch):
    import threading

    stop = threading.Event()
    state = {"done": False, "published": False}
    monkeypatch.setattr(worker, "engine", SimpleNamespace(connect=lambda: nullcontext(None)))

    def select(conn, limit, excluded=None):
        return (
            ["ONE"] if state["done"] and not state["published"] else [],
            ["ONE"] if limit and not state["done"] else [],
        )

    def generate(code):
        state["done"] = True
        stop.set()
        return {"status": "automatically_approved"}

    monkeypatch.setattr(worker, "select_work", select)
    monkeypatch.setattr(worker, "enrich_problem", generate)
    monkeypatch.setattr(worker, "publish_current", lambda codes: state.update(published=True))
    worker.run_worker(True, 100, workers=4, stop=stop)
    assert state == {"done": True, "published": True}
