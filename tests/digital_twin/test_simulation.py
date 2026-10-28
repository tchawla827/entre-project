from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from src.digital_twin.experiments import dh, exact_shapley_combined, run_scenarios
from src.digital_twin.exposure import linear_exceedance, summarize
from src.digital_twin.phase2_adapter import request_quality_trajectory, request_spoilage_probability
from src.digital_twin.routes import load_config, make_route
from src.digital_twin.schemas import TemperatureSample, TwinInputError
from src.digital_twin.simulation import result_tables, simulate
from src.digital_twin.temperature import ProxyReplay
from src.models.inference import UnsupportedCalibrationError


def test_degree_hours_integrates_crossing_and_zero_interval():
    assert linear_exceedance(0, 4, 2, 2) == (1, 1)
    assert linear_exceedance(4, 0, 2, 2) == (1, 1)
    assert linear_exceedance(3, 3, 0, 2) == (0, 0)


def test_baseline_duration_continuity_and_decomposition():
    r = simulate(load_config())
    assert len(r.stage_metrics) == 7
    assert r.route_metrics["air"]["duration_h"] == 47
    assert all(a.end_utc == b.start_utc for a, b in zip(r.samples, r.samples[1:]))
    assert all(s.start_utc.utcoffset() == timedelta(0) for s in r.samples)
    for ref in [2.0, 4.0]:
        assert abs(dh(r, ref)-sum(s["air"]["references"][str(ref)]["degree_hours"]
                                 for s in r.stage_metrics)) < 1e-9
    assert r.route_metrics["spoilage_probability_status"] == "NOT_CALIBRATED"


def test_disruptions_increase_exposure_and_duration_is_reported():
    c = load_config()
    results, table, stages = run_scenarios(c)
    baseline = dh(results["baseline"])
    assert dh(results["road_failure"]) > baseline
    assert dh(results["combined"]) > dh(results["road_failure"])
    assert results["processing_delay"].route_metrics["air"]["duration_h"] == 50
    assert set(stages.scenario) == set(c["scenarios"])


def test_raising_all_stage_setpoints_cannot_lower_exposure():
    c = load_config()
    warm = deepcopy(c)
    for s in warm["stages"]:
        s["setpoint_c"] += 1
    assert dh(simulate(warm)) >= dh(simulate(c))


def test_deterministic_replay_and_timestep_refinement():
    c = load_config()
    a, b = simulate(c, "road_failure", seed=8), simulate(c, "road_failure", seed=8)
    assert a.run.run_id == b.run.run_id
    assert result_tables(a) == result_tables(b)
    v15, v5 = dh(simulate(c, step_minutes=15)), dh(simulate(c, step_minutes=5))
    assert abs(v15-v5)/v5 < .01


def test_run_id_changes_with_resolved_stage_or_lag_settings():
    c = load_config()
    original = simulate(c)
    changed = deepcopy(c)
    changed["stages"][2]["setpoint_c"] += .2
    assert simulate(changed).run.run_id != original.run.run_id
    assert simulate(c, perturb={"product_tau_h": 3}).run.run_id != original.run.run_id


def test_exact_three_player_shapley_sums_to_combined_effect():
    s = exact_shapley_combined(load_config())
    assert abs(sum(s["contribution_degree_hours"].values())-s["combined_delta_degree_hours"]) < 1e-8
    assert all(v > 0 for v in s["contribution_degree_hours"].values())


def test_attributed_nonfish_proxy_replay():
    c = load_config()
    for kind in ["citrus", "coldroom"]:
        p = ProxyReplay(kind, c)
        m = p.manifest()
        assert "not fish" in m["source_channel"] or "generic cold-room" in m["source_channel"]
        result = simulate(c, mode="proxy_" + kind, proxy=p)
        assert result.route_metrics["air"]["duration_h"] == 47
        assert result.samples[0].source_type == "synthetic_air_shaped_by_nonfish_proxy_residual"


def test_unsupported_inference_is_refused():
    with pytest.raises(UnsupportedCalibrationError):
        request_spoilage_probability()
    with pytest.raises(UnsupportedCalibrationError):
        request_quality_trajectory("Mackerel", "fresh", 0, [0, 1], [2, 4], "TVC")


def test_bad_route_event_and_temperature_inputs_fail():
    c = load_config()
    with pytest.raises(TwinInputError):
        make_route(c, "Shrimp")
    with pytest.raises(TwinInputError):
        simulate(c, mode="proxy_citrus")
    bad = deepcopy(c)
    bad["scenarios"]["road_failure"]["changes"][0]["events"][0]["duration_h"] = 10
    with pytest.raises(TwinInputError):
        simulate(bad, "road_failure")
    bad = deepcopy(c)
    bad["start_utc"] = "2026-01-01T00:00:00+05:30"
    with pytest.raises(TwinInputError):
        simulate(bad)


def test_zero_duration_stage_adds_no_exposure():
    c = load_config()
    c["stages"][2]["duration_h"] = 0
    r = simulate(c)
    stage = next(s for s in r.stage_metrics if s["stage_id"] == "cold_storage")
    assert stage["duration_h"] == 0
    assert stage["air"]["references"]["2.0"]["degree_hours"] == 0
    assert r.route_metrics["air"]["duration_h"] == 35


def test_gap_overlap_duplicate_or_missing_sample_is_rejected():
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = TemperatureSample(t, t+timedelta(hours=1), "a", 2, 3, 2, 2.5, "synthetic", None)
    b = TemperatureSample(t+timedelta(hours=2), t+timedelta(hours=3), "a", 3, 4, 2.5, 3, "synthetic", None)
    with pytest.raises(TwinInputError):
        summarize([a, b], [2], "air")
    with pytest.raises(TwinInputError):
        summarize([a, a], [2], "air")
    with pytest.raises(TwinInputError):
        TemperatureSample(t, t, "a", 2, 3, 2, 3, "synthetic", None)
    with pytest.raises(TwinInputError):
        TemperatureSample(t, t+timedelta(hours=1), "a", float("nan"), 3, 2, 3, "synthetic", None)


def test_output_parquet_can_be_loaded_independently():
    path = "results/digital_twin/synthetic/baseline_trace.parquet"
    d = pd.read_parquet(path)
    assert len(d) == 188 and d.schema_version.eq(1).all()
    assert d.start_utc.iloc[0].endswith("+00:00")
    assert d.end_utc.iloc[-1].endswith("+00:00")


def test_sea_route_is_separate_hypothetical_mode():
    from src.digital_twin.routes import ROOT
    sea = load_config(ROOT / "configs/digital_twin/sea_route.yaml")
    baseline = simulate(sea)
    disrupted = simulate(sea, "vessel_excursion")
    assert baseline.route_metrics["air"]["duration_h"] == 375
    assert baseline.run.shipment.route.id != simulate(load_config()).run.shipment.route.id
    assert dh(disrupted) > dh(baseline)
    assert baseline.route_metrics["spoilage_probability_status"] == "NOT_CALIBRATED"
