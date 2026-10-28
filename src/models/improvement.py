"""Bounded second-round challengers; never uses the exposed trout day-6 check for selection."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import HuberRegressor, LinearRegression, TheilSenRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import SplineTransformer
from sklearn.linear_model import Ridge

from .cli import ROOT, OUT, SEED, prepare


def score(y, p):
    return {"mae": float(mean_absolute_error(y, p)),
            "rmse": float(np.sqrt(mean_squared_error(y, p))),
            "bias": float(np.mean(np.asarray(p) - np.asarray(y)))}


def trout_challengers():
    d = pd.read_parquet(ROOT / "data/curated/trout_microbiology_outcomes.parquet")
    d["candidate_fish"] = d.microbiology_sample_id.str.extract(r"F[1-4]F([0-9]+)")[0]
    held = set(d.loc[d.storage_age_days.eq(6), "candidate_fish"])
    d = d[d.storage_age_days.lt(6) & ~d.candidate_fish.isin(held)].copy()
    assert len(d) == 17
    models = {
        "linear_existing": lambda: LinearRegression(),
        "huber": lambda: HuberRegressor(epsilon=1.35, alpha=0, max_iter=1000),
        "theil_sen": lambda: TheilSenRegressor(random_state=SEED),
        "linear_ridge_1": lambda: Ridge(alpha=1.0),
        "spline_ridge_10": lambda: make_pipeline(SplineTransformer(n_knots=4, degree=2), Ridge(alpha=10.0)),
    }
    rows = []
    for day in sorted(d.storage_age_days.unique()):
        val = d[d.storage_age_days.eq(day)]
        tr = d[d.storage_age_days.ne(day) & ~d.candidate_fish.isin(set(val.candidate_fish))]
        assert set(tr.candidate_fish).isdisjoint(set(val.candidate_fish))
        for name, make in models.items():
            model = make().fit(tr[["storage_age_days"]], tr.tvc_log10_cfu_g)
            pred = model.predict(val[["storage_age_days"]])
            for oid, y, p in zip(val.outcome_id, val.tvc_log10_cfu_g, pred):
                rows.append({"model": name, "held_out_day": int(day), "outcome_id": oid,
                             "observed": float(y), "predicted": float(p)})
        # Monotonic cohort-mean trend, fitted on training days only.
        means = tr.groupby("storage_age_days").tvc_log10_cfu_g.mean()
        iso = IsotonicRegression(increasing=True, out_of_bounds="clip").fit(means.index.to_numpy(), means.to_numpy())
        for oid, y in zip(val.outcome_id, val.tvc_log10_cfu_g):
            rows.append({"model": "isotonic_day_means", "held_out_day": int(day), "outcome_id": oid,
                         "observed": float(y), "predicted": float(iso.predict([day])[0])})
    pred = pd.DataFrame(rows)
    pred.to_csv(OUT / "improvement_trout_cv_predictions.csv", index=False)
    comp = pred.groupby("model").apply(lambda x: pd.Series(score(x.observed, x.predicted)), include_groups=False).sort_values("mae")
    comp.to_csv(OUT / "improvement_trout_comparison.csv")
    day_err = pred.assign(abs_error=lambda x: (x.observed-x.predicted).abs()).groupby(["model", "held_out_day"]).abs_error.mean().unstack(0)
    rng = np.random.default_rng(SEED + 1)
    draw = rng.integers(0, len(day_err), size=(10000, len(day_err)))
    comparisons = {}
    old = day_err["linear_existing"].to_numpy()[draw].mean(axis=1)
    for name in comp.index:
        if name == "linear_existing":
            continue
        new = day_err[name].to_numpy()[draw].mean(axis=1)
        diff = old-new
        comparisons[name] = {"linear_minus_challenger_mae_day_bootstrap_95pct": np.quantile(diff, [.025, .975]).tolist(),
                             "wins_out_of_6_days": int((day_err[name] < day_err["linear_existing"]).sum())}
    (OUT / "improvement_trout_bootstrap.json").write_text(json.dumps(comparisons, indent=2), encoding="utf-8")
    return comp, comparisons


def trout_forward_check():
    d = pd.read_parquet(ROOT / "data/curated/trout_microbiology_outcomes.parquet")
    d["candidate_fish"] = d.microbiology_sample_id.str.extract(r"F[1-4]F([0-9]+)")[0]
    final_ids = set(d.loc[d.storage_age_days.eq(6), "candidate_fish"])
    d = d[d.storage_age_days.lt(6) & ~d.candidate_fish.isin(final_ids)].copy()
    rows = []
    for day in range(2, 6):
        va = d[d.storage_age_days.eq(day)]
        tr = d[d.storage_age_days.lt(day) & ~d.candidate_fish.isin(set(va.candidate_fish))]
        assert set(tr.candidate_fish).isdisjoint(set(va.candidate_fish))
        for name, model in {
            "linear": LinearRegression(), "theil_sen": TheilSenRegressor(random_state=SEED),
            "huber": HuberRegressor(epsilon=1.35, alpha=0, max_iter=1000),
        }.items():
            model.fit(tr[["storage_age_days"]], tr.tvc_log10_cfu_g)
            pred = model.predict(va[["storage_age_days"]])
            rows.append({"model": name, "forecast_day": day, "n_training_assays": len(tr),
                         "n_test_assays": len(va), **score(va.tvc_log10_cfu_g, pred)})
    folds = pd.DataFrame(rows)
    folds.to_csv(OUT / "improvement_trout_forward_folds.csv", index=False)
    paired = folds.pivot(index="forecast_day", columns="model", values="mae")
    advantage = (paired["linear"] - paired["theil_sen"]).to_numpy()
    rng = np.random.default_rng(SEED + 1)
    sample = advantage[rng.integers(0, len(advantage), size=(10000, len(advantage)))].mean(axis=1)
    (OUT / "improvement_trout_forward_bootstrap.json").write_text(json.dumps({
        "linear_minus_theil_sen_mae_95pct": np.quantile(sample, [.025, .975]).tolist(),
        "theil_sen_wins_out_of_four_days": int((advantage > 0).sum()),
        "n_forward_day_groups": len(advantage), "seed": SEED + 1,
    }, indent=2), encoding="utf-8")
    return folds.groupby("model").mae.mean().sort_values()


def catfish_challengers():
    d = pd.read_parquet(ROOT / "data/curated/fish_temperature_quality_experiments.parquet")
    cells = d.groupby(["quality_outcome", "package_type", "storage_condition", "storage_age_days"], as_index=False).outcome_value.mean()
    rows = []
    for (endpoint, pkg, condition), g in cells.groupby(["quality_outcome", "package_type", "storage_condition"]):
        g = g.sort_values("storage_age_days")
        days = g.storage_age_days.to_numpy(dtype=float)
        values = g.outcome_value.to_numpy(dtype=float)
        assert list(days) == [0., 30., 60., 90.]
        observed = values[2]
        anchors_x = days[[0, 1, 3]]
        anchors_y = values[[0, 1, 3]]
        # Candidate fits use no day-60 target. Day zero is a shared empirical baseline.
        candidates = {
            "linear_interpolation_existing": float(np.interp(60, anchors_x, anchors_y)),
            "day30_carry_forward": float(values[1]),
            "pchip_shape_preserving": float(PchipInterpolator(anchors_x, anchors_y)(60)),
            "quadratic_through_anchors": float(np.polyval(np.polyfit(anchors_x, anchors_y, 2), 60)),
        }
        for name, value in candidates.items():
            rows.append({"endpoint": endpoint, "package_type": pkg, "storage_condition": condition,
                         "method": name, "observed_day60": observed, "predicted_day60": value,
                         "absolute_error": abs(value-observed)})
    pred = pd.DataFrame(rows)
    pred.to_csv(OUT / "improvement_catfish_cell_predictions.csv", index=False)
    peroxide = pred[pred.endpoint.eq("Peroxide value")].pivot(
        index=["package_type", "storage_condition"], columns="method", values="absolute_error")
    advantage = (peroxide["linear_interpolation_existing"] - peroxide["pchip_shape_preserving"]).to_numpy()
    rng = np.random.default_rng(SEED + 1)
    sample = advantage[rng.integers(0, len(advantage), size=(10000, len(advantage)))].mean(axis=1)
    (OUT / "improvement_catfish_peroxide_bootstrap.json").write_text(json.dumps({
        "linear_minus_pchip_mae_95pct": np.quantile(sample, [.025, .975]).tolist(),
        "pchip_wins_out_of_six_arms": int((advantage > 0).sum()),
        "n_treatment_arms": len(advantage), "seed": SEED + 1,
    }, indent=2), encoding="utf-8")
    comp = pred.groupby(["endpoint", "method"]).apply(
        lambda x: pd.Series(score(x.observed_day60, x.predicted_day60)), include_groups=False).reset_index()
    comp.to_csv(OUT / "improvement_catfish_comparison.csv", index=False)
    return comp


def catfish_forward_check():
    d = pd.read_parquet(ROOT / "data/curated/fish_temperature_quality_experiments.parquet")
    d = d[d.quality_outcome.eq("Peroxide value")]
    cells = d.groupby(["package_type", "storage_condition", "storage_age_days"], as_index=False).outcome_value.mean()
    rows = []
    for (pkg, condition), g in cells.groupby(["package_type", "storage_condition"]):
        g = g.sort_values("storage_age_days")
        days = g.storage_age_days.to_numpy(dtype=float)
        values = g.outcome_value.to_numpy(dtype=float)
        assert list(days) == [0., 30., 60., 90.]
        observed = values[3]
        forecasts = {
            "day60_carry_forward": values[2],
            "last_interval_linear": values[2] + (values[2]-values[1]),
            "quadratic_first_three": float(np.polyval(np.polyfit(days[:3], values[:3], 2), 90)),
        }
        for name, predicted in forecasts.items():
            rows.append({"package_type": pkg, "storage_condition": condition,
                         "model": name, "observed_day90": observed,
                         "predicted_day90": float(predicted), "abs_error": abs(predicted-observed)})
    result = pd.DataFrame(rows)
    result.to_csv(OUT / "improvement_catfish_forward_day90.csv", index=False)
    return result.groupby("model").abs_error.mean().sort_values()


def main():
    prepare()
    trout, boot = trout_challengers()
    catfish = catfish_challengers()
    print("TROUT\n", trout.to_string())
    print("TROUT PAIRED DAY BOOTSTRAP\n", json.dumps(boot, indent=2))
    print("TROUT FORWARD-ONLY DAY MAE\n", trout_forward_check().to_string())
    print("CATFISH\n", catfish.to_string(index=False))
    print("CATFISH PEROXIDE DAY-90 FORWARD MAE\n", catfish_forward_check().to_string())


if __name__ == "__main__":
    main()
