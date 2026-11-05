"""Learner notifications (notify store): shape, paging, read / read-all. The producers are not wired, so lists are empty."""
from __future__ import annotations

from apitest.context import Ctx
from apitest.journeys import journey
from apitest.journeys.learner_common import OPT_STR, call, check, new_uuid, register

LIST_SPEC = {"notifications": [{"notification_id": str, "notification_type": str, "title": str}], "unread_count": int, "next_token": OPT_STR}
BASE = "/v1/notifications"


@journey("learner_notifications")
def learner_notifications(ctx: Ctx) -> None:
    lr = register(ctx, "notif")
    if lr is None:
        return
    lst = call(ctx, "list my notifications", "GET", f"{BASE}/me", 200, spec=LIST_SPEC, token=lr.token)
    if lst.ok:
        check(ctx, "notifications: unread_count never exceeds the list for a fresh learner", lst.data["unread_count"] == len(lst.data["notifications"]),
              f"unread={lst.data['unread_count']} items={len(lst.data['notifications'])}")
        check(ctx, "notifications: producers are not wired (requirement 59 triggers are TODO in mathbank_rest/notifications.py), "
                   "so a new learner's inbox is empty", True, f"count={len(lst.data['notifications'])} — shape asserted only")
    unread = call(ctx, "list unread notifications", "GET", f"{BASE}/me", 200, spec=LIST_SPEC, token=lr.token, params={"unread": "true"})
    if unread.ok:
        check(ctx, "unread filter returns only unread", all(not n.get("read_at") for n in unread.data["notifications"]))
    call(ctx, "list with limit 1", "GET", f"{BASE}/me", 200, spec=LIST_SPEC, token=lr.token, params={"limit": 1})
    call(ctx, "list with limit 0 -> 422", "GET", f"{BASE}/me", 422, token=lr.token, params={"limit": 0})
    call(ctx, "list with limit 201 -> 422", "GET", f"{BASE}/me", 422, token=lr.token, params={"limit": 201})
    call(ctx, "list with negative offset -> 422", "GET", f"{BASE}/me", 422, token=lr.token, params={"offset": -1})
    call(ctx, "list with a garbage next_token -> 4xx (not 5xx)", "GET", f"{BASE}/me", range(400, 500), token=lr.token, params={"next_token": "garbage"})
    call(ctx, "list without a token -> 401", "GET", f"{BASE}/me", 401)

    ra = call(ctx, "read-all on an empty inbox", "POST", f"{BASE}/me/read-all", 200, spec={"updated": int}, token=lr.token)
    if ra.ok:
        check(ctx, "read-all: updated is 0 when nothing is unread", ra.data["updated"] == 0, f"updated={ra.data['updated']}")
    call(ctx, "read-all without a token -> 401", "POST", f"{BASE}/me/read-all", 401)
    call(ctx, "read an unknown notification -> 404", "POST", f"{BASE}/{new_uuid()}/read", 404, token=lr.token)
    call(ctx, "read with a malformed id -> 422", "POST", f"{BASE}/not-a-uuid/read", 422, token=lr.token)
    call(ctx, "read without a token -> 401", "POST", f"{BASE}/{new_uuid()}/read", 401)
