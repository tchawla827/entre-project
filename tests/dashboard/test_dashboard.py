import io
import json
import zipfile
from copy import deepcopy

import pandas as pd
import pytest

from src.dashboard.export import selected_files, zip_bytes
from src.dashboard.loaders import load_json, load_table
from src.dashboard.service import (channel_summary, make_request, metrics, options,
                                   request_key, run_pair, stage_rows)
from src.integration import execute
from src.models.inference import UnsupportedCalibrationError


def test_options_and_request_contract():
    assert "airport_delay_door" in options("air")["scenarios"]
    assert "seaport_delay_door" in options("sea")["scenarios"]
    assert "airport_delay_door" not in options("sea")["scenarios"]
    for route in ("air", "sea"):
        for mode in ("synthetic", "proxy_citrus", "proxy_coldroom"):
            req = make_request(route, "baseline", mode, 2, "air", 2404, 15)
            assert req["schema_version"] == 1 and req["route"] == route and req["mode"] == mode
    for bad in (dict(route="sea", scenario="airport_delay_door"), dict(channel="fish_core"),
                dict(mode="invalid"), dict(reference=float("nan"))):
        with pytest.raises(ValueError):
            make_request(**bad)


def test_api_pair_and_numbers():
    req = make_request("air", "road_failure", "synthetic", 2.0, seed=2404)
    selected, baseline = run_pair(req)
    assert selected["status"] == "SIMULATED_EXPOSURE_ONLY"
    assert selected["prediction"] is None
    assert selected["capabilities"]["spoilage_probability"]["status"] == "NOT_CALIBRATED"
    assert metrics(selected, "air", 2.0)["degree_hours"] == pytest.approx(70.84803997815442)
    assert metrics(baseline, "air", 2.0)["degree_hours"] == pytest.approx(15.045518284998254)
    assert sum(x["degree_hours"] for x in stage_rows(selected, "air", 2.0)) == pytest.approx(
        metrics(selected, "air", 2.0)["degree_hours"])
    assert channel_summary(selected, "air", 2.0)["degree_hours"] != channel_summary(selected, "estimated_product", 2.0)["degree_hours"]
    assert selected["source_class"] == "fully_synthetic"
    assert len(selected["trace"]) > 0
    assert selected["trace"][0]["source_type"] == "synthetic_first_order_air"
    assert run_pair(req)[0]["run_id"] == selected["run_id"]
    assert request_key(req, "air") != request_key({**req, "scenario": "baseline"}, "air")


def test_export_fidelity_and_null_relative():
    result, baseline = run_pair(make_request("air", "road_failure", "synthetic", 2, seed=2404))
    files = selected_files(result, baseline, "estimated_product", 2.0)
    complete = json.loads(files["complete_result.json"])
    assert complete["selection"] == {"channel": "estimated_product", "reference_c": 2.0}
    assert complete["selected_result"]["run_id"] == result["run_id"]
    assert complete["selected_summary"]["degree_hours"] == metrics(result, "estimated_product", 2.0)["degree_hours"]
    trace = pd.read_csv(io.BytesIO(files["trace.csv"]))
    assert set(trace["run_id"]) == {result["run_id"]}
    assert set(trace["selected_channel"]) == {"estimated_product"}
    with zipfile.ZipFile(io.BytesIO(zip_bytes(files))) as archive:
        assert set(files).issubset(archive.namelist())
    zero = deepcopy(baseline)
    zero["thermal_exposure"]["route"]["air"]["references"]["2.0"]["degree_hours"] = 0.0
    assert json.loads(selected_files(result, zero, "air", 2)["complete_result.json"])["selected_summary"]["relative_delta_fraction"] is None


def test_saved_schema_and_scientific_refusal():
    comparison = load_table("scenario_comparison")
    assert len(comparison) == 192 and set(comparison["schema_version"]) == {1}
    assert len(load_table("intervention_attribution")) == 12
    assert load_json("capability_matrix")["capabilities"]["spoilage_probability"]["status"] == "NOT_CALIBRATED"
    with pytest.raises(UnsupportedCalibrationError):
        execute({"target":"spoilage_probability"})


def test_missing_artifact(monkeypatch, tmp_path):
    import src.dashboard.loaders as loaders
    monkeypatch.setattr(loaders, "DATA", tmp_path)
    with pytest.raises(FileNotFoundError, match="artifact missing"):
        loaders.load_table("scenario_comparison")


def test_ui_smoke():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file("app.py", default_timeout=45).run()
    assert not app.exception
    assert "Fish spoilage is not calibrated" in " ".join(x.value for x in app.markdown)
    assert any("15.05" in x.value for x in app.metric)
    app.selectbox(key="scenario_air").set_value("road_failure").run()
    assert not app.exception
    run = next(x for x in app.button if x.label == "Run simulation")
    run.click().run()
    assert not app.exception
    assert any("70.85" in x.value for x in app.metric)
