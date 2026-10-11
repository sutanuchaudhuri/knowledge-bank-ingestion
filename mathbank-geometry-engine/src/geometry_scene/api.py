import os
import secrets
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Response
from fastapi import Path as APIPath

from .errors import GeometryError, InvalidFrame
from .repository import Repository
from .schemas import SceneInput, StateDelta
from .service import validate_frame

SceneID = Annotated[str, APIPath(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")]
Version = Annotated[int, APIPath(ge=0)]


def make_router(
    owner_dependency: Callable,
    repository_dependency: Callable,
    mutation_authorization: Callable | None = None,
    expose_solver_diagnostics: bool = True,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/geometry-scenes",
        tags=["geometry-scenes"],
        dependencies=[Depends(mutation_authorization)] if mutation_authorization else [],
    )
    Owner = Annotated[str, Depends(owner_dependency)]
    Store = Annotated[Repository, Depends(repository_dependency)]
    Key = Annotated[str | None, Header(alias="Idempotency-Key", max_length=200)]

    def call(operation, *args):
        try:
            return operation(*args)
        except InvalidFrame as exc:
            raise HTTPException(
                exc.status_code,
                {
                    "code": exc.code,
                    "message": "scene failed mathematical/visual validation",
                    "validation": exc.frame.validation.model_dump(),
                    "solver_diagnostics": exc.frame.scene_state.solver_diagnostics
                    if expose_solver_diagnostics
                    else {
                        "tool_versions": exc.frame.scene_state.solver_diagnostics.get(
                            "tool_versions", {}
                        )
                    },
                },
            ) from None
        except GeometryError as exc:
            raise HTTPException(exc.status_code, {"code": exc.code, "message": str(exc)}) from None

    def result(frame, replayed=False):
        state = frame.model_dump(mode="json")
        if not expose_solver_diagnostics:
            state["scene_state"]["solver_diagnostics"] = {
                "tool_versions": frame.scene_state.solver_diagnostics.get("tool_versions", {})
            }
        return {
            **state,
            "scene_id": frame.scene_state.scene_id,
            "version": frame.version,
            "replayed": replayed,
            "frame_asset": {
                "mime_type": "image/svg+xml",
                "content_path": f"/v1/geometry-scenes/{frame.scene_state.scene_id}/versions/{frame.version}/render",
            },
        }

    # Runtime annotations are intentionally resolved here: factory-scoped dependencies differ
    # between the standalone server and the existing authenticated REST application.
    @router.post("", status_code=201)
    def create(body: SceneInput, owner: Owner, store: Store, key: Key = None):
        frame, replayed = call(store.create, body, owner, key)
        return result(frame, replayed)

    @router.post("/{scene_id}/deltas")
    def delta(scene_id: SceneID, body: StateDelta, owner: Owner, store: Store, key: Key = None):
        frame, replayed = call(store.apply, scene_id, body, owner, key)
        return result(frame, replayed)

    @router.get("/{scene_id}")
    def current(scene_id: SceneID, owner: Owner, store: Store):
        return result(call(store.current, scene_id, owner))

    @router.get("/{scene_id}/versions/{version}")
    def read(scene_id: SceneID, version: Version, owner: Owner, store: Store):
        return result(call(store.read, scene_id, version, owner))

    @router.get("/{scene_id}/versions/{version}/render")
    def render_version(scene_id: SceneID, version: Version, owner: Owner, store: Store):
        frame = call(store.read, scene_id, version, owner)
        return Response(
            frame.svg,
            media_type="image/svg+xml",
            headers={
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; sandbox",
            },
        )

    @router.post("/{scene_id}/versions/{version}/validate")
    def validate(scene_id: SceneID, version: Version, owner: Owner, store: Store):
        return call(validate_frame, call(store.read, scene_id, version, owner)).model_dump()

    @router.get("/{scene_id}/frames")
    def frames(scene_id: SceneID, owner: Owner, store: Store):
        return {"frames": call(store.frames, scene_id, owner)}

    return router


def create_app(repository: Repository, token: str) -> FastAPI:
    if len(token) < 16:
        raise ValueError("standalone API token must have at least 16 characters")

    def owner(authorization: Annotated[str | None, Header()] = None):
        if not authorization or not secrets.compare_digest(authorization, "Bearer " + token):
            raise HTTPException(401, "valid standalone bearer token required")
        return "standalone"

    app = FastAPI(title="Geometry Scene Engine", version="0.1.0")
    app.include_router(make_router(owner, lambda: repository))
    return app


def app_factory():
    token = os.environ.get("GEOMETRY_SCENE_TOKEN")
    path = os.environ.get("GEOMETRY_SCENE_DB")
    if not token or not path:
        raise RuntimeError("set GEOMETRY_SCENE_TOKEN and GEOMETRY_SCENE_DB explicitly")
    return create_app(Repository(Path(path)), token)
