import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etl"))

import derive_step_techniques as d  # noqa: E402

G = d.PREFIX


def test_generic_keyword_only_confirms_problem_technique():
    text = "Lines AB and CD are parallel, so the angles are equal."
    assert d.derive(text, [G + "PARALLEL_LINE_GEOMETRY"]) == {
        G + "PARALLEL_LINE_GEOMETRY": ("RULE_STEP_TEXT_IN_PROBLEM", 0.85, "parallel")}
    assert d.derive(text, [G + "SIMILAR_TRIANGLES"]) == {}


def test_named_theorem_tags_outside_problem_list():
    out = d.derive("By Menelaus' theorem for triangle ABC and line PQ we get", [])
    assert out == {G + "MENELAUS_THEOREM": ("RULE_STEP_TEXT_NAMED", 0.80, "Menelaus")}


def test_power_formula_signature_is_high_confidence_without_problem_tag():
    out = d.derive("It is clear that AX · XA1 = R2 −OX2.", [])
    assert out[G + "POWER_OF_A_POINT"][:2] == ("RULE_STEP_FORMULA", 0.90)


def test_equal_products_need_power_in_problem_list():
    text = "Hence AC · AG = AE · AB."
    assert d.derive(text, [G + "SIMILAR_TRIANGLES"]) == {}
    assert d.derive(text, [G + "POWER_OF_A_POINT"])[G + "POWER_OF_A_POINT"][:2] == ("RULE_STEP_FORMULA", 0.70)


def test_power_of_a_prime_is_not_power_of_a_point():
    assert G + "POWER_OF_A_POINT" not in d.derive("the power of a prime p divides n", [])


def test_plan_records_outcomes():
    steps = [("s1", "sol", 1, "draw the bisector", [G + "ANGLE_BISECTORS"]),
             ("s2", "sol", 2, "hence x = 2", [G + "ANGLE_BISECTORS"]),
             ("s3", "sol", 3, "hence x = 2", [])]
    rows, runs, stats = d.plan(steps)
    assert [r[:2] for r in rows] == [("s1", G + "ANGLE_BISECTORS")]
    assert [r[2] for r in runs] == ["TAGGED", "NO_MATCH", "NO_PROBLEM_TECHNIQUE"]
    assert stats["RULE_STEP_TEXT_IN_PROBLEM"] == 1


def test_llm_answers_are_restricted_to_closed_list_and_asked_steps():
    answer = {"steps": [{"step_id": "s1", "technique_ids": [G + "INVERSION", "TECH.GEO.MADE_UP"], "reason": "r"},
                        {"step_id": "zz", "technique_ids": [G + "INVERSION"], "reason": "r"}]}
    assert d.validate_llm(answer, {"s1"}, {G + "INVERSION"}) == [("s1", G + "INVERSION", "r")]
    assert d.validate_llm({"bad": 1}, {"s1"}, {G + "INVERSION"}) == []


def test_keyword_map_has_no_duplicates_and_compiles():
    assert len(d.KEYWORDS) == 54
