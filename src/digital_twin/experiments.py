"""Controlled interventions, exact three-factor Shapley attribution and paired assumption Monte Carlo."""
from __future__ import annotations

import itertools
import json
import math

import numpy as np
import pandas as pd

from .simulation import simulate
from .exposure import linear_exceedance
from .temperature import ProxyReplay


def dh(result, ref=2.0, channel="air") -> float:
    return result.route_metrics[channel]["references"][str(float(ref))]["degree_hours"]


def run_scenarios(config: dict, mode: str = "synthetic", proxy: ProxyReplay | None = None,
                  species: str = "Mackerel", step_minutes: int | None = None,
                  perturb: dict | None = None, seed: int = 0):
    results = {name: simulate(config, name, species, mode, proxy, step_minutes, perturb, seed=seed)
               for name in config["scenarios"]}
    baseline = results["baseline"]
    rows, stages = [], []
    for name, result in results.items():
        duration = result.route_metrics["air"]["duration_h"]
        row = {"scenario": name, "run_id": result.run.run_id, "temperature_mode": mode,
               "duration_h": duration, "duration_delta_h": duration-baseline.route_metrics["air"]["duration_h"],
               "air_peak_c": result.route_metrics["air"]["peak_c"],
               "air_mean_c": result.route_metrics["air"]["mean_c"],
               "estimated_product_peak_c": result.route_metrics["estimated_product"]["peak_c"],
               "spoilage_probability_status": "NOT_CALIBRATED"}
        for ref in config["air_reference_c"]:
            key = str(float(ref)).replace(".", "p")
            value = dh(result, ref)
            row[f"air_degree_hours_above_{key}c"] = value
            row[f"air_delta_degree_hours_above_{key}c"] = value-dh(baseline, ref)
            row[f"air_hours_above_{key}c"] = result.route_metrics["air"]["references"][str(float(ref))]["hours_above"]
            row[f"air_degree_hours_per_route_hour_{key}c"] = value/duration if duration else None
            row[f"estimated_product_degree_hours_above_{key}c"] = dh(result, ref, "estimated_product")
        rows.append(row)
        for s in result.stage_metrics:
            entry = {"scenario": name, "stage_id": s["stage_id"], "duration_h": s["duration_h"],
                     "air_peak_c": s["air"]["peak_c"]}
            baseline_stage = next(b for b in baseline.stage_metrics if b["stage_id"] == s["stage_id"])
            for ref in config["air_reference_c"]:
                key = str(float(ref)).replace(".", "p")
                v = s["air"]["references"][str(float(ref))]
                entry[f"air_degree_hours_above_{key}c"] = v["degree_hours"]
                entry[f"air_delta_degree_hours_above_{key}c"] = v["degree_hours"] - baseline_stage["air"]["references"][str(float(ref))]["degree_hours"]
                entry[f"fraction_route_exposure_above_{key}c"] = v["fraction_of_route_degree_hours"]
            stages.append(entry)
    return results, pd.DataFrame(rows), pd.DataFrame(stages)


def _window_degree_hours(samples, start, end, ref: float, channel="air") -> float:
    """Integrate only the overlap with a time window; interpolate partial edge intervals."""
    total = 0.0
    a_name, b_name = (("air_start_c", "air_end_c") if channel == "air" else
                      ("estimated_product_start_c", "estimated_product_end_c"))
    for s in samples:
        left, right = max(start, s.start_utc), min(end, s.end_utc)
        if right <= left:
            continue
        length = (s.end_utc-s.start_utc).total_seconds()
        p = (left-s.start_utc).total_seconds()/length
        q = (right-s.start_utc).total_seconds()/length
        v0, v1 = getattr(s, a_name), getattr(s, b_name)
        t0, t1 = v0+(v1-v0)*p, v0+(v1-v0)*q
        total += linear_exceedance(t0, t1, (right-left).total_seconds()/3600, ref)[1]
    return total


def event_deltas(results: dict, references_c: list[float]) -> pd.DataFrame:
    """Event-window extra exposure versus the same stage-local window in baseline."""
    base = results["baseline"]
    base_stage = {s["stage_id"]: s for s in base.stage_metrics}
    rows = []
    for scenario, result in results.items():
        if scenario == "baseline":
            continue
        scenario_stage = {s["stage_id"]: s for s in result.stage_metrics}
        for event in result.event_metrics:
            stage_id = event["stage_id"]
            stage_start = pd.Timestamp(scenario_stage[stage_id]["start_utc"])
            baseline_start = pd.Timestamp(base_stage[stage_id]["start_utc"])
            start, end = pd.Timestamp(event["start_utc"]), pd.Timestamp(event["end_utc"])
            baseline_event_start = baseline_start + (start-stage_start)
            baseline_event_end = baseline_start + (end-stage_start)
            row = {"scenario": scenario, "stage_id": stage_id, "event_kind": event["kind"],
                   "event_duration_h": event["duration_h"],
                   "includes_upstream_carryover": scenario == "combined",
                   "time_to_recovery_h": event["time_to_recovery_h"],
                   "recovery_censored_at_stage_end": event["recovery_censored_at_stage_end"]}
            for ref in references_c:
                key = str(float(ref)).replace(".", "p")
                for channel in ["air", "estimated_product"]:
                    actual = _window_degree_hours(result.samples, start, end, float(ref), channel)
                    expected = _window_degree_hours(base.samples, baseline_event_start,
                                                    baseline_event_end, float(ref), channel)
                    row[f"{channel}_event_window_extra_degree_hours_above_{key}c"] = actual-expected
            rows.append(row)
    return pd.DataFrame(rows)


def exact_shapley_combined(config: dict, ref=2.0, species="Mackerel", step_minutes=None,
                           players=None):
    players = players or ["road_failure", "airport_delay_door", "flight_excursion"]
    changes = {p: config["scenarios"][p]["changes"][0] for p in players}
    values = {}
    for count in range(4):
        for subset in itertools.combinations(players, count):
            subset = frozenset(subset)
            chosen = [changes[p] for p in players if p in subset]
            result = simulate(config, "shapley_" + "_".join(sorted(subset)) if subset else "shapley_empty",
                              species=species, step_minutes=step_minutes, custom_changes=chosen)
            values[subset] = dh(result, ref)
    contribution = {}
    n = len(players)
    for player in players:
        amount = 0.0
        others = [p for p in players if p != player]
        for count in range(n):
            for subset_tuple in itertools.combinations(others, count):
                subset = frozenset(subset_tuple)
                weight = math.factorial(count)*math.factorial(n-count-1)/math.factorial(n)
                amount += weight*(values[subset | {player}]-values[subset])
        contribution[player] = amount
    total_delta = values[frozenset(players)] - values[frozenset()]
    assert abs(sum(contribution.values())-total_delta) < 1e-8
    return {"algorithm": "exact_shapley_all_2^3_coalitions", "reference_c": ref,
            "players": players, "baseline_degree_hours": values[frozenset()],
            "combined_degree_hours": values[frozenset(players)],
            "combined_delta_degree_hours": total_delta,
            "contribution_degree_hours": contribution,
            "sum_check": sum(contribution.values()),
            "interpretation": "attribution of simulated intervention effects; not real causal spoilage risk"}


def monte_carlo(config: dict, mode: str = "synthetic", proxy: ProxyReplay | None = None,
                draws: int | None = None, species="Mackerel"):
    mc = config["monte_carlo"]
    n = int(draws or mc["draws"])
    rng = np.random.default_rng(int(mc["seed"]))
    rows = []
    rank_rows = []
    for index in range(n):
        p = {"duration_multiplier": float(rng.uniform(*mc["duration_multiplier"])),
             "setpoint_offset_c": float(rng.uniform(*mc["setpoint_offset_c"])),
             "ambient_offset_c": float(rng.uniform(*mc["ambient_offset_c"])),
             "air_tau_h": float(rng.uniform(*mc["air_tau_h"])),
             "product_tau_h": float(rng.uniform(*mc["product_tau_h"])),
             "event_duration_multiplier": float(rng.uniform(*mc["event_duration_multiplier"]))}
        results, table, _ = run_scenarios(config, mode, proxy, species, perturb=p, seed=int(mc["seed"])+index)
        for ref in config["air_reference_c"]:
            key = str(float(ref)).replace(".", "p")
            delta_col = f"air_delta_degree_hours_above_{key}c"
            candidates = table[~table.scenario.isin(["baseline", "combined"])].copy()
            winner = candidates.loc[candidates[delta_col].idxmax(), "scenario"]
            rank_rows.append({"draw": index, "reference_c": float(ref),
                              "dominant_intervention": winner, "max_delta_degree_hours": float(candidates[delta_col].max())})
        for _, row in table.iterrows():
            rows.append({"draw": index, "scenario": row.scenario, "mode": mode,
                         "duration_h": row.duration_h,
                         "degree_hours_above_2c": row.air_degree_hours_above_2p0c,
                         "delta_degree_hours_above_2c": row.air_delta_degree_hours_above_2p0c,
                         "degree_hours_above_4c": row.air_degree_hours_above_4p0c,
                         "delta_degree_hours_above_4c": row.air_delta_degree_hours_above_4p0c,
                         **p})
    draw_df, rank_df = pd.DataFrame(rows), pd.DataFrame(rank_rows)
    quantiles = draw_df.groupby("scenario").agg(
        n=("draw", "size"),
        delta_2c_q05=("delta_degree_hours_above_2c", lambda x:x.quantile(.05)),
        delta_2c_median=("delta_degree_hours_above_2c", "median"),
        delta_2c_q95=("delta_degree_hours_above_2c", lambda x:x.quantile(.95)),
        delta_4c_q05=("delta_degree_hours_above_4c", lambda x:x.quantile(.05)),
        delta_4c_median=("delta_degree_hours_above_4c", "median"),
        delta_4c_q95=("delta_degree_hours_above_4c", lambda x:x.quantile(.95))).reset_index()
    frequency = rank_df.groupby(["reference_c", "dominant_intervention"]).size().rename("draws").reset_index()
    frequency["fraction"] = frequency.draws/n
    return draw_df, rank_df, quantiles, frequency
