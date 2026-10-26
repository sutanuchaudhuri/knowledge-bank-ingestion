"""Unauthenticated hosted smoke checks; never substitute for real staff sign-in."""
import argparse
from pathlib import Path
from urllib.parse import urlparse

import httpx

from mathbank_rest.socratic_app import app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    target = urlparse(args.url)
    if target.scheme != "https" or not target.hostname or target.username or target.password:
        parser.error("Use the public isolated HTTPS Studio URL, without credentials")
    base = args.url.rstrip("/")
    with httpx.Client(base_url=base, timeout=45, follow_redirects=False) as client:
        health = client.get("/health")
        assert health.status_code == 200, f"Health failed with HTTP {health.status_code}"
        assert health.json() == {"ok": True, "prototype_only": True, "evaluation_available": True,
                                 "evaluation_scope": "SYNTHETIC_PREVIEW_DETERMINISTIC",
                                 "model_jobs_available": False}
        schema = client.get("/openapi.json")
        assert schema.status_code == 200
        assert schema.json() == app.openapi(), "Hosted isolated OpenAPI differs from current source"
        index = client.get("/")
        assert index.status_code == 200 and '<div id="root">' in index.text
        assert "default-src 'self'" in index.headers["Content-Security-Policy"]
        built = Path(__file__).resolve().parents[2] / "mathbank-socratic-admin/dist/index.html"
        assert index.text == built.read_text(), "Hosted SPA differs from current production build"
        for path in ("session", "strategies", "resources", "workflows"):
            denied = client.get(f"/v1/admin/socratic/{path}")
            assert denied.status_code == 401, f"{path} did not deny unauthenticated access"
            assert denied.headers.get("Cache-Control") == "no-store"
        denied = client.post("/v1/admin/socratic/session",
                             headers={"Origin": "https://untrusted.example.test"},
                             json={"username": "synthetic-smoke-not-a-user", "password": "synthetic-not-a-credential"})
        assert denied.status_code == 403
        invalid = client.post("/v1/admin/socratic/session", headers={"Origin": base},
                              json={"username": "synthetic-smoke-not-a-user"})
        assert invalid.status_code == 422
        assert client.get("/v1/learner/profile").status_code == 404
    print("PASS: hosted readiness, exact isolated source OpenAPI/SPA, no-store 401, foreign-origin 403, safe 422 and legacy-route absence.")
    print("NOT VERIFIED: successful Cognito staff sign-in/groups, protected cloud persistence, logout/revocation or any model/orchestration job.")


if __name__ == "__main__":
    main()
