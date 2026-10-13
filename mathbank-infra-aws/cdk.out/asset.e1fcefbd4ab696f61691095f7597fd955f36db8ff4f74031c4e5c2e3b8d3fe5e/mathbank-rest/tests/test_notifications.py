"""Placeholder test file (requirements/54 §6 — scaffolded, not tested yet).

TODO: once notifications.py has real list_notifications/mark_read logic, add tests:
- recipient_id ownership check on mark_read (one recipient cannot mark another's read)
- record_notification round-trips through the real notification.event table (needs
  migration 043 applied — use a ROUTE_DB_TESTS=1-gated rollback fixture matching this
  repo's existing live-test convention, see tests/test_micro_course_item_sequence.py)
"""
import pytest

pytestmark = pytest.mark.skip(reason="requirements/54 §6 — scaffolded, not tested yet")


def test_notifications_placeholder():
    pass
