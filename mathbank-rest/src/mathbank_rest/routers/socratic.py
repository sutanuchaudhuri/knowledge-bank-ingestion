"""Socratic Studio staff boundary and isolated draft persistence."""
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Request, Response, Security
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.security import APIKeyCookie
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from mathbank_rest import socratic_auth as auth
from mathbank_rest import socratic_contracts as contracts
from mathbank_rest import socratic_preview as preview
from mathbank_rest import socratic_service as service
from mathbank_rest import socratic_users as users
from mathbank_rest.config import settings


class StaffRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def sanitized(request: Request):
            try:
                return await original(request)
            except RequestValidationError:
                # FastAPI's default errors echo raw input, including invalid passwords.
                raise auth.fail(422, "INVALID_STAFF_REQUEST", "Staff request fields are invalid.") from None

        return sanitized


class StaffErrorDetail(BaseModel):
    code: str
    message: str
    correlation_id: str
    retryable: bool


class StaffError(BaseModel):
    detail: StaffErrorDetail


router = APIRouter(prefix="/v1/admin/socratic", tags=["admin-socratic"], route_class=StaffRoute,
                   responses={code: {"model": StaffError} for code in (401, 403, 404, 409, 422, 429, 503)})
access_scheme = APIKeyCookie(name=auth.ACCESS_COOKIE, scheme_name="SocraticStaffCookie",
                            auto_error=False, description="HttpOnly staff access cookie; Cognito by default, explicit loopback-only local testing.")
refresh_scheme = APIKeyCookie(name=auth.REFRESH_COOKIE, scheme_name="SocraticRefreshCookie",
                             auto_error=False, description="HttpOnly current-session revocation cookie.")
origin_parameter = {
    "name": "Origin", "in": "header", "required": True, "schema": {"type": "string"},
    "description": "Exact explicitly configured Studio origin; cross-site requests are denied.",
}
csrf_parameter = {
    "name": "X-CSRF-Token", "in": "header", "required": True, "schema": {"type": "string"},
    "description": "CSRF token returned by the current staff session.",
}


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=128)
    password: SecretStr = Field(min_length=1, max_length=256)


role_scheme = APIKeyCookie(name=auth.ROLE_COOKIE, scheme_name="SocraticRoleCookie", auto_error=False,
                           description="Active Studio role; can only narrow the access granted by group membership.")


def require_staff(
    request: Request, response: Response,
    access_token: Annotated[str | None, Security(access_scheme)],
    role: Annotated[str | None, Security(role_scheme)] = None,
) -> auth.StaffSession:
    """Recheck staff session/capabilities; never trust caller actor fields."""
    response.headers["Cache-Control"] = "no-store"
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        auth.check_csrf(request, access_token or "")
    return auth.load_session(access_token or "", request=request, role=role)


def set_role_cookie(response: Response, role: str, max_age: int | None = None) -> None:
    response.set_cookie(auth.ROLE_COOKIE, role, max_age=max_age or settings.socratic_session_seconds,
                        path=auth.COOKIE_PATH, secure=settings.socratic_cookie_secure, httponly=True,
                        samesite="strict")


@router.post("/session", response_model=auth.StaffSession,
             openapi_extra={"parameters": [origin_parameter]})
def login(request: Request, response: Response, body: LoginRequest):
    """Sign in through configured Cognito or explicit local mode; return identity/CSRF, never tokens."""
    auth.check_origin(request)
    try:
        result = auth.login(body.username, body.password.get_secret_value(), request=request)
    except HTTPException as exc:
        code = exc.detail.get("code") if isinstance(exc.detail, dict) else None
        users.record(request, "STUDIO_SIGN_IN_FAILED", body.username.strip().lower(), detail={"code": code})
        raise
    for name, value in ((auth.ACCESS_COOKIE, result.access_token),
                        (auth.REFRESH_COOKIE, result.refresh_token)):
        response.set_cookie(name, value, max_age=result.max_age, path=auth.COOKIE_PATH,
                            secure=settings.socratic_cookie_secure, httponly=True, samesite="strict")
    set_role_cookie(response, result.session.role, result.max_age)
    users.record(request, "STUDIO_SIGN_IN_SUCCEEDED", result.session.actor.username, actor=result.session.actor,
                 detail={"role": result.session.role, "auth_mode": result.session.auth_mode})
    response.headers["Cache-Control"] = "no-store"
    return result.session


@router.get("/session", response_model=auth.StaffSession)
def session(staff: Annotated[auth.StaffSession, Depends(require_staff)]):
    """Restore a staff session with provider validity/capability checks and stable principal."""
    return staff


@router.delete("/session", status_code=204,
               openapi_extra={"parameters": [origin_parameter, csrf_parameter]})
def logout(
    request: Request, response: Response,
    access_token: Annotated[str | None, Security(access_scheme)],
    refresh_token: Annotated[str | None, Security(refresh_scheme)],
):
    """Revoke this refresh-token family and clear cookies; no global sign-out."""
    try:
        actor = auth.load_session(access_token or "", request=request).actor
    except HTTPException:
        actor = None  # an expired access token can still revoke its refresh family; it just isn't audited
    auth.logout(request, access_token or "", refresh_token or "")
    if actor:
        users.record(request, "STUDIO_SIGN_OUT", actor.username, actor=actor)
    for name in (auth.ACCESS_COOKIE, auth.REFRESH_COOKIE, auth.ROLE_COOKIE):
        response.delete_cookie(name, path=auth.COOKIE_PATH,
                               secure=settings.socratic_cookie_secure,
                               httponly=True, samesite="strict")
    response.headers["Cache-Control"] = "no-store"


Staff = Annotated[auth.StaffSession, Depends(require_staff)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128,
                                     pattern=r"^[A-Za-z0-9_-]+$")]
mutation_headers = {"parameters": [origin_parameter, csrf_parameter]}


class RoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["admin", "student"]


@router.put("/session/role", response_model=auth.StaffSession,
            openapi_extra={"parameters": [origin_parameter, csrf_parameter]})
def switch_role(request: Request, response: Response, body: RoleRequest,
                access_token: Annotated[str | None, Security(access_scheme)]):
    """Switch the active role among those the user's groups grant; access changes immediately."""
    response.headers["Cache-Control"] = "no-store"
    auth.check_csrf(request, access_token or "")
    current = auth.load_session(access_token or "", request=request)
    if body.role not in current.roles:
        raise auth.fail(403, "STAFF_ROLE_NOT_GRANTED", "Your group membership does not grant this role.")
    session = auth.load_session(access_token or "", request=request, role=body.role)
    set_role_cookie(response, session.role)
    users.record(request, "STUDIO_ROLE_SWITCHED", session.actor.username, actor=session.actor,
                 detail={"role": session.role})
    return session


class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: SecretStr = Field(min_length=1, max_length=256)
    new_password: SecretStr = Field(min_length=8, max_length=256)


@router.post("/session/password", status_code=204,
             openapi_extra={"parameters": [origin_parameter, csrf_parameter]})
def change_password(request: Request, response: Response, body: PasswordChangeRequest,
                    access_token: Annotated[str | None, Security(access_scheme)]):
    """Change your own password (current password required); other sessions keep their tokens until expiry."""
    response.headers["Cache-Control"] = "no-store"
    session = auth.load_session(access_token or "", request=request)
    auth.change_password(request, access_token or "", body.current_password.get_secret_value(),
                         body.new_password.get_secret_value())
    users.record(request, "STUDIO_PASSWORD_CHANGED", session.actor.username, actor=session.actor)


Username = Annotated[str, Path(min_length=1, max_length=128, pattern=r"^[^/\\\s]+$")]


def user_admin(staff: auth.StaffSession) -> auth.StaffActor:
    return auth.require_capability(staff, "manage_users")


@router.get("/users", response_model=users.UserPage)
def list_users(staff: Staff, q: Annotated[str | None, Query(max_length=64)] = None,
               limit: Annotated[int, Query(ge=1, le=60)] = 25,
               next_token: Annotated[str | None, Query(max_length=4096)] = None):
    """Search the Cognito user pool by email or username prefix (admin role only)."""
    user_admin(staff)
    return users.list_users(q, limit, next_token)


@router.get("/users/{username}", response_model=users.UserDetail)
def get_user(staff: Staff, username: Username):
    """User detail: status, groups, MFA and Studio access history (last 30 days + recent events)."""
    user_admin(staff)
    return users.get_user(username)


@router.put("/users/{username}/groups/{group}", response_model=users.UserDetail, openapi_extra=mutation_headers)
def add_group(request: Request, staff: Staff, username: Username,
              group: Annotated[str, Path(min_length=1, max_length=128)]):
    return users.add_group(user_admin(staff), username, group, request)


@router.delete("/users/{username}/groups/{group}", response_model=users.UserDetail, openapi_extra=mutation_headers)
def remove_group(request: Request, staff: Staff, username: Username,
                 group: Annotated[str, Path(min_length=1, max_length=128)]):
    return users.remove_group(user_admin(staff), username, group, request)


@router.post("/users/{username}/password-reset", response_model=users.UserDetail, openapi_extra=mutation_headers)
def reset_password(request: Request, staff: Staff, username: Username):
    """Force a password reset; Cognito emails the user a code (self-service 'forgot password' completes it)."""
    return users.reset_password(user_admin(staff), username, request)


@router.post("/users/{username}/sign-out", response_model=users.UserDetail, openapi_extra=mutation_headers)
def sign_out_everywhere(request: Request, staff: Staff, username: Username):
    """Invalidate all of the user's refresh tokens (every device)."""
    return users.global_sign_out(user_admin(staff), username, request)


class EnabledRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


@router.put("/users/{username}/enabled", response_model=users.UserDetail, openapi_extra=mutation_headers)
def set_enabled(request: Request, staff: Staff, username: Username, body: EnabledRequest):
    return users.set_enabled(user_admin(staff), username, body.enabled, request)


@router.get("/strategies", response_model=dict[str, list[contracts.Strategy]])
def strategies(staff: Staff):
    """List immutable DRAFT candidate strategies, not approved teaching policies."""
    auth.require_capability(staff, "author")
    return {"strategies": service.strategies()}


@router.get("/resources", response_model=contracts.ResourcePage)
def resources(staff: Staff, q: str = Query(default="", max_length=200),
              limit: int = Query(default=25, ge=1, le=100),
              offset: int = Query(default=0, ge=0, le=100000)):
    """Read source statements and solution/route references only; never solution bodies."""
    auth.require_capability(staff, "author")
    return service.resources(q, limit, offset)


@router.get("/workflows", response_model=contracts.WorkflowPage)
def workflows(staff: Staff, limit: int = Query(default=25, ge=1, le=100),
              offset: int = Query(default=0, ge=0, le=100000)):
    """Page only the signed-in author's own prototype drafts."""
    return service.list_workflows(auth.require_any(staff, "author", "preview"), limit, offset)


@router.post("/workflows", response_model=contracts.Workflow, status_code=201,
             openapi_extra=mutation_headers)
def create_workflow(body: contracts.CreateWorkflow, staff: Staff, key: IdempotencyKey):
    """Create an owned draft and atomically append revision, audit, outbox and replay receipt."""
    return service.create_workflow(body, auth.require_capability(staff, "author"), key)


@router.get("/workflows/{workflow_id}", response_model=contracts.Workflow)
def workflow(workflow_id: UUID, staff: Staff):
    """Return the current owned immutable draft revision; nonowner is indistinguishable from missing."""
    return service.get_workflow(workflow_id, auth.require_any(staff, "author", "preview"))


@router.get("/workflows/{workflow_id}/revisions/{revision}", response_model=contracts.Workflow)
def workflow_revision(workflow_id: UUID, revision: Annotated[int, Path(ge=1)], staff: Staff):
    """Read an immutable historical revision of an owned draft."""
    return service.get_workflow(workflow_id, auth.require_capability(staff, "author"), revision)


@router.put("/workflows/{workflow_id}", response_model=contracts.Workflow, openapi_extra=mutation_headers)
def update_workflow(workflow_id: UUID, body: contracts.UpdateWorkflow, staff: Staff, key: IdempotencyKey):
    """Save with expected-hash fencing and exact source checks; no publishing or AWS side effects."""
    return service.update_workflow(workflow_id, body, auth.require_capability(staff, "author"), key)


@router.post("/workflows/{workflow_id}/validate", response_model=contracts.Validation,
             openapi_extra=mutation_headers)
def validate_workflow(workflow_id: UUID, body: contracts.ValidateWorkflow, staff: Staff):
    """Check draft structure/dependency freshness only, never mathematical/release approval."""
    return service.validate_workflow(workflow_id, body.expected_hash, auth.require_capability(staff, "author"))


@router.post("/workflows/{workflow_id}/simulate", response_model=contracts.Preview, status_code=201,
             openapi_extra=mutation_headers)
def simulate(workflow_id: UUID, body: contracts.Simulate, staff: Staff):
    """Start a synthetic preview pinned to the exact saved hash and a private activity snapshot."""
    return preview.start_preview(workflow_id, body, auth.require_any(staff, "author", "preview"))


@router.get("/previews/{preview_id}", response_model=contracts.Preview)
def get_preview(preview_id: UUID, staff: Staff):
    """Current safe screen and decision history; never answer keys, hidden hints or future nodes."""
    return preview.get_preview(preview_id, auth.require_any(staff, "author", "preview"))


@router.post("/previews/{preview_id}/respond", response_model=contracts.Preview, openapi_extra=mutation_headers)
def respond_preview(preview_id: UUID, body: contracts.Respond, staff: Staff):
    """Score the current activity with the shared deterministic evaluator and route; no learner writes."""
    return preview.respond(preview_id, body, auth.require_any(staff, "author", "preview"))


@router.post("/previews/{preview_id}/assist", response_model=contracts.Preview, openapi_extra=mutation_headers)
def assist_preview(preview_id: UUID, body: contracts.PreviewCommand, staff: Staff):
    """Disclose the next approved hint for the current activity; recorded as assisted."""
    return preview.assist(preview_id, body, auth.require_any(staff, "author", "preview"))


@router.post("/previews/{preview_id}/reveal", response_model=contracts.Preview, openapi_extra=mutation_headers)
def reveal_preview(preview_id: UUID, body: contracts.PreviewCommand, staff: Staff):
    """Explicitly reveal the current explanation; later correct answers are not independent success."""
    return preview.reveal(preview_id, body, auth.require_any(staff, "author", "preview"))


@router.post("/previews/{preview_id}/transition", response_model=contracts.Preview, openapi_extra=mutation_headers)
def transition_preview(preview_id: UUID, body: contracts.Transition, staff: Staff):
    """Staff routing test with a simulated outcome; explicitly not a grade."""
    return preview.transition(preview_id, body, auth.require_any(staff, "author", "preview"))
