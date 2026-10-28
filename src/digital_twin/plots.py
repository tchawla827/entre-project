from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def make_figures(results, scenarios, stages, quantiles, frequencies, folder: Path,
                 assumption_sensitivity=None, proxy_baselines=None):
    folder.mkdir(parents=True, exist_ok=True)
    base, failure = results["baseline"], results["road_failure"]
    plt.figure(figsize=(11, 4))
    for name, result in [("baseline", base), ("road failure", failure)]:
        times = [(s.start_utc-base.run.shipment.route.start_utc).total_seconds()/3600 for s in result.samples]
        values = [s.air_start_c for s in result.samples]
        times.append((result.samples[-1].end_utc-base.run.shipment.route.start_utc).total_seconds()/3600)
        values.append(result.samples[-1].air_end_c)
        plt.plot(times, values, label=name, linewidth=1.5)
    elapsed = 0
    for s in base.stage_metrics:
        if elapsed:
            plt.axvline(elapsed, color="gray", alpha=.3, linewidth=.8)
        elapsed += s["duration_h"]
    plt.axhline(2, color="black", linestyle="--", linewidth=.8, label="scenario 2 C reference")
    plt.xlabel("Hours from hypothetical route start")
    plt.ylabel("Modeled equipment-air temperature, C")
    plt.legend()
    plt.tight_layout()
    plt.savefig(folder / "baseline_vs_road_failure.png", dpi=180)
    plt.close()

    plt.figure(figsize=(10, 4))
    t = [(s.start_utc-base.run.shipment.route.start_utc).total_seconds()/3600 for s in failure.samples]
    plt.plot(t, [s.air_start_c for s in failure.samples], label="modeled equipment air")
    plt.plot(t, [s.estimated_product_start_c for s in failure.samples],
             label="illustrative lagged product estimate")
    plt.xlabel("Hours from hypothetical route start")
    plt.ylabel("Temperature, C")
    plt.legend()
    plt.tight_layout()
    plt.savefig(folder / "air_vs_assumed_product_lag.png", dpi=180)
    plt.close()

    one = scenarios[~scenarios.scenario.isin(["baseline", "combined"])].sort_values(
        "air_delta_degree_hours_above_2p0c", ascending=False)
    plt.figure(figsize=(8, 4))
    plt.barh(one.scenario, one.air_delta_degree_hours_above_2p0c)
    plt.gca().invert_yaxis()
    plt.xlabel("Additional modeled air degree-hours above 2 C versus baseline")
    plt.tight_layout()
    plt.savefig(folder / "one_stage_intervention_ranking.png", dpi=180)
    plt.close()

    order = scenarios.sort_values("air_hours_above_2p0c", ascending=False)
    plt.figure(figsize=(8, 4))
    plt.barh(order.scenario, order.air_hours_above_2p0c, label="above 2 C")
    plt.barh(order.scenario, order.air_hours_above_4p0c, label="above 4 C")
    plt.gca().invert_yaxis()
    plt.xlabel("Modeled equipment-air hours above scenario reference")
    plt.legend()
    plt.tight_layout()
    plt.savefig(folder / "time_above_references.png", dpi=180)
    plt.close()

    chosen = stages[stages.scenario.isin(["baseline", "combined"])].copy()
    pivot = chosen.pivot(index="scenario", columns="stage_id", values="air_degree_hours_above_2p0c")
    pivot = pivot.reindex(["baseline", "combined"])
    pivot.plot(kind="bar", stacked=True, figsize=(9, 4), width=.55)
    plt.xticks(rotation=0)
    plt.ylabel("Modeled air degree-hours above 2 C")
    plt.legend(title="Physical stage", fontsize=7, bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()
    plt.savefig(folder / "stage_exposure_decomposition.png", dpi=180)
    plt.close()

    q = quantiles[~quantiles.scenario.eq("baseline")].sort_values("delta_2c_median", ascending=False)
    x = np.arange(len(q))
    plt.figure(figsize=(9, 4))
    plt.errorbar(x, q.delta_2c_median,
                 yerr=[q.delta_2c_median-q.delta_2c_q05, q.delta_2c_q95-q.delta_2c_median],
                 fmt="o", capsize=3)
    plt.xticks(x, q.scenario, rotation=30, ha="right")
    plt.ylabel("Additional air degree-hours above 2 C; assumption-draw 5-95%")
    plt.tight_layout()
    plt.savefig(folder / "assumption_uncertainty.png", dpi=180)
    plt.close()

    f = frequencies[frequencies.reference_c.eq(2.0)].sort_values("fraction", ascending=False)
    plt.figure(figsize=(7, 3.5))
    plt.bar(f.dominant_intervention, f.fraction)
    plt.ylim(0, 1)
    plt.xticks(rotation=25, ha="right")
    plt.ylabel("Fraction of assumption draws ranked first")
    plt.tight_layout()
    plt.savefig(folder / "dominant_stage_stability.png", dpi=180)
    plt.close()

    if assumption_sensitivity is not None:
        a = assumption_sensitivity.sort_values("spearman_with_combined_delta_2c", key=abs)
        plt.figure(figsize=(7, 4))
        plt.barh(a.assumption, a.spearman_with_combined_delta_2c)
        plt.xlabel("Spearman association with combined-scenario extra air exposure")
        plt.xlim(-1, 1)
        plt.tight_layout()
        plt.savefig(folder / "assumption_sensitivity_tornado.png", dpi=180)
        plt.close()
    if proxy_baselines:
        plt.figure(figsize=(10, 4))
        for label, result in proxy_baselines.items():
            t = [(s.start_utc-result.run.shipment.route.start_utc).total_seconds()/3600 for s in result.samples]
            plt.plot(t, [s.air_start_c for s in result.samples], label=label, linewidth=1.2)
        plt.xlabel("Hours from hypothetical route start")
        plt.ylabel("Modeled equipment-air temperature, C")
        plt.title("Proxy modes use transformed non-fish residual shapes")
        plt.legend()
        plt.tight_layout()
        plt.savefig(folder / "proxy_shape_replay_comparison.png", dpi=180)
        plt.close()
