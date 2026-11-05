"""Learner identity: register, login, profile, password change (token_version revocation), rate limit."""
from __future__ import annotations

from apitest.context import Ctx
from apitest.journeys import journey
from apitest.journeys.learner_common import (
    AUTH_SPEC,
    NEW_PASSWORD,
    PASSWORD,
    PROFILE_SPEC,
    call,
    check,
    claims,
    new_email,
    new_uuid,
    register,
)

ME = "/v1/learner/me"


@journey("learner_identity")
def learner_identity(ctx: Ctx) -> None:
    lr = register(ctx, "ident", first="Ada", last="Lovelace")
    if lr is None:
        return
    reg_claims = claims(lr.token)
    check(ctx, "register token: sub is the student id", reg_claims.get("sub") == lr.student_id, f"claims={reg_claims}")
    check(ctx, "register token: has exp and iat", "exp" in reg_claims and "iat" in reg_claims, f"claims={reg_claims}")

    # --- registration negatives
    dup = call(ctx, "register duplicate email -> 409", "POST", "/v1/learner/register", 409,
               json={"email": lr.email, "password": PASSWORD, "first_name": "X", "last_name": "Y"})
    check(ctx, "duplicate-email 409 carries a string detail", isinstance(dup.detail, str), f"detail={dup.detail!r}")
    call(ctx, "register duplicate email in another letter case -> 409", "POST", "/v1/learner/register", 409,
         json={"email": lr.email.upper(), "password": PASSWORD, "first_name": "X", "last_name": "Y"})
    call(ctx, "register password shorter than 8 -> 422", "POST", "/v1/learner/register", 422,
         json={"email": new_email(ctx, "short"), "password": "abc1234", "first_name": "X", "last_name": "Y"})
    call(ctx, "register malformed email -> 422", "POST", "/v1/learner/register", 422,
         json={"email": "not-an-email", "password": PASSWORD, "first_name": "X", "last_name": "Y"})
    call(ctx, "register missing last_name -> 422", "POST", "/v1/learner/register", 422,
         json={"email": new_email(ctx, "nolast"), "password": PASSWORD, "first_name": "X"})
    call(ctx, "register first_name over 100 chars -> 422", "POST", "/v1/learner/register", 422,
         json={"email": new_email(ctx, "long"), "password": PASSWORD, "first_name": "x" * 101, "last_name": "Y"})
    call(ctx, "register whitespace-only first_name -> 422 (PATCH /me rejects blank names)", "POST", "/v1/learner/register", 422,
         json={"email": new_email(ctx, "blank"), "password": PASSWORD, "first_name": "   ", "last_name": "Y"})

    uni_email = new_email(ctx, "uni")
    uni = call(ctx, "register with non-ASCII names", "POST", "/v1/learner/register", 201, spec=AUTH_SPEC,
               json={"email": uni_email, "password": PASSWORD, "first_name": "Zoë", "last_name": "李小龍"})
    if uni.ok:
        uni_me = call(ctx, "non-ASCII profile round-trips", "GET", ME, 200, spec=PROFILE_SPEC, token=uni.data["access_token"])
        if uni_me.ok:
            check(ctx, "non-ASCII names are stored intact", uni_me.data["first_name"] == "Zoë" and uni_me.data["last_name"] == "李小龍"
                  and uni_me.data["display_name"] == "Zoë 李小龍", f"profile={uni_me.data}")

    # register has no Idempotency-Key handling: a replay is a plain duplicate (409). A 201 replay would have to be the same student.
    key, em = new_uuid(), new_email(ctx, "idem")
    body = {"email": em, "password": PASSWORD, "first_name": "Idem", "last_name": "Potent"}
    first = call(ctx, "register with Idempotency-Key", "POST", "/v1/learner/register", 201, spec=AUTH_SPEC, json=body,
                 headers={"Idempotency-Key": key})
    if first.ok:
        replay = call(ctx, "register replay with the same Idempotency-Key (not supported -> 409, or 201 replaying the same student)",
                      "POST", "/v1/learner/register", {201, 409}, json=body, headers={"Idempotency-Key": key})
        if replay.status == 201:
            check(ctx, "register replay returns the same student", replay.data["student_id"] == first.data["student_id"])
        else:
            check(ctx, "register: Idempotency-Key is not honoured (replay is a duplicate 409)", True,
                  "POST /v1/learner/register ignores Idempotency-Key; replay -> 409 an account with this email already exists")

    # --- login
    login = call(ctx, "login", "POST", "/v1/learner/login", 200, spec=AUTH_SPEC, json={"email": lr.email, "password": lr.password})
    if not login.ok:
        return
    tok_login = login.data["access_token"]
    check(ctx, "login: same student id as register", login.data["student_id"] == lr.student_id)
    login_claims = claims(tok_login)
    check(ctx, "login token carries an integer tv claim", isinstance(login_claims.get("tv"), int), f"claims={login_claims}")
    tv0 = login_claims.get("tv", 0)
    bad = call(ctx, "login wrong password -> 401", "POST", "/v1/learner/login", 401, json={"email": lr.email, "password": "wrong-password-1"})
    unk = call(ctx, "login unknown email -> 401", "POST", "/v1/learner/login", 401,
               json={"email": new_email(ctx, "ghost"), "password": PASSWORD})
    check(ctx, "login: unknown email and wrong password give the same detail (no user enumeration)", bad.detail == unk.detail,
          f"{bad.detail!r} vs {unk.detail!r}")
    call(ctx, "login is case-insensitive on the email", "POST", "/v1/learner/login", 200, spec=AUTH_SPEC,
         json={"email": lr.email.upper(), "password": lr.password})
    call(ctx, "login empty body -> 422", "POST", "/v1/learner/login", 422, json={})

    # --- me
    me = call(ctx, "get me", "GET", ME, 200, spec=PROFILE_SPEC, token=tok_login)
    if me.ok:
        d = me.data
        check(ctx, "me: identity matches registration", d["student_id"] == lr.student_id and d["email"].lower() == lr.email.lower()
              and d["first_name"] == "Ada" and d["last_name"] == "Lovelace", f"profile={d}")
        check(ctx, "me: status is ACTIVE", d["status"] == "ACTIVE")
        check(ctx, "me: last_login_at is stamped by login", d["last_login_at"] is not None, f"last_login_at={d['last_login_at']}")
        check(ctx, "me: display_name defaults to the full name", d["display_name"] == "Ada Lovelace", f"display_name={d['display_name']}")
    call(ctx, "get me without a token -> 401", "GET", ME, 401)

    # --- patch me
    p = call(ctx, "patch first_name", "PATCH", ME, 200, spec=PROFILE_SPEC, token=tok_login, json={"first_name": "Grace"})
    if p.ok:
        check(ctx, "patch: display_name follows the names", p.data["display_name"] == "Grace Lovelace", f"display_name={p.data['display_name']}")
    p = call(ctx, "patch grade and phone", "PATCH", ME, 200, spec=PROFILE_SPEC, token=tok_login, json={"grade": "10", "phone": "+15551230000"})
    if p.ok:
        check(ctx, "patch: grade/phone stored, names unchanged",
              p.data["grade"] == "10" and p.data["phone"] == "+15551230000" and p.data["first_name"] == "Grace", f"profile={p.data}")
    p = call(ctx, "patch explicit display_name", "PATCH", ME, 200, token=tok_login, json={"display_name": "The Countess"})
    if p.ok:
        check(ctx, "patch: explicit display_name sticks", p.data["display_name"] == "The Countess")
    me2 = call(ctx, "get me after patches", "GET", ME, 200, spec=PROFILE_SPEC, token=tok_login)
    if me2.ok:
        check(ctx, "patches persisted", me2.data["first_name"] == "Grace" and me2.data["grade"] == "10"
              and me2.data["display_name"] == "The Countess", f"profile={me2.data}")
    p = call(ctx, "patch grade null clears it", "PATCH", ME, 200, token=tok_login, json={"grade": None})
    if p.ok:
        check(ctx, "patch: grade cleared", p.data["grade"] is None, f"grade={p.data['grade']}")
    call(ctx, "patch email -> 422 (identity fields are not editable)", "PATCH", ME, 422, token=tok_login, json={"email": new_email(ctx, "x")})
    call(ctx, "patch first_name null -> 422", "PATCH", ME, 422, token=tok_login, json={"first_name": None})
    call(ctx, "patch first_name empty -> 422", "PATCH", ME, 422, token=tok_login, json={"first_name": ""})
    call(ctx, "patch first_name whitespace -> 422", "PATCH", ME, 422, token=tok_login, json={"first_name": "   "})
    call(ctx, "patch first_name over 100 chars -> 422", "PATCH", ME, 422, token=tok_login, json={"first_name": "x" * 101})
    call(ctx, "patch phone over 30 chars -> 422", "PATCH", ME, 422, token=tok_login, json={"phone": "1" * 31})
    call(ctx, "patch without a token -> 401", "PATCH", ME, 401, json={"first_name": "Nope"})

    # --- password change revokes every older token (tv claim)
    PW = f"{ME}/password"
    call(ctx, "change password: wrong current -> 403", "POST", PW, 403, token=tok_login,
         json={"current_password": "not-my-password", "new_password": NEW_PASSWORD})
    call(ctx, "change password: new password too short -> 422", "POST", PW, 422, token=tok_login,
         json={"current_password": PASSWORD, "new_password": "short"})
    call(ctx, "change password: unknown field -> 422", "POST", PW, 422, token=tok_login,
         json={"current_password": PASSWORD, "new_password": NEW_PASSWORD, "extra": 1})
    call(ctx, "change password without a token -> 401", "POST", PW, 401, json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})
    ch = call(ctx, "change password", "POST", PW, 200, spec={"changed": bool, "access_token": str, "token_type": str}, token=tok_login,
              json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})
    if not ch.ok:
        return
    new_tok = ch.data["access_token"]
    new_claims = claims(new_tok)
    check(ctx, "change password: fresh token carries tv = old tv + 1", new_claims.get("tv") == tv0 + 1, f"old tv={tv0} new claims={new_claims}")
    call(ctx, "old register token is rejected after the password change (no tv claim)", "GET", ME, 401, token=lr.token)
    call(ctx, "old login token is rejected after the password change (tv revoked)", "GET", ME, 401, token=tok_login)
    call(ctx, "fresh token from the password change works", "GET", ME, 200, spec=PROFILE_SPEC, token=new_tok)
    call(ctx, "login with the old password -> 401", "POST", "/v1/learner/login", 401, json={"email": lr.email, "password": PASSWORD})
    relog = call(ctx, "login with the new password", "POST", "/v1/learner/login", 200, spec=AUTH_SPEC,
                 json={"email": lr.email, "password": NEW_PASSWORD})
    if relog.ok:
        check(ctx, "re-login token carries the bumped tv", claims(relog.data["access_token"]).get("tv") == tv0 + 1)
        call(ctx, "re-login token works", "GET", ME, 200, spec=PROFILE_SPEC, token=relog.data["access_token"])
        call(ctx, "old-password change attempt with the stale token is rejected", "POST", PW, 401, token=tok_login,
             json={"current_password": NEW_PASSWORD, "new_password": PASSWORD})


@journey("learner_password_rate_limit")
def learner_password_rate_limit(ctx: Ctx) -> None:
    lr = register(ctx, "pwrl")
    if lr is None:
        return
    pw = f"{ME}/password"
    for i in range(1, 6):
        call(ctx, f"change password wrong current #{i} -> 403", "POST", pw, 403, token=lr.token,
             json={"current_password": f"wrong-password-{i}", "new_password": NEW_PASSWORD})
    call(ctx, "change password after 5 attempts in 15 minutes -> 429 (even with the right password)", "POST", pw, 429, token=lr.token,
         json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})
    call(ctx, "account still works with the original password after the lock", "POST", "/v1/learner/login", 200, spec=AUTH_SPEC,
         json={"email": lr.email, "password": PASSWORD})
