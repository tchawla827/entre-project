from copy import deepcopy

import pandas as pd
import pytest

from src.digital_twin.experiments import exact_shapley_combined
from src.digital_twin.routes import ROOT, load_config
from src.digital_twin.schemas import TwinInputError
from src.integration.api import execute
from src.integration.schemas import IntegrationInputError, IntegrationRequest
from src.models.inference import UnsupportedCalibrationError


def test_end_to_end_baseline_and_disruption_are_deterministic():
    request = {"target": "thermal_exposure", "scenario": "baseline"}
    a, b = execute(request), execute(request)
    assert a["run_id"] == b["run_id"] and a["trace"] == b["trace"]
    road = execute({**request, "scenario": "road_failure"})
    key = "2.0"
    assert road["thermal_exposure"]["route"]["air"]["references"][key]["degree_hours"] > a["thermal_exposure"]["route"]["air"]["references"][key]["degree_hours"]
    assert a["prediction"] is None and a["source_class"] == "fully_synthetic"
    assert all("synthetic" in row["source_type"] for row in a["trace"])


def test_product_channel_is_explicitly_assumed_and_no_species_physics():
    a = execute({"species": "Mackerel"}, include_trace=False)
    b = execute({"species": "Tuna"}, include_trace=False)
    assert a["thermal_exposure"]["route"]["air"] == b["thermal_exposure"]["route"]["air"]
    assert "estimated_product" in a["thermal_exposure"]["route"]
    assert "measured_fish_core" not in a["thermal_exposure"]["route"]
    assert a["thermal_exposure"]["route"]["spoilage_probability_status"] == "NOT_CALIBRATED"


def test_refusal_and_scoped_models():
    for target in ["fresh_fish_quality_trajectory", "spoilage_probability"]:
        with pytest.raises(UnsupportedCalibrationError):
            execute({"target": target})
    trout = execute({"target": "trout_tvc_within_domain", "species": "Rainbow trout",
                     "product_state": "trout_fillet_nominal_4c", "storage_age_days": 3})
    assert trout["status"] == "LIMITED_WITHIN_STUDY" and trout["thermal_exposure"] is None
    with pytest.raises(UnsupportedCalibrationError):
        execute({"target": "trout_tvc_within_domain", "species": "Rainbow trout",
                 "product_state": "trout_fillet_nominal_4c", "storage_age_days": 7})
    smoked = execute({"target": "smoked_catfish_endpoint_within_domain", "species": "Smoked catfish",
                      "product_state": "smoked_catfish", "endpoint": "pH", "package_type": "Paper",
                      "storage_condition": "Refrigerated", "storage_age_days": 30})
    assert smoked["prediction"]["not_a_spoilage_probability"]
    with pytest.raises(UnsupportedCalibrationError):
        execute({"target": "smoked_catfish_endpoint_within_domain", "species": "Smoked catfish",
                 "product_state": "smoked_catfish", "endpoint": "freshness_probability",
                 "package_type": "Paper", "storage_condition": "Refrigerated", "storage_age_days": 30})


def test_invalid_contracts_fail():
    for bad in [{"temperature_unit": "F"}, {"route": "unknown"}, {"step_minutes": 0},
                {"start_utc": "2026-01-01T00:00:00"}, {"start_utc": "2026-01-01T05:30:00+05:30"},
                {"product_state": "frozen"}, {"schema_version": 2}, {"future_field": 1},
                {"references_c": [2, 2]}]:
        with pytest.raises(IntegrationInputError):
            execute(bad)
    with pytest.raises(IntegrationInputError):
        execute({"route": "sea", "scenario": "flight_excursion"})
    with pytest.raises(TwinInputError):
        execute({"stage_overrides": {"road": {"duration_h": -2}}})


def test_overlapping_events_and_zero_reference_shares():
    c = load_config()
    c["scenarios"]["road_failure"]["changes"][0]["events"] += [
        {"kind": "door_open", "start_h": 2, "duration_h": 1}]
    from src.digital_twin.simulation import simulate
    with pytest.raises(TwinInputError):
        simulate(c, "road_failure")
    r = execute({"references_c": [50.0]})
    assert r["thermal_exposure"]["route"]["air"]["references"]["50.0"]["degree_hours"] == 0
    assert all(s["air"]["references"]["50.0"]["fraction_of_route_degree_hours"] is None
               for s in r["thermal_exposure"]["stages"])


def test_proxy_provenance_and_phase3_regression():
    for mode in ["proxy_citrus", "proxy_coldroom"]:
        r = execute({"mode": mode}, include_trace=False)
        assert r["source_class"] == "nonfish_proxy_shaped_synthetic"
        assert r["source_provenance"]["source_channel"]
    r = execute({}, include_trace=False)
    assert abs(r["thermal_exposure"]["route"]["air"]["references"]["2.0"]["degree_hours"] - 15.045518284998254) < 1e-6


def test_saved_artifacts_round_trip_and_attribution():
    root = ROOT / "results/integration"
    table = pd.read_parquet(root / "scenario_comparison.parquet")
    stages = pd.read_parquet(root / "stage_contributions.parquet")
    assert len(table) == 192 and len(stages) == 1344
    assert len(pd.read_parquet(root / "physical_stage_rankings.parquet")) == 192
    assert len(pd.read_parquet(root / "stage_rank_draws.parquet")) == 1200
    baseline = pd.read_parquet(root / "traces/air/synthetic/baseline.parquet")
    assert len(baseline) == 188 and baseline.schema_version.eq(1).all()
    s = exact_shapley_combined(load_config())
    assert abs(sum(s["contribution_degree_hours"].values()) - s["combined_delta_degree_hours"]) < 1e-8


def test_missing_or_changed_phase2_artifact_is_refused(monkeypatch, tmp_path):
    import src.integration.api as api
    from src.integration.api import ArtifactUnavailableError
    monkeypatch.setattr(api, "ROOT", tmp_path)
    request = {"target": "trout_tvc_within_domain", "species": "Rainbow trout",
               "product_state": "trout_fillet_nominal_4c", "storage_age_days": 3}
    with pytest.raises(ArtifactUnavailableError):
        execute(request)
    artifact = tmp_path / "models/freshness/trout_tvc.joblib"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"changed model")
    manifest = tmp_path / "reports/modeling/environment_and_data.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"artifact_sha256":{"models\\\\freshness\\\\trout_tvc.joblib":"wrong"}}')
    with pytest.raises(ArtifactUnavailableError):
        execute(request)
