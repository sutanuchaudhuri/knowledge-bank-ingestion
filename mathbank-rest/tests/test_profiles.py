"""App profiles (requirement 71 §2.1): every router in exactly one group; runtime has no PostgreSQL."""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap

import pytest

from mathbank_rest import profiles

SRC = os.path.join(os.path.dirname(__file__), "..", "src")


def _run(profile: str, code: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": SRC, "MB_APP_PROFILE": profile, "PYTHONWARNINGS": "ignore"}
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], env=env, capture_output=True, text=True, timeout=120, check=False)
    # a third-party deprecation warning can land on stdout; the result is always the last line
    r.result = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    return r


def test_every_router_is_in_exactly_one_group():
    groups = profiles.partition()
    names = [n for g in groups.values() for n in g]
    assert len(names) == len(set(names)), "a router is in two groups"
    assert set(names) == set(profiles.ROUTERS), (
        f"unassigned: {set(profiles.ROUTERS) - set(names)}; unknown: {set(names) - set(profiles.ROUTERS)}")


def test_runtime_pending_names_a_work_package_for_each_router():
    assert all(wp.startswith("WP") for wp in profiles.RUNTIME_PENDING.values())


def test_combined_profile_mounts_every_router_like_main():
    assert profiles.PROFILES["combined"] == tuple(profiles.ROUTERS)


def test_main_py_stays_the_combined_app_with_every_operation():
    from mathbank_rest.main import app as main_app

    ops = {(m.upper(), p) for p, v in main_app.openapi()["paths"].items() for m in v if m in ("get", "post", "put", "patch", "delete")}
    assert len(ops) >= 374 and ("GET", "/health/stores") in ops and ("GET", "/health") in ops
    # every admin router's routes are present in the combined app
    for name in profiles.ADMIN_ROUTERS:
        for r in profiles.load_router(name).routes:
            path = r.path.replace(":path", "")  # OpenAPI renders {x:path} as {x}
            assert any(p == path for _, p in ops), f"{name}: {r.path} missing from main.py"


def test_admin_profile_mounts_exactly_the_admin_routers():
    code = """
        from mathbank_rest.app_admin import app
        paths = set(app.openapi()["paths"])
        print(len(paths), "/health/stores" in paths, any(p.startswith("/v1/learner") for p in paths))
    """
    r = _run("admin", code)
    assert r.returncode == 0, r.stderr
    n, stores, learner = r.result.split()
    assert int(n) > 50 and stores == "True" and learner == "False"


def test_runtime_profile_starts_without_postgres_and_reports_stores():
    code = """
        from fastapi.testclient import TestClient
        from mathbank_rest.app_runtime import app
        c = TestClient(app)
        h = c.get("/health").json(); s = c.get("/health/stores").json()
        print(h["profile"], "postgres" in h, s["profile"], len(s["stores"]))
    """
    r = _run("runtime", code)
    assert r.returncode == 0, r.stderr
    assert r.result.split() == ["runtime", "False", "runtime", "13"]  # 12 contexts + vectors


def test_runtime_profile_refuses_any_postgres_use():
    code = """
        from mathbank_rest.db.postgres import engine, check_postgres
        for use in (lambda: engine.connect(), lambda: engine.begin(), lambda: engine.execute("select 1")):
            try:
                use()
            except RuntimeError as exc:
                assert "runtime profile" in str(exc)
            else:
                raise SystemExit("engine was usable in the runtime profile")
        print(check_postgres())
    """
    r = _run("runtime", code)
    assert r.returncode == 0, r.stderr
    assert "disabled in the runtime profile" in r.result


def test_combined_profile_still_builds_a_real_engine():
    r = _run("combined", "from mathbank_rest.db.postgres import engine; print(type(engine).__name__)")
    assert r.returncode == 0, r.stderr
    assert r.result == "Engine"


def test_unknown_profile_is_rejected():
    with pytest.raises(ValueError):
        profiles.create_app("nope")


def test_lambda_handler_selects_profile_from_environment():
    code = """
        import os, sys, types
        sys.modules["mangum"] = types.SimpleNamespace(Mangum=lambda app: app)
        import mathbank_rest.lambda_handler as h
        print(h.handler.title)
    """
    assert "(runtime)" in _run("runtime", code).result
    assert "(admin)" in _run("admin", code).result
    assert _run("combined", code).result == "mathbank-rest"
