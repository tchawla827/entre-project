import pandas as pd
import pytest

from src.models.inference import (
    UnsupportedCalibrationError,
    predict_quality_trajectory,
    predict_smoked_catfish_peroxide,
    predict_smoked_catfish_endpoint,
    predict_trout_tvc,
)


def test_trout_split_excludes_candidate_original_fish_overlap():
    s = pd.read_csv("reports/modeling/trout_split_manifest.csv")
    dev = set(s.loc[s.split.eq("development"), "candidate_original_fish_id"])
    test = set(s.loc[s.split.eq("final_test"), "candidate_original_fish_id"])
    assert dev.isdisjoint(test)
    assert s.split.eq("embargo_candidate_fish_overlap").sum() == 1


def test_trout_prediction_is_evidence_scoped():
    p = predict_trout_tvc(3)
    assert 4 < p["expected_tvc_log10_cfu_g"] < 8
    assert p["not_a_spoilage_probability"]
    with pytest.raises(UnsupportedCalibrationError):
        predict_trout_tvc(7)


def test_smoked_curve_rejects_unsupported_conditions():
    a = predict_smoked_catfish_peroxide("Paper", "Refrigerated", 30)
    b = predict_smoked_catfish_peroxide("Paper", "Refrigerated", 60)
    assert a["estimated_peroxide_value_source_units"] <= b["estimated_peroxide_value_source_units"]
    with pytest.raises(UnsupportedCalibrationError):
        predict_smoked_catfish_peroxide("Paper", "20 C", 30)
    ph = predict_smoked_catfish_endpoint("pH", "Paper", "Refrigerated", 60)
    assert 5 < ph["estimated_source_value"] < 8
    with pytest.raises(UnsupportedCalibrationError):
        predict_smoked_catfish_endpoint("freshness_probability", "Paper", "Refrigerated", 60)


def test_variable_temperature_trajectory_refused():
    with pytest.raises(UnsupportedCalibrationError):
        predict_quality_trajectory("Mackerel", "fresh", 0, [0, 1], [4, 8], "TVC")


def test_improvement_search_never_uses_exposed_day_six():
    trials = pd.read_csv("reports/modeling/improvement_trout_cv_predictions.csv")
    assert set(trials.held_out_day) == set(range(6))
    assert not trials.outcome_id.isin(["trout_tvc:F1F17", "trout_tvc:F1F18", "trout_tvc:F4F19"]).any()
    forward = pd.read_csv("reports/modeling/improvement_trout_forward_folds.csv")
    assert set(forward.forecast_day) == {2, 3, 4, 5}
