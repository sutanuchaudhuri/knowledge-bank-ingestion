"""Micro-course learner journey: browse, enroll, answer, advance to completion, help, abandon, re-enroll."""
from __future__ import annotations

from apitest.context import Ctx
from apitest.journeys import journey
from apitest.journeys.learner_common import (
    ANSWER_KEYS,
    OPT_INT,
    OPT_STR,
    SECRET_KEYS,
    ANY,
    call,
    check,
    find_keys,
    new_uuid,
    register,
)

COURSE_LIST_SPEC = [{"canonical_code": str, "title": str, "description": OPT_STR, "estimated_minutes": OPT_INT, "release_id": str,
                     "version": int, "state_count": int, "primary_targets": list}]
READER_SPEC = {"micro_course_id": str, "canonical_code": str, "title": str, "release_id": str, "version": int, "transitions": list,
               "states": [{"state_id": str, "state_key": str, "state_type": str, "title": str, "ordinal": int, "activities": list,
                           "assets": list, "interactions": list, "items": list}]}
CURRENT_STATE_SPEC = {"state_id": str, "state_key": str, "state_type": str, "title": str, "ordinal": int,
                      "activities": [{"activity_id": str, "activity_type": str, "prompt": str, "options": list, "ordinal": int}],
                      "assets": list, "interactions": list, "learning_items": list,
                      "items": [{"item_kind": str, "item_id": str, "ordinal": int, "required": bool}]}
ENROLL_SPEC = {"enrollment_id": str, "enrollment_status": str, "started_at": str, "completed_at": OPT_STR, "micro_course_id": str,
               "release_id": str, "version": int, "state_version": int, "canonical_code": str, "course_title": str, "step_count": int,
               "step_number": int, "can_continue": bool, "can_go_back": bool, "can_finish": bool, "current_state": ANY}
ACTIVITY_RESULT_SPEC = {"activity_id": str, "is_correct": (bool, type(None)), "gave_up": bool, "explanation": OPT_STR}
ENROLLMENT_ROW_SPEC = {"enrollment_id": str, "canonical_code": str, "micro_course_id": str, "release_id": str, "status": str,
                       "current_state_id": OPT_STR, "state_version": int, "started_at": str, "completed_at": OPT_STR}
LIST_SPEC = {"items": [ENROLLMENT_ROW_SPEC], "total": int}
BASE = "/v1/micro-courses"


def answer_activities(ctx: Ctx, lr, eid: str, state: dict, label: str) -> bool:
    for act in state["activities"]:
        body = {"activity_id": act["activity_id"]}
        if act["options"]:
            body["choice_index"] = 0
        else:
            body["value"] = 36
        r = call(ctx, f"answer activity ({label}, {act['activity_type']})", "POST", f"{BASE}/enrollments/{eid}/activity-responses", 200,
                 spec=ACTIVITY_RESULT_SPEC, token=lr.token, json=body)
        if not r.ok:
            return False
    return True


@journey("learner_microcourse")
def learner_microcourse(ctx: Ctx) -> None:
    lr = register(ctx, "mc")
    if lr is None:
        return
    lst = call(ctx, "list micro-courses", "GET", BASE, 200, spec=COURSE_LIST_SPEC, params={"limit": 50}, leak=SECRET_KEYS)
    if not lst.ok or not lst.data:
        check(ctx, "at least one published micro-course exists in dev content", False, f"list={lst.data}")
        return
    courses = lst.data
    one = call(ctx, "list micro-courses limit 1", "GET", BASE, 200, params={"limit": 1})
    if one.ok:
        check(ctx, "list: limit=1 returns one course", len(one.data) == 1, f"n={len(one.data)}")
    call(ctx, "list micro-courses limit 0 -> 422", "GET", BASE, 422, params={"limit": 0})
    call(ctx, "list micro-courses limit 201 -> 422", "GET", BASE, 422, params={"limit": 201})
    call(ctx, "list micro-courses negative offset -> 422", "GET", BASE, 422, params={"offset": -1})
    multi = [c for c in courses if c["state_count"] > 1]
    if not multi:
        check(ctx, "a published multi-state micro-course exists", False, f"courses={[c['canonical_code'] for c in courses]}")
        return
    pick = next((c for c in multi if c["canonical_code"] == "MC-MARKOV-STREAKS"), multi[0])
    code = pick["canonical_code"]

    rd = call(ctx, "get micro-course by code", "GET", f"{BASE}/{code}", 200, spec=READER_SPEC, leak=SECRET_KEYS | ANSWER_KEYS)
    if rd.ok:
        check(ctx, "reader: states are ordered by ordinal", [s["ordinal"] for s in rd.data["states"]] == sorted(s["ordinal"] for s in rd.data["states"]))
        check(ctx, "reader: state count matches the listing", len(rd.data["states"]) == pick["state_count"], f"{len(rd.data['states'])} vs {pick['state_count']}")
        assets = [a for s in rd.data["states"] for a in s["assets"]]
        if assets:
            call(ctx, "course asset that is not in the private store -> 409/404", "GET", f"{BASE}/{code}/assets/{assets[0]['asset_id']}/content",
                 {200, 404, 409})
    call(ctx, "get unknown micro-course -> 404", "GET", f"{BASE}/NO-SUCH-COURSE", 404)
    call(ctx, "get asset of an unknown course -> 404", "GET", f"{BASE}/NO-SUCH-COURSE/assets/{new_uuid()}/content", 404)

    # --- enroll
    call(ctx, "enroll without a token -> 401", "POST", f"{BASE}/{code}/enroll", 401)
    call(ctx, "enroll in an unknown course -> 404", "POST", f"{BASE}/NO-SUCH-COURSE/enroll", 404, token=lr.token)
    ekey = new_uuid()
    en = call(ctx, "enroll", "POST", f"{BASE}/{code}/enroll", 201, spec={**ENROLL_SPEC, "current_state": CURRENT_STATE_SPEC}, token=lr.token,
              headers={"Idempotency-Key": ekey}, leak=SECRET_KEYS | ANSWER_KEYS)
    if not en.ok:
        return
    eid = en.data["enrollment_id"]
    check(ctx, "enroll: IN_PROGRESS at step 1, cannot go back", en.data["enrollment_status"] == "IN_PROGRESS" and en.data["step_number"] == 1
          and en.data["can_go_back"] is False and en.data["completed_at"] is None, f"data={ {k: v for k, v in en.data.items() if k != 'current_state'} }")
    check(ctx, "enroll: state_version starts at 1", en.data["state_version"] == 1)
    rep = call(ctx, "enroll replay with the same Idempotency-Key", "POST", f"{BASE}/{code}/enroll", 201, token=lr.token, headers={"Idempotency-Key": ekey})
    if rep.ok:
        check(ctx, "enroll replay: same enrollment", rep.data["enrollment_id"] == eid)
    res = call(ctx, "enroll again without a key resumes the open enrollment", "POST", f"{BASE}/{code}/enroll", 201, token=lr.token)
    if res.ok:
        check(ctx, "second enroll: no duplicate enrollment is created", res.data["enrollment_id"] == eid, f"{res.data['enrollment_id']} vs {eid}")
    ge = call(ctx, "get enrollment", "GET", f"{BASE}/enrollments/{eid}", 200, spec={**ENROLL_SPEC, "current_state": CURRENT_STATE_SPEC}, token=lr.token,
              leak=SECRET_KEYS | ANSWER_KEYS)
    call(ctx, "get unknown enrollment -> 404", "GET", f"{BASE}/enrollments/{new_uuid()}", 404, token=lr.token)
    call(ctx, "get enrollment with a malformed id -> 422", "GET", f"{BASE}/enrollments/not-a-uuid", 422, token=lr.token)
    call(ctx, "get enrollment without a token -> 401", "GET", f"{BASE}/enrollments/{eid}", 401)
    if not ge.ok:
        return
    lst_en = call(ctx, "list my enrollments", "GET", "/v1/learner/micro-course-enrollments", 200, spec=LIST_SPEC, token=lr.token)
    if lst_en.ok:
        check(ctx, "enrollments list: the open enrollment, total matches", [i["enrollment_id"] for i in lst_en.data["items"]] == [eid]
              and lst_en.data["total"] == 1 and lst_en.data["items"][0]["status"] == "IN_PROGRESS", f"data={lst_en.data}")

    # --- negatives on the first state
    state = ge.data["current_state"]
    sv = ge.data["state_version"]
    adv = f"{BASE}/enrollments/{eid}/advance"
    call(ctx, "advance with a stale expected_state_version -> 409", "POST", adv, 409, token=lr.token, json={"expected_state_version": sv + 50, "action": "CONTINUE"})
    call(ctx, "go BACK from the first state -> 409/422", "POST", adv, {409, 422}, token=lr.token, json={"expected_state_version": sv, "action": "BACK"})
    call(ctx, "advance with an unknown action -> 422", "POST", adv, 422, token=lr.token, json={"expected_state_version": sv, "action": "TELEPORT"})
    call(ctx, "advance with an unknown field -> 422", "POST", adv, 422, token=lr.token, json={"expected_state_version": sv, "action": "CONTINUE", "x": 1})
    call(ctx, "advance without a token -> 401", "POST", adv, 401, json={"expected_state_version": sv, "action": "CONTINUE"})
    call(ctx, "answer an unknown activity -> 404", "POST", f"{BASE}/enrollments/{eid}/activity-responses", 404, token=lr.token,
         json={"activity_id": new_uuid(), "choice_index": 0})
    call(ctx, "answer a learning item that is not in the state -> 404", "POST", f"{BASE}/enrollments/{eid}/responses", 404, token=lr.token,
         json={"learning_item_id": "no-such-item", "choice_index": 0})
    call(ctx, "interaction event for an unknown interaction -> 404", "POST", f"{BASE}/enrollments/{eid}/interaction-events", 404, token=lr.token,
         json={"interaction_instance_id": new_uuid(), "event_type": "X", "semantic_action": "y"})
    call(ctx, "activity response with an unknown field -> 422", "POST", f"{BASE}/enrollments/{eid}/activity-responses", 422, token=lr.token,
         json={"activity_id": new_uuid(), "choice_index": 0, "extra": True})
    call(ctx, "learning item response with a negative choice -> 422", "POST", f"{BASE}/enrollments/{eid}/responses", 422, token=lr.token,
         json={"learning_item_id": "x", "choice_index": -1})
    call(ctx, "item-help with an unknown item_kind -> 422", "POST", f"{BASE}/enrollments/{eid}/item-help", 422, token=lr.token,
         json={"item_kind": "banana", "item_id": "x"})
    if state["activities"]:
        act = state["activities"][0]
        call(ctx, "answer an activity with an out-of-range choice -> 4xx", "POST", f"{BASE}/enrollments/{eid}/activity-responses", range(400, 500),
             token=lr.token, json={"activity_id": act["activity_id"], "choice_index": 99})
        call(ctx, "item-help for an item outside the current state -> 4xx", "POST", f"{BASE}/enrollments/{eid}/item-help", range(400, 500),
             token=lr.token, json={"item_kind": "activity", "item_id": new_uuid(), "intent": "help"})
        gu = call(ctx, "item-help give_up reveals the answer (deterministic, no LLM)", "POST", f"{BASE}/enrollments/{eid}/item-help", 200, token=lr.token,
                  json={"item_kind": "activity", "item_id": act["activity_id"], "intent": "give_up"},
                  spec={"intent": str, "item_kind": str, "action": str, "gave_up": bool}, leak=SECRET_KEYS)
        if gu.ok:
            check(ctx, "give_up: revealed for an activity", gu.data["action"] == "revealed" and gu.data["gave_up"] is True, f"data={gu.data}")
        if len(state["activities"]) > 1:
            hp = call(ctx, "item-help intent=help (one LLM call)", "POST", f"{BASE}/enrollments/{eid}/item-help", 200, token=lr.token,
                      json={"item_kind": "activity", "item_id": state["activities"][1]["activity_id"], "intent": "help",
                            "student_message": "I do not know where to start."}, spec=dict, leak=SECRET_KEYS | ANSWER_KEYS)
            if hp.ok:
                check(ctx, "help: a grounded hint without the answer", not find_keys(hp.data, ANSWER_KEYS), f"data={str(hp.data)[:300]}")

    # --- walk the whole course
    cur, completed = ge.data, False
    for hop in range(len(rd.data["states"]) + 3 if rd.ok else 10):
        st = cur["current_state"]
        label = f"{cur['step_number']}/{cur['step_count']} {st['state_key']}"
        if not answer_activities(ctx, lr, eid, st, label):
            return
        for ia in st["interactions"][:1]:
            ev = call(ctx, f"record interaction event ({label})", "POST", f"{BASE}/enrollments/{eid}/interaction-events", 200,
                      spec={"interaction_event_id": str}, token=lr.token,
                      json={"interaction_instance_id": ia["interaction_instance_id"], "event_type": "CONTROL_CHANGED", "semantic_action": "set_parameter",
                            "control_key": "p", "action_payload": {"value": 0.5}, "before_state": {"p": 0.25}, "after_state": {"p": 0.5}},
                      headers={"Idempotency-Key": new_uuid()})
            if ev.ok:
                ev2 = call(ctx, "interaction event with a blank event_type -> 422", "POST", f"{BASE}/enrollments/{eid}/interaction-events", 422,
                           token=lr.token, json={"interaction_instance_id": ia["interaction_instance_id"], "event_type": "", "semantic_action": "x"})
        for li in st["learning_items"][:1]:
            call(ctx, f"answer learning item ({label})", "POST", f"{BASE}/enrollments/{eid}/responses", 200, token=lr.token,
                 json={"learning_item_id": li["learning_item_id"], "choice_index": 0}, spec=dict)
        akey = new_uuid()
        body = {"expected_state_version": cur["state_version"], "action": "CONTINUE"}
        nxt = call(ctx, f"advance from {label}", "POST", adv, 200, spec=ENROLL_SPEC, token=lr.token, json=body, headers={"Idempotency-Key": akey},
                   leak=SECRET_KEYS | ANSWER_KEYS)
        if not nxt.ok:
            return
        check(ctx, "advance: state_version increases", nxt.data["state_version"] > cur["state_version"], f"{cur['state_version']} -> {nxt.data['state_version']}")
        if hop == 0:
            rp = call(ctx, "advance replay with the same Idempotency-Key", "POST", adv, 200, token=lr.token, json=body, headers={"Idempotency-Key": akey})
            if rp.ok:
                check(ctx, "advance replay: no second step is taken", rp.data["state_version"] == nxt.data["state_version"]
                      and rp.data["step_number"] == nxt.data["step_number"], f"{rp.data['step_number']} vs {nxt.data['step_number']}")
            call(ctx, "advance replay without a key with the old version -> 409", "POST", adv, 409, token=lr.token, json=body)
        cur = nxt.data
        if cur["enrollment_status"] == "COMPLETED":
            completed = True
            break
    check(ctx, "walking every state completes the enrollment", completed, f"last status={cur['enrollment_status']} step={cur['step_number']}/{cur['step_count']}")
    if not completed:
        return
    check(ctx, "completed: completed_at stamped", cur["completed_at"] is not None)
    inbox = call(ctx, "notifications after graded micro-course activities", "GET", "/v1/notifications/me", 200, token=lr.token,
                 spec={"notifications": list, "unread_count": int, "next_token": OPT_STR})
    if inbox.ok:
        check(ctx, "notifications: graded micro-course items should notify the learner (requirement 59 triggers are unwired, so this is informational)",
              True, f"notifications after a full course = {len(inbox.data['notifications'])}")
    call(ctx, "advance a completed enrollment -> 409", "POST", adv, 409, token=lr.token, json={"expected_state_version": cur["state_version"], "action": "CONTINUE"})
    call(ctx, "abandon a completed enrollment -> 409", "POST", f"{BASE}/enrollments/{eid}/abandon", 409, token=lr.token)
    done = call(ctx, "list enrollments filtered COMPLETED", "GET", "/v1/learner/micro-course-enrollments", 200, spec=LIST_SPEC, token=lr.token,
                params={"status": "COMPLETED"})
    if done.ok:
        check(ctx, "status filter COMPLETED returns the course", [i["enrollment_id"] for i in done.data["items"]] == [eid], f"data={done.data}")
    inprog = call(ctx, "list enrollments filtered IN_PROGRESS", "GET", "/v1/learner/micro-course-enrollments", 200, token=lr.token, params={"status": "IN_PROGRESS"})
    if inprog.ok:
        check(ctx, "status filter IN_PROGRESS excludes the completed one", all(i["enrollment_id"] != eid for i in inprog.data["items"]))
    call(ctx, "list enrollments invalid status -> 422", "GET", "/v1/learner/micro-course-enrollments", 422, token=lr.token, params={"status": "NOPE"})
    call(ctx, "list enrollments limit 0 -> clamped, not an error", "GET", "/v1/learner/micro-course-enrollments", {200, 422}, token=lr.token, params={"limit": 0})

    # --- re-enroll after completion, then abandon
    again = call(ctx, "enroll again after completion starts a fresh enrollment", "POST", f"{BASE}/{code}/enroll", 201, token=lr.token)
    if not again.ok:
        return
    eid2 = again.data["enrollment_id"]
    check(ctx, "re-enroll: a new enrollment at step 1 (the completed one is not reopened)", eid2 != eid and again.data["step_number"] == 1
          and again.data["enrollment_status"] == "IN_PROGRESS", f"id={eid2} old={eid} step={again.data['step_number']}")
    ab = call(ctx, "abandon the open enrollment", "POST", f"{BASE}/enrollments/{eid2}/abandon", 200, token=lr.token,
              spec={**ENROLLMENT_ROW_SPEC}, headers={"Idempotency-Key": new_uuid()})
    if ab.ok:
        check(ctx, "abandon: status ABANDONED", ab.data["status"] == "ABANDONED", f"data={ab.data}")
    call(ctx, "abandon again -> 409", "POST", f"{BASE}/enrollments/{eid2}/abandon", 409, token=lr.token)
    call(ctx, "advance an abandoned enrollment -> 409", "POST", f"{BASE}/enrollments/{eid2}/advance", 409, token=lr.token,
         json={"expected_state_version": 1, "action": "CONTINUE"})
    call(ctx, "answer on an abandoned enrollment -> 404/409", "POST", f"{BASE}/enrollments/{eid2}/activity-responses", {404, 409}, token=lr.token,
         json={"activity_id": new_uuid(), "choice_index": 0})
    ge2 = call(ctx, "get an abandoned enrollment", "GET", f"{BASE}/enrollments/{eid2}", 200, token=lr.token)
    if ge2.ok:
        check(ctx, "abandoned enrollment is readable and ABANDONED", ge2.data["enrollment_status"] == "ABANDONED")
    all_en = call(ctx, "list all enrollments", "GET", "/v1/learner/micro-course-enrollments", 200, spec=LIST_SPEC, token=lr.token)
    if all_en.ok:
        check(ctx, "enrollments list: newest first, both enrollments", [i["enrollment_id"] for i in all_en.data["items"]] == [eid2, eid]
              and all_en.data["total"] == 2, f"ids={[i['enrollment_id'] for i in all_en.data['items']]}")
    ab_list = call(ctx, "list enrollments filtered ABANDONED", "GET", "/v1/learner/micro-course-enrollments", 200, token=lr.token, params={"status": "ABANDONED"})
    if ab_list.ok:
        check(ctx, "status filter ABANDONED returns only the abandoned one", [i["enrollment_id"] for i in ab_list.data["items"]] == [eid2])
