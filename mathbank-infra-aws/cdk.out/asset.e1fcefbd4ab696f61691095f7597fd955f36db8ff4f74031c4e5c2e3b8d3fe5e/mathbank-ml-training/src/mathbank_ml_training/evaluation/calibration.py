"""Calibration monitoring (requirements/13 §9 "prediction calibration").

A model's predicted probability of 0.7 should correspond to roughly 70% of such
predictions being correct — this module checks that, it does not fix a miscalibrated
model (fixing is Platt scaling / isotonic regression inside the model's own train() step).
"""
from __future__ import annotations


def calibration_curve(predicted_probabilities: list[float], actual_outcomes: list[bool], *,
                        n_bins: int = 10) -> list[dict]:
    """TODO: implement. Return one dict per bin: {bin_range, mean_predicted,
    observed_frequency, count}. Use this to decide whether a model needs
    CalibratedClassifierCV before being registered (requirements/13 §5 approval gate)."""
    raise NotImplementedError("requirements/55 §2 CALIBRATE stage")


def expected_calibration_error(predicted_probabilities: list[float], actual_outcomes: list[bool]) -> float:
    """TODO: implement, standard ECE formula over calibration_curve()'s bins."""
    raise NotImplementedError("requirements/55 §2 CALIBRATE stage — ECE")
