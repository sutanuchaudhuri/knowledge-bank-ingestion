"""Service-key identity bridge of the exam agent: students/onboard -> by-cognito-sub -> students/{id} -> mint-session-token
(+ mastery-summary, difficulty-distribution)."""
from __future__ import annotations

from uuid import uuid4

from apitest.context import Ctx
from apitest.journeys import journey
from apitest.journeys.exam_common import call, check, content_fixtures, email, good, js, keys_of, register, scan, svc

PROFILE_KEYS = {"student_id", "email", "first_name", "last_name", "display_name", "grade", "phone", "status"}
NEVER = {"password_hash", "password", "token_version", "cognito_sub_secret"}


@journey("exam_identity")
def exam_identity(ctx: Ctx) -> None:
    sub, addr = str(uuid4()), email(ctx, "ident")
    body = {"cognito_sub": sub, "first_name": "Ida", "last_name": "Cognito", "email": addr, "grade": "11", "phone": "+15550100"}
    r = svc(ctx, "onboard named", "POST", "/students/onboard", 200, json=body)
    if not good(r):
        return
    student = js(r)
    sid = student["student_id"]
    check(ctx, "onboard shape", PROFILE_KEYS <= set(student) and student["status"] == "ACTIVE" and student["email"] == addr
          and student["grade"] == "11", str(student))
    check(ctx, "onboard leaks no credential field", not (keys_of(student) & NEVER), str(sorted(keys_of(student))))

    again = svc(ctx, "onboard same identity again (idempotent)", "POST", "/students/onboard", 200, json=body)
    check(ctx, "second onboard returns the same student", good(again) and js(again)["student_id"] == sid, str(js(again)))

    svc(ctx, "onboard: taken email, other sub, unverified", "POST", "/students/onboard", 409, code="EMAIL_ALREADY_REGISTERED",
        json={**body, "cognito_sub": str(uuid4())})
    svc(ctx, "onboard: sub is not a uuid", "POST", "/students/onboard", {400, 422}, json={**body, "cognito_sub": "not-a-uuid", "email": email(ctx, "bad")})
    svc(ctx, "onboard: empty first_name", "POST", "/students/onboard", 422, json={**body, "first_name": ""})
    svc(ctx, "onboard: unknown field", "POST", "/students/onboard", 422, json={**body, "role": "admin"})

    anon_a = svc(ctx, "onboard anonymous #1", "POST", "/students/onboard", 200,
                 json={"cognito_sub": None, "first_name": "Anon", "last_name": "Ymous", "is_anonymous": True})
    anon_b = svc(ctx, "onboard anonymous #2", "POST", "/students/onboard", 200,
                 json={"cognito_sub": None, "first_name": "Anon", "last_name": "Ymous", "is_anonymous": True})
    if good(anon_a) and good(anon_b):
        check(ctx, "each anonymous onboarding is a new student", js(anon_a)["student_id"] != js(anon_b)["student_id"], "same id twice")

    # linking an existing password account: only with a verified e-mail
    pw = register(ctx, "linkme")
    if pw is not None:
        link_sub = str(uuid4())
        link = {"cognito_sub": link_sub, "first_name": "Api", "last_name": "Linkme", "email": pw.email}
        svc(ctx, "link existing account: email not verified", "POST", "/students/onboard", 409, json=link)
        linked = svc(ctx, "link existing account: email verified", "POST", "/students/onboard", 200, json={**link, "email_verified": True})
        check(ctx, "link keeps the existing student id", good(linked) and js(linked)["student_id"] == pw.sid, str(js(linked)))
        got = svc(ctx, "by-cognito-sub of the linked account", "GET", f"/students/by-cognito-sub/{link_sub}", 200)
        check(ctx, "by-cognito-sub resolves the linked student", good(got) and js(got)["student_id"] == pw.sid, str(js(got)))

    got = svc(ctx, "by-cognito-sub", "GET", f"/students/by-cognito-sub/{sub}", 200)
    check(ctx, "by-cognito-sub returns the onboarded student", good(got) and js(got)["student_id"] == sid and PROFILE_KEYS <= set(js(got)), str(js(got)))
    check(ctx, "by-cognito-sub leaks no credential field", good(got) and not (keys_of(js(got)) & NEVER), str(sorted(keys_of(js(got)))))
    up = svc(ctx, "by-cognito-sub (upper case)", "GET", f"/students/by-cognito-sub/{sub.upper()}", 200)
    check(ctx, "sub lookup is case-insensitive", good(up) and js(up)["student_id"] == sid, str(js(up)))
    svc(ctx, "by-cognito-sub unknown", "GET", f"/students/by-cognito-sub/{uuid4()}", 404, code="NOT_FOUND")

    prof = svc(ctx, "student profile", "GET", f"/students/{sid}", 200)
    if good(prof):
        p = js(prof)
        check(ctx, "profile shape", {"student_id", "email", "status", "created_at", "last_login_at"} <= set(p), str(sorted(p)))
        check(ctx, "profile leaks no credential field", not (keys_of(p) & NEVER), str(sorted(keys_of(p))))
    svc(ctx, "student profile unknown", "GET", f"/students/{uuid4()}", 404, code="NOT_FOUND")
    svc(ctx, "student profile malformed id", "GET", "/students/not-a-uuid", 422)

    minted = svc(ctx, "mint session token", "POST", f"/students/{sid}/mint-session-token", 200)
    if good(minted):
        m = js(minted)
        check(ctx, "mint shape", m.get("token_type") == "bearer" and m.get("student_id") == sid and m.get("access_token"), str(sorted(m)))
        token = m["access_token"]
        me = call(ctx, "minted token opens /v1/learner/me", "GET", "/v1/learner/me", 200, token=token)
        check(ctx, "token belongs to the onboarded student", good(me) and js(me).get("email") == addr, str(js(me)))
        mine = call(ctx, "minted token opens /v1/quiz/mine", "GET", "/v1/quiz/mine", 200, token=token)
        check(ctx, "a new learner has no quizzes", good(mine) and js(mine) == [], str(js(mine)))
        scan(ctx, "quiz/mine of a new learner", mine)
        after = svc(ctx, "profile after mint", "GET", f"/students/{sid}", 200)
        check(ctx, "mint stamps last_login_at", good(after) and js(after).get("last_login_at") is not None, str(js(after)))
    svc(ctx, "mint for an unknown student", "POST", f"/students/{uuid4()}/mint-session-token", 404, code="NOT_FOUND")

    ms = svc(ctx, "mastery-summary of a new student", "GET", f"/students/{sid}/mastery-summary", 200)
    if good(ms):
        check(ctx, "mastery-summary shape", isinstance(js(ms).get("concepts"), list) and isinstance(js(ms).get("techniques"), list), str(js(ms)))
    svc(ctx, "mastery-summary of an unknown student", "GET", f"/students/{uuid4()}/mastery-summary", {200, 404})

    # difficulty-distribution is a content read (dev) the generator uses
    svc(ctx, "difficulty-distribution needs a slug", "GET", "/difficulty-distribution", 422)
    unknown = svc(ctx, "difficulty-distribution unknown concept", "GET", "/difficulty-distribution", 200, params={"concept_slug": f"no-such-{ctx.run_id}"})
    check(ctx, "unknown slug -> empty distribution", good(unknown) and js(unknown) == {"distribution": {}}, str(js(unknown)))
    fx = content_fixtures(ctx)
    for kind, slugs in (("concept_slug", fx["concepts"]), ("technique_slug", fx["techniques"])):
        if slugs:
            d = svc(ctx, f"difficulty-distribution {kind}", "GET", "/difficulty-distribution", 200, params={kind: slugs[0]})
            if good(d):
                dist = js(d).get("distribution")
                check(ctx, f"distribution ({kind}) is band -> count", isinstance(dist, dict) and all(isinstance(v, int) for v in dist.values())
                      and set(dist) <= {"easy", "medium", "hard", "very_hard"}, str(js(d)))
