"""Placeholder test file — intentionally minimal (requirements/54 §6: "no automated test
suite yet, scaffold first"). Not a `pytest` run as part of CI yet; kept here so the
`tests/` folder exists with the project's eventual test-file naming convention
established, matching mathbank-rest/mathbank-agent's own `tests/test_*.py` pattern.

TODO: once contracts.py is considered final, add real tests here:
- every contract round-trips through `.model_dump()`/`model_validate()`
- Explanation is a required (non-optional) field on Prediction/Recommendation
- CohortAssignment has no permanent-label field (requirements/08 §6 — assert the field
  set directly, so a future accidental addition of e.g. `permanent_label` is caught)
"""
import pytest

pytestmark = pytest.mark.skip(reason="requirements/54 §6 — scaffolded, not tested yet")


def test_contracts_placeholder():
    pass
