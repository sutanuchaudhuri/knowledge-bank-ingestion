"""Serve real local staff sessions; optionally enable configured database draft persistence."""
import argparse
import os

os.environ["SOCRATIC_AUTH_MODE"] = "local"

from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute

from mathbank_rest import socratic_auth
from mathbank_rest.routers.socratic import router

app = FastAPI(title="Socratic local staff authentication", description=__doc__)
app.include_router(APIRouter(routes=[
    route for route in router.routes if isinstance(route, APIRoute) and "/session" in route.path
]))


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--with-drafts", action="store_true",
                        help="Enable the real isolated API against REST's configured Postgres; not an offline fixture.")
    args = parser.parse_args()
    socratic_auth.configured()
    target = app
    if args.with_drafts:
        from mathbank_rest.socratic_app import app as drafts_app
        target = drafts_app
        from mathbank_rest.config import settings
        settings.socratic_access_audit = True  # sign-ins/role switches are audited like the hosted Studio
        print("LOCAL AUTH + REAL DRAFT STORAGE: uses configured Postgres. No model/AWS orchestration. Ctrl-C to stop.")
    else:
        print("LOCAL AUTH ONLY: no workflow persistence, model or AWS integrations. Ctrl-C to stop.")
    uvicorn.run(target, host="127.0.0.1", port=args.port, proxy_headers=False)


if __name__ == "__main__":
    main()
