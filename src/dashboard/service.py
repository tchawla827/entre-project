"""Thin, validated bridge to the version-1 integration service."""
from __future__ import annotations

import json
from pathlib import Path

from src.digital_twin.routes import ROOT, load_config
from src.integration import execute
from src.integration.schemas import IntegrationRequest


def options(route: str) -> dict:
    if route not in {"air", "sea"}:
        raise ValueError("Choose air or sea")
    config = load_config(ROOT / "configs/digital_twin" / ("experiment.yaml" if route == "air" else "sea_route.yaml"))
    return {"scenarios": list(config["scenarios"]), "species": config["species_options"], "route_id": config["route_id"]}


def make_request(route="air", scenario="baseline", mode="synthetic", reference=2.0,
                 channel="air", seed=2404, step=15, species="Mackerel") -> dict:
    if channel not in {"air", "estimated_product"}:
        raise ValueError("Unsupported temperature channel")
    if scenario not in options(route)["scenarios"]:
        raise ValueError("Scenario is unavailable for the selected route")
    request = {"schema_version": 1, "target": "thermal_exposure", "route": route,
               "scenario": scenario, "mode": mode, "species": species,
               "references_c": [float(reference)], "step_minutes": int(step), "seed": int(seed)}
    IntegrationRequest.from_dict(request)
    return request


def request_key(request: dict, channel: str) -> str:
    return json.dumps({"request": request, "channel": channel}, sort_keys=True)


def run_pair(request: dict) -> tuple[dict, dict]:
    selected = execute(request, include_trace=True)
    base_request = {**request, "scenario": "baseline"}
    baseline = selected if request["scenario"] == "baseline" else execute(base_request, include_trace=False)
    for result in (selected, baseline):
        if result["schema_version"] != 1 or result["status"] != "SIMULATED_EXPOSURE_ONLY":
            raise ValueError("Unexpected integration response schema/status")
        if result["prediction"] is not None or result["capabilities"]["spoilage_probability"]["status"] != "NOT_CALIBRATED":
            raise ValueError("Biological prediction contract changed; review before display")
    if not selected["trace"]:
        raise ValueError("Integration service returned an empty trace")
    return selected, baseline


def metrics(result: dict, channel: str, reference: float) -> dict:
    return result["thermal_exposure"]["route"][channel]["references"][str(float(reference))]


def channel_summary(result: dict, channel: str, reference: float) -> dict:
    route = result["thermal_exposure"]["route"]
    r = metrics(result, channel, reference)
    c = route[channel]
    return {"run_id": result["run_id"], "route_id": result["route_id"],
            "scenario": route["scenario"], "channel": channel, "reference_c": float(reference),
            "duration_h": c["duration_h"], "peak_c": c["peak_c"],
            "hours_above": r["hours_above"], "degree_hours": r["degree_hours"],
            "degree_hours_per_route_hour": r["degree_hours"] / c["duration_h"] if c["duration_h"] else None,
            "status": result["status"], "prediction_status": route["spoilage_probability_status"]}


def stage_rows(result: dict, channel: str, reference: float) -> list[dict]:
    rows = []
    for stage in result["thermal_exposure"]["stages"]:
        m = stage[channel]["references"][str(float(reference))]
        rows.append({"stage_id": stage["stage_id"], "stage": stage["name"],
                     "start_utc": stage["start_utc"], "end_utc": stage["end_utc"],
                     "duration_h": stage["duration_h"], "setpoint_c": stage["setpoint_c"],
                     "degree_hours": m["degree_hours"], "hours_above": m["hours_above"],
                     "fraction_of_route_degree_hours": m["fraction_of_route_degree_hours"]})
    return rows


def event_rows(result: dict) -> list[dict]:
    return [{"stage_id": e["stage_id"], "kind": e["kind"], "start_utc": e["start_utc"],
             "end_utc": e["end_utc"], "duration_h": e["duration_h"],
             "time_to_recovery_h": e["time_to_recovery_h"],
             "recovery_censored_at_stage_end": e["recovery_censored_at_stage_end"]}
            for e in result["thermal_exposure"]["events"]]
