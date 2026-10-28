"""Run the Phase 3 thermal-exposure twin; no biological spoilage model is inferred."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import sklearn

from src.models.inference import UnsupportedCalibrationError

from .experiments import dh, exact_shapley_combined, monte_carlo, run_scenarios, event_deltas
from .exposure import linear_exceedance
from .phase2_adapter import capabilities, request_spoilage_probability, request_quality_trajectory
from .plots import make_figures
from .routes import ROOT, DEFAULT_CONFIG, load_config
from .simulation import result_tables, simulate
from .temperature import ProxyReplay


RESULTS = ROOT / "results/digital_twin"
REPORTS = ROOT / "reports/digital_twin"
FIGURES = ROOT / "figures/digital_twin"


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")


def save_runs(mode: str, results: dict, table: pd.DataFrame, stages: pd.DataFrame, proxy=None):
    folder = RESULTS / mode
    folder.mkdir(parents=True, exist_ok=True)
    table.to_csv(folder / "scenario_summary.csv", index=False)
    stages.to_csv(folder / "stage_exposure.csv", index=False)
    for name, result in results.items():
        pd.DataFrame(result_tables(result)).to_parquet(folder / f"{name}_trace.parquet", index=False)
        write_json(folder / f"{name}_metrics.json", {
            "schema_version": 1, "run": {"run_id": result.run.run_id,
                                          "scenario": result.run.shipment.scenario.id,
                                          "scenario_changes": result.run.shipment.scenario.changes,
                                          "route_id": result.run.shipment.route.id,
                                          "temperature_mode": result.run.temperature_mode,
                                          "step_minutes": result.run.step_minutes,
                                          "seed": result.run.seed},
            "route_metrics": result.route_metrics, "stages": result.stage_metrics,
            "events": result.event_metrics,
            "source_provenance": proxy.manifest() if proxy else {
                "type": "synthetic_first_order_assumption", "observed_shipment": False},
            "capabilities": capabilities()})


def manifest(config: dict) -> dict:
    paths = sorted((ROOT / "configs/digital_twin").glob("*.yaml")) + sorted((ROOT / "src/digital_twin").glob("*.py"))
    models = sorted((ROOT / "models").rglob("*"))
    curated = [ROOT / "data/curated" / f"{name}.parquet" for name in [
        "citrus_reefer_temperature_proxy", "coldroom_temperature_proxy", "mpeda_export_statistics"]]
    return {"schema_version": 1, "python": platform.python_version(), "platform": platform.platform(),
            "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__,
            "sklearn": sklearn.__version__, "config_file": str(DEFAULT_CONFIG.relative_to(ROOT)),
            "config_and_code_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            "model_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in models if p.is_file()},
            "curated_source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in curated},
            "source_scope": "scenario/aggregate/nonfish-proxy; no observed Indian fish shipment",
            "thermal_biology_calibration": "NOT_CALIBRATED"}


def data_audit() -> dict:
    citrus = pd.read_parquet(ROOT / "data/curated/citrus_reefer_temperature_proxy.parquet")
    cold = pd.read_parquet(ROOT / "data/curated/coldroom_temperature_proxy.parquet")
    mpeda = pd.read_parquet(ROOT / "data/curated/mpeda_export_statistics.parquet")
    newest = mpeda[mpeda.financial_year.eq("2025-26") & mpeda.measure_code.eq("Q")]
    def q(dimension, label):
        x = newest[newest.dimension_type.eq(dimension) & newest.dimension_source.eq(label)]
        return float(x.value.iloc[0]) if len(x) == 1 else None
    citrus_stream = citrus[citrus.source_file.eq("10C_OP.csv") & citrus.sensor_position_source.eq("P1_mean")]
    sensor_missing = cold.groupby("sensor_id").temperature_c.apply(lambda x:int(x.isna().sum())).to_dict()
    first_sensor = cold[cold.sensor_id.eq("SENSOR02")]
    timestamp = pd.to_datetime(first_sensor.local_timestamp)
    return {"mpeda_fy": "2025-26", "mpeda_quantity_unit": "metric_tonnes",
            "chilled_items_all_markets_q": q("item", "CHILLED ITEMS"),
            "eu_all_items_q": q("market", "EUROPEAN UNION"),
            "cochin_air_cargo_all_items_q": q("port", "COCHIN AIR CARGO ACC"),
            "cochin_sez_all_items_q": q("port", "COCHIN SPECIAL ECONOMIC ZONE - SEZ CARGO"),
            "mpeda_join_warning": "separate item, market and port marginals; no product x destination x port shipment",
            "citrus_rows": len(citrus), "citrus_stream_count": int(citrus.groupby(["source_file", "sensor_position_source"]).ngroups),
            "selected_citrus_stream_rows": len(citrus_stream),
            "selected_citrus_interval_h": float(citrus_stream.elapsed_hours.diff().dropna().median()),
            "citrus_duplicate_stream_time": int(citrus.duplicated(["source_file", "sensor_position_source", "elapsed_hours"]).sum()),
            "citrus_missing_temperature": int(citrus.temperature_c.isna().sum()),
            "citrus_source_channel": "source package-position; air/product interpretation unverified",
            "coldroom_rows": len(cold), "coldroom_sensor_count": int(cold.sensor_id.nunique()),
            "coldroom_source_interval_s_sensor02": float(timestamp.diff().dt.total_seconds().median()),
            "coldroom_missing_temperature": int(cold.temperature_c.isna().sum()),
            "coldroom_missing_by_sensor": sensor_missing,
            "coldroom_sensor02_above_30c_rows": int((first_sensor.temperature_c > 30).sum()),
            "coldroom_timezone": "source-local unknown; only relative replay used",
            "proxy_status": "nonfish thermal-shape input only; not fish core, Indian shipment or biological validation"}


def sensitivity(config: dict):
    profiles = {
        "nominal": {
            "road_failure": config["scenarios"]["road_failure"]["changes"],
            "airport_delay_door": config["scenarios"]["airport_delay_door"]["changes"],
            "flight_excursion": config["scenarios"]["flight_excursion"]["changes"]},
        "brief_road_failure": {
            "road_failure": [{"stage": "road", "events": [{"kind": "refrigeration_off", "start_h": 1, "duration_h": .5}]}],
            "airport_delay_door": config["scenarios"]["airport_delay_door"]["changes"],
            "flight_excursion": config["scenarios"]["flight_excursion"]["changes"]},
        "strong_flight_excursion": {
            "road_failure": config["scenarios"]["road_failure"]["changes"],
            "airport_delay_door": config["scenarios"]["airport_delay_door"]["changes"],
            "flight_excursion": [{"stage": "flight", "events": [{"kind": "setpoint_offset", "start_h": 2,
                                                                      "duration_h": 8, "delta_c": 8}]}]},
    }
    baseline = simulate(config)
    rows = []
    for profile, interventions in profiles.items():
        for name, changes in interventions.items():
            result = simulate(config, f"sensitivity_{profile}_{name}", custom_changes=changes)
            for ref in config["air_reference_c"]:
                rows.append({"profile": profile, "intervention": name, "reference_c": ref,
                             "delta_degree_hours": dh(result, ref)-dh(baseline, ref),
                             "event_magnitude_status": "hypothetical_changed_assumption"})
    df = pd.DataFrame(rows)
    rank = df.loc[df.groupby(["profile", "reference_c"]).delta_degree_hours.idxmax(),
                  ["profile", "reference_c", "intervention", "delta_degree_hours"]]
    return df, rank


def verification(config: dict) -> dict:
    a, b = simulate(config), simulate(config)
    assert a.run.run_id == b.run.run_id and result_tables(a) == result_tables(b)
    assert a.route_metrics["air"]["duration_h"] == 47
    for ref in config["air_reference_c"]:
        total = dh(a, ref)
        subtotal = sum(s["air"]["references"][str(float(ref))]["degree_hours"] for s in a.stage_metrics)
        assert abs(total-subtotal) < 1e-8
    assert linear_exceedance(10, 10, 0, 2) == (0, 0)
    shifted = copy.deepcopy(config)
    for s in shifted["stages"]:
        s["setpoint_c"] += 1
    assert dh(simulate(shifted)) >= dh(a) - 1e-9
    coarser = dh(simulate(config, step_minutes=30))
    finer = dh(simulate(config, step_minutes=5))
    convergence_relative = abs(dh(a)-finer)/max(finer, 1e-9)
    assert convergence_relative < .01
    try:
        request_spoilage_probability()
    except UnsupportedCalibrationError:
        blocked = True
    else:
        blocked = False
    assert blocked
    try:
        request_quality_trajectory("Mackerel", "fresh", 0, [0, 1], [2, 4], "TVC")
    except UnsupportedCalibrationError:
        blocked_quality = True
    else:
        blocked_quality = False
    assert blocked_quality
    return {"deterministic_replay": True, "stage_decomposition_exact": True,
            "warming_monotonic_air_exposure": True, "zero_duration_no_exposure": True,
            "15min_vs_5min_relative_difference": convergence_relative,
            "30min_degree_hours": coarser, "15min_degree_hours": dh(a),
            "5min_degree_hours": finer,
            "spoilage_probability_refused": blocked, "quality_trajectory_refused": blocked_quality}


def analyze(config: dict):
    REPORTS.mkdir(parents=True, exist_ok=True)
    all_modes = {}
    for mode in ["synthetic", "proxy_citrus", "proxy_coldroom"]:
        proxy = None if mode == "synthetic" else ProxyReplay(mode.split("_")[1], config)
        results, table, stages = run_scenarios(config, mode, proxy)
        save_runs(mode, results, table, stages, proxy)
        event_deltas(results, config["air_reference_c"]).to_csv(
            RESULTS / mode / "event_window_deltas.csv", index=False)
        all_modes[mode] = (results, table, stages, proxy)
    shapley = exact_shapley_combined(config)
    write_json(REPORTS / "exact_shapley.json", shapley)
    draws, rank_draws, quantiles, frequencies = monte_carlo(config)
    draws.to_parquet(RESULTS / "assumption_draws.parquet", index=False)
    rank_draws.to_csv(REPORTS / "ranking_draws.csv", index=False)
    quantiles.to_csv(REPORTS / "monte_carlo_quantiles.csv", index=False)
    frequencies.to_csv(REPORTS / "ranking_stability.csv", index=False)
    convergence_rows = []
    for n in [25, 50, 100, 150, 200]:
        if n > int(config["monte_carlo"]["draws"]):
            continue
        part = draws[(draws.draw < n) & draws.scenario.eq("combined")]
        for ref in config["air_reference_c"]:
            ranks = rank_draws[(rank_draws.draw < n) & rank_draws.reference_c.eq(ref)]
            metric = "delta_degree_hours_above_2c" if ref == 2.0 else "delta_degree_hours_above_4c"
            convergence_rows.append({"draws": n, "reference_c": ref,
                                     "combined_delta_median_degree_hours": float(part[metric].median()),
                                     "road_dominant_fraction": float(ranks.dominant_intervention.eq("road_failure").mean())})
    pd.DataFrame(convergence_rows).to_csv(REPORTS / "monte_carlo_convergence.csv", index=False)
    combined = draws[draws.scenario.eq("combined")]
    names = ["duration_multiplier", "setpoint_offset_c", "ambient_offset_c", "air_tau_h",
             "product_tau_h", "event_duration_multiplier"]
    association = pd.DataFrame({"assumption": names,
                                "spearman_with_combined_delta_2c": [
                                    combined[n].corr(combined.delta_degree_hours_above_2c, method="spearman")
                                    for n in names]})
    association.to_csv(REPORTS / "assumption_sensitivity.csv", index=False)
    sens, sens_rank = sensitivity(config)
    sens.to_csv(REPORTS / "event_magnitude_sensitivity.csv", index=False)
    sens_rank.to_csv(REPORTS / "event_magnitude_rankings.csv", index=False)
    verification_result = verification(config)
    write_json(REPORTS / "verification.json", verification_result)
    write_json(REPORTS / "reproducibility_manifest.json", manifest(config))
    make_figures(*all_modes["synthetic"][:3], quantiles, frequencies, FIGURES, association,
                 {mode: value[0]["baseline"] for mode, value in all_modes.items()})
    write_json(REPORTS / "proxy_replay_manifests.json", {
        mode: value[3].manifest() for mode, value in all_modes.items() if value[3] is not None})
    write_json(REPORTS / "data_audit.json", data_audit())
    return all_modes, shapley, quantiles, frequencies, sens_rank, verification_result


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sim = sub.add_parser("simulate")
    sim.add_argument("--scenario", default="baseline")
    sim.add_argument("--all", action="store_true")
    sim.add_argument("--mode", choices=["synthetic", "proxy_citrus", "proxy_coldroom"], default="synthetic")
    sim.add_argument("--species", default="Mackerel")
    sim.add_argument("--step-minutes", type=int, default=None)
    sim.add_argument("--route", choices=["air", "sea"], default="air")
    ana = sub.add_parser("analyze")
    ana.add_argument("--all", action="store_true")
    val = sub.add_parser("validate")
    val.add_argument("--all", action="store_true")
    args = parser.parse_args()
    config = load_config(ROOT / "configs/digital_twin/sea_route.yaml") if args.command == "simulate" and args.route == "sea" else load_config()
    if args.command == "simulate":
        proxy = None if args.mode == "synthetic" else ProxyReplay(args.mode.split("_")[1], config)
        if args.all:
            results, table, stages = run_scenarios(config, args.mode, proxy, args.species,
                                                    args.step_minutes)
            save_runs(("sea_" if args.route == "sea" else "") + args.mode,
                      results, table, stages, proxy)
            print(table.to_string(index=False))
        else:
            result = simulate(config, args.scenario, args.species, args.mode, proxy, args.step_minutes)
            table = pd.DataFrame([{"scenario": args.scenario, "run_id": result.run.run_id,
                                   "air_degree_hours_above_2c": dh(result),
                                   "duration_h": result.route_metrics["air"]["duration_h"]}])
            # Single-run output has the same detailed metrics/trace schema as a full run.
            folder = RESULTS / (("sea_" if args.route == "sea" else "") + args.mode)
            folder.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(result_tables(result)).to_parquet(folder / f"{args.scenario}_trace.parquet", index=False)
            write_json(folder / f"{args.scenario}_metrics.json", {
                "schema_version": 1,
                "run": {"run_id": result.run.run_id, "scenario": args.scenario,
                        "scenario_changes": result.run.shipment.scenario.changes,
                        "route_id": result.run.shipment.route.id,
                        "temperature_mode": result.run.temperature_mode,
                        "step_minutes": result.run.step_minutes, "seed": result.run.seed},
                "route_metrics": result.route_metrics,
                "scenario_changes": result.run.shipment.scenario.changes,
                "stages": result.stage_metrics, "events": result.event_metrics,
                "source_provenance": proxy.manifest() if proxy else {"type": "synthetic_first_order_assumption"},
                "capabilities": capabilities()})
            print(table.to_string(index=False))
    elif args.command == "analyze":
        modes, shapley, quantiles, frequency, sensitivity_rank, check = analyze(config)
        for mode, (_, table, _, _) in modes.items():
            print(mode, "baseline", round(float(table.loc[table.scenario.eq("baseline"), "air_degree_hours_above_2p0c"].iloc[0]), 3),
                  "combined", round(float(table.loc[table.scenario.eq("combined"), "air_degree_hours_above_2p0c"].iloc[0]), 3))
        print("SHAPLEY", json.dumps(shapley["contribution_degree_hours"]))
        print("MONTE_CARLO", quantiles[["scenario", "delta_2c_median", "delta_2c_q05", "delta_2c_q95"]].to_string(index=False))
        print("SENSITIVITY", sensitivity_rank.to_string(index=False))
        print("VERIFIED", json.dumps(check))
    else:
        check = verification(config)
        REPORTS.mkdir(parents=True, exist_ok=True)
        write_json(REPORTS / "verification.json", check)
        print(json.dumps(check, indent=2))


if __name__ == "__main__":
    main()
