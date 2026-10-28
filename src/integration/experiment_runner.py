"""Executed Phase 4 experiment suite over the Phase 3 simulator and service contract."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.digital_twin.experiments import exact_shapley_combined, monte_carlo
from src.digital_twin.routes import ROOT, load_config
from src.digital_twin.simulation import simulate

from .api import execute


OUT = ROOT / "results/integration"
REPORT = ROOT / "reports/integration"
FIGURES = ROOT / "figures/integration"
CONFIG = ROOT / "configs/integration/experiments.yaml"


def protocol() -> dict:
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("unsupported experiment protocol")
    return data


def _metric_row(response: dict, route: str, mode: str, scenario: str, ref: float, channel: str,
                baseline: dict | None) -> dict:
    obj = response["thermal_exposure"]["route"][channel]
    metric = obj["references"][str(float(ref))]
    base = (baseline["thermal_exposure"]["route"][channel]["references"][str(float(ref))]
            if baseline is not None else metric)
    exposure, base_exposure = metric["degree_hours"], base["degree_hours"]
    duration = obj["duration_h"]
    return {"schema_version": 1, "route": route, "route_id": response["route_id"],
            "scenario": scenario, "mode": mode, "channel": channel, "reference_c": float(ref),
            "run_id": response["run_id"], "source_class": response["source_class"],
            "duration_h": duration, "peak_c": obj["peak_c"], "mean_c": obj["mean_c"],
            "hours_above": metric["hours_above"], "percent_time_above": metric["percent_time_above"],
            "max_continuous_excursion_h": metric["max_continuous_excursion_h"],
            "degree_hours": exposure, "degree_hours_per_route_hour": exposure/duration if duration else None,
            "delta_degree_hours": exposure-base_exposure,
            "relative_delta_fraction": ((exposure-base_exposure)/base_exposure
                                        if base_exposure > 0 else None),
            "baseline_run_id": baseline["run_id"] if baseline else response["run_id"],
            "prediction_status": "NOT_CALIBRATED"}


def run_all() -> dict:
    p = protocol()
    OUT.mkdir(parents=True, exist_ok=True)
    rows, stages, events, run_records = [], [], [], []
    for route in p["routes"]:
        route_config = load_config(ROOT / "configs/digital_twin" /
                                   ("sea_route.yaml" if route == "sea" else "experiment.yaml"))
        for mode in p["modes"]:
            baseline = None
            for scenario in route_config["scenarios"]:
                request = {"schema_version": 1, "target": "thermal_exposure", "route": route,
                           "scenario": scenario, "mode": mode, "species": p["default_species"],
                           "references_c": p["references_c"], "step_minutes": p["step_minutes"],
                           "seed": p["seed"]}
                response = execute(request)
                if scenario == "baseline":
                    baseline = response
                if baseline is None:
                    raise AssertionError("baseline must be first configured scenario")
                trace_path = OUT / "traces" / route / mode / f"{scenario}.parquet"
                trace_path.parent.mkdir(parents=True, exist_ok=True)
                pd.DataFrame(response["trace"]).to_parquet(trace_path, index=False)
                run_records.append({"route": route, "mode": mode, "scenario": scenario,
                                    "run_id": response["run_id"], "trace_path": str(trace_path.relative_to(ROOT)),
                                    "source_class": response["source_class"],
                                    "source_provenance": response["source_provenance"],
                                    "request": request})
                for ref in p["references_c"]:
                    for channel in ("air", "estimated_product"):
                        rows.append(_metric_row(response, route, mode, scenario, ref, channel, baseline))
                        for stage in response["thermal_exposure"]["stages"]:
                            m = stage[channel]["references"][str(float(ref))]
                            stages.append({"schema_version": 1, "route": route, "mode": mode,
                                           "scenario": scenario, "channel": channel, "reference_c": ref,
                                           "run_id": response["run_id"], "stage_id": stage["stage_id"],
                                           "stage_start_utc": stage["start_utc"],
                                           "stage_end_utc": stage["end_utc"],
                                           "stage_duration_h": stage["duration_h"],
                                           "degree_hours": m["degree_hours"], "hours_above": m["hours_above"],
                                           "fraction_of_route_degree_hours": m["fraction_of_route_degree_hours"],
                                           "peak_c": stage[channel]["peak_c"]})
                for event in response["thermal_exposure"]["events"]:
                    events.append({"route": route, "mode": mode, "scenario": scenario,
                                   "run_id": response["run_id"], "stage_id": event["stage_id"],
                                   "event_kind": event["kind"], "start_utc": event["start_utc"],
                                   "end_utc": event["end_utc"], "duration_h": event["duration_h"],
                                   "time_to_recovery_h": event["time_to_recovery_h"],
                                   "recovery_censored_at_stage_end": event["recovery_censored_at_stage_end"]})
    comparison, stage_df = pd.DataFrame(rows), pd.DataFrame(stages)
    comparison.to_parquet(OUT / "scenario_comparison.parquet", index=False)
    stage_df.to_parquet(OUT / "stage_contributions.parquet", index=False)
    physical_ranks = []
    for key, group in stage_df.groupby(["route", "mode", "scenario", "channel", "reference_c"]):
        total = group.degree_hours.sum()
        top = group.loc[group.degree_hours.idxmax()] if total > 0 else None
        physical_ranks.append({"route": key[0], "mode": key[1], "scenario": key[2],
                               "channel": key[3], "reference_c": key[4],
                               "top_stage_id": top.stage_id if top is not None else None,
                               "top_stage_degree_hours": top.degree_hours if top is not None else None,
                               "undefined_zero_route_exposure": bool(total == 0)})
    pd.DataFrame(physical_ranks).to_parquet(OUT / "physical_stage_rankings.parquet", index=False)
    pd.DataFrame(events).to_parquet(OUT / "events.parquet", index=False)
    (OUT / "run_manifest.json").write_text(json.dumps({"schema_version": 1, "runs": run_records}, indent=2),
                                           encoding="utf-8")
    return {"runs": len(run_records), "comparison_rows": len(comparison), "stage_rows": len(stage_df)}


def _standardized(config: dict, route: str, ref: float) -> list[dict]:
    event = protocol()["standardized_event"]
    baseline = simulate(config)
    base = baseline.route_metrics["air"]["references"][str(float(ref))]["degree_hours"]
    rows = []
    for stage in config["stages"]:
        if stage["duration_h"] < event["start_h"]+event["duration_h"]:
            continue
        change = [{"stage": stage["id"], "events": [event]}]
        result = simulate(config, "standardized_" + stage["id"], custom_changes=change)
        value = result.route_metrics["air"]["references"][str(float(ref))]["degree_hours"]
        rows.append({"route": route, "stage_id": stage["id"], "reference_c": ref,
                     "event_kind": event["kind"], "event_delta_c": event["delta_c"],
                     "event_duration_h": event["duration_h"], "run_id": result.run.run_id,
                     "delta_degree_hours": value-base})
    return rows


def analyze_all() -> dict:
    p = protocol()
    OUT.mkdir(parents=True, exist_ok=True)
    attribution, interactions, fair, stress, mc_rows, ranks, convergence, stage_rank_draws = [], [], [], [], [], [], [], []
    for route in p["routes"]:
        config = load_config(ROOT / "configs/digital_twin" /
                             ("sea_route.yaml" if route == "sea" else "experiment.yaml"))
        players = (["road_failure", "airport_delay_door", "flight_excursion"] if route == "air"
                   else ["road_failure", "seaport_delay_door", "vessel_excursion"])
        for ref in p["references_c"]:
            s = exact_shapley_combined(config, ref=ref, players=players)
            for player, value in s["contribution_degree_hours"].items():
                attribution.append({"route": route, "reference_c": ref, "intervention": player,
                                    "shapley_degree_hours": value, "combined_delta_degree_hours": s["combined_delta_degree_hours"],
                                    "algorithm": s["algorithm"], "run_scope": "hypothetical_synthetic_air"})
            baseline = simulate(config)
            single_sum = sum(simulate(config, x).route_metrics["air"]["references"][str(float(ref))]["degree_hours"]
                             - baseline.route_metrics["air"]["references"][str(float(ref))]["degree_hours"]
                             for x in players)
            interactions.append({"route": route, "reference_c": ref, "players": ",".join(players),
                                 "combined_delta_degree_hours": s["combined_delta_degree_hours"],
                                 "sum_single_delta_degree_hours": single_sum,
                                 "interaction_degree_hours": s["combined_delta_degree_hours"]-single_sum})
            fair.extend(_standardized(config, route, ref))
        for label, perturb in p["stress_profiles"].items():
            baseline = simulate(config, perturb=perturb)
            for scenario in config["scenarios"]:
                result = simulate(config, scenario, perturb=perturb)
                for ref in p["references_c"]:
                    key = str(float(ref))
                    v = result.route_metrics["air"]["references"][key]["degree_hours"]
                    b = baseline.route_metrics["air"]["references"][key]["degree_hours"]
                    stress.append({"route": route, "profile": label, "scenario": scenario,
                                   "reference_c": ref, "run_id": result.run.run_id,
                                   "duration_h": result.route_metrics["air"]["duration_h"],
                                   "degree_hours": v, "delta_degree_hours": v-b,
                                   "degree_hours_per_route_hour": v/result.route_metrics["air"]["duration_h"],
                                   **perturb})
        draws, rank_draws, _, _ = monte_carlo(config, draws=p["monte_carlo_draws"][route])
        draws.insert(0, "route", route)
        rank_draws.insert(0, "route", route)
        for _, draw in draws[draws.scenario.eq("combined")].iterrows():
            perturb = {key: float(draw[key]) for key in ["duration_multiplier", "setpoint_offset_c",
                "ambient_offset_c", "air_tau_h", "product_tau_h", "event_duration_multiplier"]}
            result = simulate(config, "combined", perturb=perturb,
                              seed=int(config["monte_carlo"]["seed"])+int(draw["draw"]))
            for ref in p["references_c"]:
                key = str(float(ref))
                for channel in ("air", "estimated_product"):
                    ordered = sorted(result.stage_metrics,
                        key=lambda stage: stage[channel]["references"][key]["degree_hours"], reverse=True)
                    total = result.route_metrics[channel]["references"][key]["degree_hours"]
                    stage_rank_draws.append({"route": route, "draw": int(draw["draw"]),
                        "reference_c": ref, "channel": channel,
                        "top_stage_id": ordered[0]["stage_id"] if total > 0 else None,
                        "top_stage_degree_hours": ordered[0][channel]["references"][key]["degree_hours"] if total > 0 else None,
                        "undefined_zero_route_exposure": total == 0})
        mc_rows.append(draws)
        ranks.append(rank_draws)
        for n in [25, 50, 100, 200]:
            if n > p["monte_carlo_draws"][route]:
                continue
            for ref in p["references_c"]:
                part = draws[(draws.draw < n) & draws.scenario.eq("combined")]
                column = "delta_degree_hours_above_2c" if ref == 2 else "delta_degree_hours_above_4c"
                ranked = rank_draws[(rank_draws.draw < n) & rank_draws.reference_c.eq(ref)]
                convergence.append({"route": route, "draws": n, "reference_c": ref,
                                    "combined_median_delta_degree_hours": part[column].median(),
                                    "road_dominant_fraction": ranked.dominant_intervention.eq("road_failure").mean()})
    pd.DataFrame(attribution).to_parquet(OUT / "intervention_attribution.parquet", index=False)
    pd.DataFrame(interactions).to_parquet(OUT / "interactions.parquet", index=False)
    pd.DataFrame(fair).to_parquet(OUT / "standardized_interventions.parquet", index=False)
    pd.DataFrame(stress).to_parquet(OUT / "stress_profiles.parquet", index=False)
    pd.concat(mc_rows).to_parquet(OUT / "sensitivity_draws.parquet", index=False)
    pd.concat(ranks).to_parquet(OUT / "ranking_draws.parquet", index=False)
    pd.DataFrame(convergence).to_parquet(OUT / "monte_carlo_convergence.parquet", index=False)
    pd.DataFrame(stage_rank_draws).to_parquet(OUT / "stage_rank_draws.parquet", index=False)
    return {"attribution_rows": len(attribution), "draw_rows": sum(len(x) for x in mc_rows)}
