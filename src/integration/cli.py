"""Phase 4 run, analyze, and validate commands."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.digital_twin.routes import ROOT
from src.digital_twin.phase2_adapter import capabilities
from src.models.inference import UnsupportedCalibrationError

from .api import execute
from .experiment_runner import OUT, REPORT, FIGURES, analyze_all, protocol, run_all


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest() -> dict:
    files = (sorted((ROOT / "src/integration").glob("*.py")) +
             sorted((ROOT / "src/digital_twin").glob("*.py")) +
             sorted((ROOT / "configs/integration").glob("*.yaml")) +
             sorted((ROOT / "configs/digital_twin").glob("*.yaml")) +
             sorted((ROOT / "models").rglob("*.joblib")) +
             sorted((ROOT / "models").rglob("*.json")) +
             sorted((ROOT / "data/curated").glob("*.parquet")))
    return {"schema_version": 1, "python": platform.python_version(),
            "platform": platform.platform(), "code_config_model_data_sha256": {
                str(f.relative_to(ROOT)).replace("\\", "/"): _hash(f) for f in files},
            "git_commit": None, "git_note": "workspace has no Git repository",
            "biological_calibration": "NOT_CALIBRATED"}


def _figures() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    cmp = pd.read_parquet(OUT / "scenario_comparison.parquet")
    attr = pd.read_parquet(OUT / "intervention_attribution.parquet")
    fair = pd.read_parquet(OUT / "standardized_interventions.parquet")
    mc = pd.read_parquet(OUT / "sensitivity_draws.parquet")
    ranks = pd.read_parquet(OUT / "ranking_draws.parquet")
    for route in ("air", "sea"):
        sub = cmp[(cmp["route"] == route) & (cmp["mode"] == "synthetic") & (cmp.reference_c == 2)]
        fig, ax = plt.subplots(figsize=(11, 5))
        scenarios = list(sub.scenario.drop_duplicates())
        x = np.arange(len(scenarios))
        for offset, channel, label in [(-.19, "air", "simulated air"),
                                       (.19, "estimated_product", "assumed product lag")]:
            group = sub[sub.channel.eq(channel)].set_index("scenario").loc[scenarios]
            ax.bar(x+offset, group.delta_degree_hours, width=.38, label=label, alpha=.8)
        ax.set_xticks(x, scenarios, rotation=35, ha="right")
        ax.legend()
        ax.set_ylabel("Additional degree-hours above 2 °C (°C·h)")
        ax.set_title(f"Hypothetical {route} route: simulated air and assumed product lag")
        fig.tight_layout()
        fig.savefig(FIGURES / f"{route}_scenario_channels.png", dpi=160)
        plt.close(fig)
        sub = cmp[(cmp["route"] == route) & (cmp["mode"] == "synthetic") &
                  (cmp.channel == "air") & (cmp.scenario == "combined")]
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar([str(x) for x in sub.reference_c], sub.degree_hours)
        ax.set_xlabel("Scenario comparison reference (°C)")
        ax.set_ylabel("Simulated air degree-hours (°C·h)")
        ax.set_title(f"Hypothetical {route}: combined disruption")
        fig.tight_layout(); fig.savefig(FIGURES / f"{route}_reference_comparison.png", dpi=160); plt.close(fig)
        a = attr[(attr.route == route) & (attr.reference_c == 2)]
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(a.intervention, a.shapley_degree_hours)
        ax.tick_params(axis="x", rotation=25)
        ax.set_ylabel("Allocated additional air degree-hours (°C·h)")
        ax.set_title(f"Hypothetical {route}: exact intervention Shapley")
        fig.tight_layout(); fig.savefig(FIGURES / f"{route}_shapley.png", dpi=160); plt.close(fig)
    sub = fair[(fair.route == "air") & (fair.reference_c == 2)]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(sub.stage_id, sub.delta_degree_hours)
    ax.tick_params(axis="x", rotation=30)
    ax.set_ylabel("Additional simulated air degree-hours (°C·h)")
    ax.set_title("Hypothetical air route: equal 2 h, +3 °C stage events")
    fig.tight_layout(); fig.savefig(FIGURES / "standardized_stage_events.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for i, route in enumerate(("air", "sea")):
        x = mc[(mc.route == route) & mc.scenario.eq("combined")].delta_degree_hours_above_2c
        axes[i].hist(x, bins=18)
        axes[i].set_xlabel("Added simulated air degree-hours above 2 °C (°C·h)")
        axes[i].set_ylabel("Assumption draws (count)")
        axes[i].set_title(f"Hypothetical {route}; n={len(x)}")
    fig.tight_layout(); fig.savefig(FIGURES / "assumption_draw_distributions.png", dpi=160); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4))
    stability = (ranks[ranks.reference_c.eq(2)].assign(road=lambda d:d.dominant_intervention.eq("road_failure"))
                 .groupby("route").road.mean())
    ax.bar(stability.index, stability.values)
    ax.set_ylim(0, 1); ax.set_ylabel("Fraction of bounded assumption draws")
    ax.set_title("Road event largest configured intervention; simulated air, 2 °C")
    fig.tight_layout(); fig.savefig(FIGURES / "road_rank_stability.png", dpi=160); plt.close(fig)
    stage_ranks = pd.read_parquet(OUT / "stage_rank_draws.parquet")
    selected = stage_ranks[(stage_ranks.reference_c.eq(2)) & stage_ranks.channel.eq("air")]
    frequency = selected.groupby(["route", "top_stage_id"]).size().unstack(fill_value=0)
    frequency = frequency.div(frequency.sum(axis=1), axis=0)
    fig, ax = plt.subplots(figsize=(8, 4))
    frequency.plot(kind="bar", stacked=True, ax=ax)
    ax.set_ylabel("Fraction of bounded assumption draws")
    ax.set_xlabel("Hypothetical route")
    ax.set_title("Physical stage with most combined-case simulated air exposure >2 °C")
    ax.legend(title="Physical stage")
    fig.tight_layout(); fig.savefig(FIGURES / "physical_stage_rank_stability.png", dpi=160); plt.close(fig)


def _validate() -> dict:
    p = protocol()
    cmp = pd.read_parquet(OUT / "scenario_comparison.parquet")
    stage = pd.read_parquet(OUT / "stage_contributions.parquet")
    attr = pd.read_parquet(OUT / "intervention_attribution.parquet")
    runs = json.loads((OUT / "run_manifest.json").read_text(encoding="utf-8"))["runs"]
    assert len(runs) == 48 and len(cmp) == 48*2*2
    assert cmp.degree_hours.ge(0).all() and cmp.degree_hours.notna().all()
    for key, group in stage.groupby(["route", "mode", "scenario", "channel", "reference_c"]):
        row = cmp[(cmp["route"] == key[0]) & (cmp["mode"] == key[1]) & (cmp.scenario == key[2]) &
                  (cmp.channel == key[3]) & (cmp.reference_c == key[4])].iloc[0]
        assert abs(group.degree_hours.sum()-row.degree_hours) < 1e-7
        if row.degree_hours == 0:
            assert group.fraction_of_route_degree_hours.isna().all()
    for _, group in attr.groupby(["route", "reference_c"]):
        assert abs(group.shapley_degree_hours.sum()-group.combined_delta_degree_hours.iloc[0]) < 1e-7
    for item in runs:
        d = pd.read_parquet(ROOT / item["trace_path"])
        assert len(d) > 0 and d.run_id.eq(item["run_id"]).all()
        assert d.end_utc.iloc[-1] and d.start_utc.iloc[0]
        assert d.source_type.str.contains("synthetic").all()
    air = cmp[(cmp["route"] == "air") & (cmp["mode"] == "synthetic") & (cmp.channel == "air") &
              (cmp.reference_c == 2)].set_index("scenario")
    assert abs(air.loc["baseline", "degree_hours"]-15.045518284998254) < 1e-6
    assert abs(air.loc["combined", "degree_hours"]-128.08293713646458) < 1e-6
    try:
        execute({"target": "spoilage_probability"})
    except UnsupportedCalibrationError:
        refused = True
    else:
        refused = False
    assert refused
    return {"schema_version": 1, "passed": True, "run_count": len(runs),
            "comparison_rows": len(cmp), "stage_rows": len(stage),
            "phase3_air_reference_reproduced": True, "stage_conservation": True,
            "shapley_efficiency": True, "all_trace_parquet_loadable": True,
            "spoilage_probability_refused": refused}


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for cmd in ("run", "analyze", "validate"):
        sub.add_parser(cmd).add_argument("--all", action="store_true")
    args = parser.parse_args()
    if not args.all:
        parser.error("--all required")
    REPORT.mkdir(parents=True, exist_ok=True)
    if args.command == "run":
        info = run_all()
        (OUT / "provenance_manifest.json").write_text(json.dumps(_manifest(), indent=2), encoding="utf-8")
        (OUT / "capability_matrix.json").write_text(json.dumps({"schema_version": 1,
            "capabilities": capabilities(), "integrated_targets": {
                "thermal_exposure": "SIMULATED_EXPOSURE_ONLY",
                "trout_tvc_within_domain": "LIMITED_WITHIN_STUDY",
                "smoked_catfish_endpoint_within_domain": "LIMITED_WITHIN_STUDY",
                "fresh_fish_quality_trajectory": "NOT_CALIBRATED",
                "spoilage_probability": "NOT_CALIBRATED"}}, indent=2), encoding="utf-8")
        print(json.dumps(info, indent=2))
    elif args.command == "analyze":
        info = analyze_all()
        _figures()
        print(json.dumps(info, indent=2))
    else:
        check = _validate()
        (REPORT / "verification.json").write_text(json.dumps(check, indent=2), encoding="utf-8")
        print(json.dumps(check, indent=2))


if __name__ == "__main__":
    main()
