"""Reproducible, evidence-scoped Phase 2 experiments.

Run: python -m src.models.cli all
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
import sklearn
import yaml
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import adjusted_rand_score, mean_absolute_error, mean_squared_error, silhouette_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "modeling"
FIG = ROOT / "figures" / "modeling"
MODELS = ROOT / "models"
CONFIG = yaml.safe_load((ROOT / "configs/models/protocol.yaml").read_text(encoding="utf-8"))
SEED = int(CONFIG["seed"])


def prepare() -> None:
    for p in [OUT, FIG, MODELS / "freshness", MODELS / "thermal", MODELS / "exploration"]:
        p.mkdir(parents=True, exist_ok=True)


def metric(y, pred) -> dict:
    return {"mae": float(mean_absolute_error(y, pred)),
            "rmse": float(np.sqrt(mean_squared_error(y, pred))),
            "bias": float(np.mean(np.asarray(pred) - np.asarray(y)))}


def candidates() -> dict:
    # Day-only: measured TVC fish have no paired gas readings or measured product temperature.
    return {
        "mean": DummyRegressor(strategy="mean"),
        "linear": LinearRegression(),
        "quadratic_ridge_0.1": make_pipeline(PolynomialFeatures(2, include_bias=False), Ridge(alpha=0.1)),
        "quadratic_ridge_1": make_pipeline(PolynomialFeatures(2, include_bias=False), Ridge(alpha=1.0)),
        "quadratic_ridge_10": make_pipeline(PolynomialFeatures(2, include_bias=False), Ridge(alpha=10.0)),
    }


def trout() -> dict:
    d = pd.read_parquet(ROOT / "data/curated/trout_microbiology_outcomes.parquet")
    assert len(d) == 21 and d.microbiology_sample_id.is_unique
    assert d.fish_or_fillet_id_link_to_sensor.isna().all()
    assert d.storage_temperature_protocol_c.eq(4).all()
    d = d.sort_values(["storage_age_days", "microbiology_sample_id"]).reset_index(drop=True)
    # The filename pattern may encode the original fish. Err toward excluding overlap.
    # A first run exposed the day-6 holdout before this overlap was found; the revised
    # holdout is post-hoc and must never be described as an untouched final test.
    d["candidate_original_fish_id"] = d.microbiology_sample_id.str.extract(r"F[1-4]F([0-9]+)")[0]
    assert d.candidate_original_fish_id.notna().all()
    test_day = int(CONFIG["trout"]["final_temporal_day"])
    test_fish = set(d.loc[d.storage_age_days.eq(test_day), "candidate_original_fish_id"])
    d["split"] = np.select(
        [d.storage_age_days.eq(test_day), d.candidate_original_fish_id.isin(test_fish)],
        ["final_test", "embargo_candidate_fish_overlap"], default="development")
    d[["outcome_id", "microbiology_sample_id", "candidate_original_fish_id", "storage_age_days", "split"]].to_csv(
        OUT / "trout_split_manifest.csv", index=False)
    dev = d[d.split.eq("development")]
    test = d[d.split.eq("final_test")]
    rows, predictions = [], []
    for name, model in candidates().items():
        for day in sorted(dev.storage_age_days.unique()):
            va = dev[dev.storage_age_days.eq(day)]
            held_fish = set(va.candidate_original_fish_id)
            tr = dev[dev.storage_age_days.ne(day) & ~dev.candidate_original_fish_id.isin(held_fish)]
            assert set(tr.candidate_original_fish_id).isdisjoint(held_fish)
            model.fit(tr[["storage_age_days"]], tr.tvc_log10_cfu_g)
            yp = model.predict(va[["storage_age_days"]])
            rows.append({"model": name, "held_out_day": int(day), "n_test_fish": len(va), **metric(va.tvc_log10_cfu_g, yp)})
            predictions += [{"model": name, "fold_day": int(day), "outcome_id": oid,
                             "observed": float(y), "predicted": float(p), "split": "development_cv"}
                            for oid, y, p in zip(va.outcome_id, va.tvc_log10_cfu_g, yp)]
    folds = pd.DataFrame(rows)
    folds.to_csv(OUT / "trout_cv_folds.csv", index=False)
    cvp = pd.DataFrame(predictions)
    cvp.to_csv(OUT / "trout_cv_predictions.csv", index=False)
    ranking = cvp.groupby("model").apply(
        lambda x: pd.Series(metric(x.observed, x.predicted)), include_groups=False).sort_values("mae")
    ranking.to_csv(OUT / "trout_model_comparison.csv")
    # Resample the six held-out day groups, not the correlated assays within a day.
    day_errors = folds.pivot(index="held_out_day", columns="model", values="mae")
    rng = np.random.default_rng(SEED)
    draw = rng.integers(0, len(day_errors), size=(10000, len(day_errors)))
    lin_boot = day_errors["linear"].to_numpy()[draw].mean(axis=1)
    mean_boot = day_errors["mean"].to_numpy()[draw].mean(axis=1)
    bootstrap = {
        "linear_cv_mae_95pct_day_bootstrap": np.quantile(lin_boot, [.025, .975]).tolist(),
        "mean_baseline_cv_mae_95pct_day_bootstrap": np.quantile(mean_boot, [.025, .975]).tolist(),
        "baseline_minus_linear_mae_95pct_day_bootstrap": np.quantile(mean_boot-lin_boot, [.025, .975]).tolist(),
        "n_resampled_day_groups": len(day_errors), "n_bootstrap_draws": len(draw),
        "warning": "Single study and six cohorts; percentile intervals are unstable and not deployment uncertainty."
    }
    (OUT / "trout_cv_day_bootstrap.json").write_text(json.dumps(bootstrap, indent=2), encoding="utf-8")
    # Predeclared gate: choose the simplest candidate within 0.05 log units of best CV MAE.
    eligible = ranking[ranking.mae <= ranking.mae.min() + float(CONFIG["trout"]["simplicity_mae_margin_log10"])].index
    priority = ["linear", "mean", "quadratic_ridge_10", "quadratic_ridge_1", "quadratic_ridge_0.1"]
    selected = next(n for n in priority if n in eligible)
    fitted = candidates()[selected]
    assert set(dev.candidate_original_fish_id).isdisjoint(set(test.candidate_original_fish_id))
    fitted.fit(dev[["storage_age_days"]], dev.tvc_log10_cfu_g)
    yp = fitted.predict(test[["storage_age_days"]])
    final = metric(test.tvc_log10_cfu_g, yp)
    baseline = candidates()["mean"].fit(dev[["storage_age_days"]], dev.tvc_log10_cfu_g)
    baseline_metric = metric(test.tvc_log10_cfu_g, baseline.predict(test[["storage_age_days"]]))
    test_pred = test[["outcome_id", "microbiology_sample_id", "storage_age_days", "tvc_log10_cfu_g"]].copy()
    test_pred["predicted"] = yp
    test_pred["error"] = yp - test_pred.tvc_log10_cfu_g
    test_pred.to_csv(OUT / "trout_final_test_predictions.csv", index=False)
    # Six held-out days only: empirical residual range, not a calibrated prediction interval.
    sel_cvp = cvp[cvp.model.eq(selected)]
    residual_quantile = float(np.quantile(np.abs(sel_cvp.observed - sel_cvp.predicted), 0.9))
    coverage = float(np.mean(np.abs(test.tvc_log10_cfu_g.to_numpy() - yp) <= residual_quantile))
    bundle = {"estimator": fitted, "selected": selected, "training_n_fish": len(dev),
              "training_day_groups": 6, "source": "zenodo_23600663_v4",
              "domain": "rainbow trout fillet; nominal storage 4 C; day 0-6",
              "target": "observed individual TVC log10 CFU/g", "seed": SEED}
    joblib.dump(bundle, MODELS / "freshness/trout_tvc.joblib")
    result = {"selected": selected, "cv": ranking.loc[selected].to_dict(),
              "revised_holdout_posthoc": final, "revised_holdout_mean_baseline": baseline_metric,
              "untouched_final_test": "UNAVAILABLE: initial protocol invalidated after first test inspection",
              "n_development_fish": len(dev),
              "n_development_candidate_original_fish": int(dev.candidate_original_fish_id.nunique()),
              "n_development_day_groups": 6, "n_test_fish": len(test), "n_test_day_groups": 1,
              "n_test_candidate_original_fish": int(test.candidate_original_fish_id.nunique()),
              "n_embargoed_assays": int(d.split.eq("embargo_candidate_fish_overlap").sum()),
              "cv_absolute_error_90pct": residual_quantile, "test_empirical_coverage": coverage,
              "group_bootstrap": bootstrap,
              "external_validation": "BLOCKED"}
    (OUT / "trout_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    plt.figure(figsize=(6, 4))
    for day, group in d.groupby("storage_age_days"):
        plt.scatter([day] * len(group), group.tvc_log10_cfu_g, c="black", s=18, alpha=.7)
    x = np.linspace(0, 6, 100)
    plt.plot(x, fitted.predict(pd.DataFrame({"storage_age_days": x})), label=selected)
    plt.axvline(5.5, color="tab:red", linestyle="--", label="post-hoc day-6 check")
    plt.xlabel("Storage age, days at nominal 4 C")
    plt.ylabel("TVC, log10 CFU/g")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG / "trout_tvc.png", dpi=180)
    plt.close()
    return result


def catfish() -> dict:
    d = pd.read_parquet(ROOT / "data/curated/fish_temperature_quality_experiments.parquet")
    # Preserve all seven measured endpoints as separate treatment-specific curves.
    all_curves = {}
    all_diagnostics = []
    for endpoint, endpoint_rows in d.groupby("quality_outcome"):
        all_curves[endpoint] = {}
        ecells = endpoint_rows.groupby(
            ["package_type", "storage_condition", "storage_age_days"], as_index=False
        ).agg(mean=("outcome_value", "mean"), sd=("outcome_value", "std"), n=("outcome_value", "size"))
        for (pkg, condition), g in ecells.groupby(["package_type", "storage_condition"]):
            g = g.sort_values("storage_age_days")
            assert list(g.storage_age_days) == [0, 30, 60, 90] and g.n.eq(2).all()
            key = f"{pkg}|{condition}"
            all_curves[endpoint][key] = {"days": g.storage_age_days.astype(int).tolist(),
                                         "means": g["mean"].astype(float).tolist()}
            predicted = float(np.interp(60, [30, 90], [g.loc[g.storage_age_days.eq(30), "mean"].iloc[0],
                                                       g.loc[g.storage_age_days.eq(90), "mean"].iloc[0]]))
            actual = float(g.loc[g.storage_age_days.eq(60), "mean"].iloc[0])
            carry = float(g.loc[g.storage_age_days.eq(30), "mean"].iloc[0])
            all_diagnostics.append({"endpoint": endpoint, "package_type": pkg,
                                    "storage_condition": condition, "observed_day60_cell_mean": actual,
                                    "interpolated": predicted, "day30_carry_forward": carry})
    diagnostics = pd.DataFrame(all_diagnostics)
    diagnostics.to_csv(OUT / "smoked_catfish_all_endpoint_checks.csv", index=False)
    endpoint_metrics = []
    for endpoint, g in diagnostics.groupby("endpoint"):
        im = metric(g.observed_day60_cell_mean, g.interpolated)
        bm = metric(g.observed_day60_cell_mean, g.day30_carry_forward)
        endpoint_metrics.append({"endpoint": endpoint, "interpolation_mae": im["mae"],
                                 "interpolation_rmse": im["rmse"], "carry_forward_mae": bm["mae"],
                                 "n_held_out_cells": len(g)})
    pd.DataFrame(endpoint_metrics).to_csv(OUT / "smoked_catfish_all_endpoint_metrics.csv", index=False)
    (MODELS / "thermal/smoked_catfish_endpoints.json").write_text(json.dumps({
        "source": "mendeley_tvsw53j89z_v1", "product_state": "smoked",
        "temperature_conditions_c": {"Ambient": [25, 30], "Refrigerated": [4, 5]},
        "warning": "Observed treatment-cell interpolation; not variable-temperature kinetics or independent-run validation.",
        "curves_by_endpoint": all_curves}, indent=2), encoding="utf-8")
    p = d[d.quality_outcome.eq("Peroxide value")].copy()
    assert len(p) == 48 and set(p.product_state) == {"smoked"}
    assert p[p.storage_age_days.eq(0)].is_inferential_postbaseline.eq(False).all()
    # Independent experimental run IDs are absent. These are treatment-cell curves, not validated kinetics.
    cells = p.groupby(["package_type", "storage_condition", "storage_age_days"], as_index=False).agg(
        n=("outcome_value", "size"), mean=("outcome_value", "mean"), sd=("outcome_value", "std"))
    cells.to_csv(OUT / "smoked_catfish_peroxide_cells.csv", index=False)
    curves = {}
    middle_predictions = []
    for (pkg, condition), g in cells.groupby(["package_type", "storage_condition"]):
        g = g.sort_values("storage_age_days")
        assert list(g.storage_age_days) == [0, 30, 60, 90]
        key = f"{pkg}|{condition}"
        curves[key] = {"days": g.storage_age_days.astype(int).tolist(),
                       "means": g["mean"].astype(float).tolist(),
                       "n_replicates_per_cell": 2}
        # Withhold the 60-day treatment cell. Interpolate from days 30 and 90 only.
        predicted = float(np.interp(60, [30, 90], [g.loc[g.storage_age_days.eq(30), "mean"].iloc[0],
                                                   g.loc[g.storage_age_days.eq(90), "mean"].iloc[0]]))
        actual = float(g.loc[g.storage_age_days.eq(60), "mean"].iloc[0])
        middle_predictions.append({"package_type": pkg, "storage_condition": condition,
                                   "held_out_day": 60, "observed_cell_mean": actual,
                                   "predicted_cell_mean": predicted, "error": predicted - actual})
    cv = pd.DataFrame(middle_predictions)
    cv.to_csv(OUT / "smoked_catfish_interpolation_check.csv", index=False)
    # Compare against a within-arm age-30 carry-forward baseline, avoiding day-90 access.
    carry = []
    for _, row in cv.iterrows():
        g = cells[(cells.package_type.eq(row.package_type)) & (cells.storage_condition.eq(row.storage_condition))]
        carry.append(float(g.loc[g.storage_age_days.eq(30), "mean"].iloc[0]))
    result = {"held_out_cell_mean_interpolation": metric(cv.observed_cell_mean, cv.predicted_cell_mean),
              "day30_carry_forward_baseline": metric(cv.observed_cell_mean, carry),
              "n_treatment_arms": 6, "n_postbaseline_measured_rows": 36,
              "n_independent_processing_runs": "unknown", "validation": "within-study cell interpolation only",
              "variable_temperature_kinetics": "BLOCKED",
              "all_endpoint_metrics": "smoked_catfish_all_endpoint_metrics.csv"}
    (OUT / "smoked_catfish_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    artifact = {"source": "mendeley_tvsw53j89z_v1", "target": "Peroxide value, source units",
                "temperature_conditions_c": {"Ambient": [25, 30], "Refrigerated": [4, 5]},
                "product_state": "smoked", "curves": curves,
                "warning": "Cell-mean interpolation; no independent run or variable-temperature validation."}
    (MODELS / "thermal/smoked_catfish_peroxide.json").write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    plt.figure(figsize=(7, 4))
    for (pkg, cond), g in cells.groupby(["package_type", "storage_condition"]):
        plt.plot(g.storage_age_days, g["mean"], marker="o", label=f"{pkg}, {cond}")
    plt.xlabel("Storage age, days")
    plt.ylabel("Peroxide value, source units")
    plt.legend(fontsize=7)
    plt.tight_layout()
    plt.savefig(FIG / "smoked_catfish_peroxide.png", dpi=180)
    plt.close()
    return result


def explore_dafif() -> dict:
    d = pd.read_parquet(ROOT / "data/curated/fish_sensor_observations.parquet")
    agg = d.groupby("recording_group_id").agg(
        species=("species_common", "first"), storage_age_days=("storage_age_days", "first"),
        session=("session_number", "first"), n_readings=("observation_id", "size"),
        mq_median=("mq135_raw", "median"), mq_iqr=("mq135_raw", lambda v: v.quantile(.75)-v.quantile(.25)),
        tgs_median=("tgs2602_raw", "median"), tgs_iqr=("tgs2602_raw", lambda v: v.quantile(.75)-v.quantile(.25))).reset_index()
    assert len(agg) == 63 and agg.n_readings.sum() == len(d)
    features = ["mq_median", "mq_iqr", "tgs_median", "tgs_iqr"]
    scaler = StandardScaler().fit(agg[features])
    x = scaler.transform(agg[features])
    pca = PCA(n_components=2, random_state=SEED).fit(x)
    xy = pca.transform(x)
    agg["pc1"], agg["pc2"] = xy[:, 0], xy[:, 1]
    trials = []
    for k in CONFIG["dafif"]["k_candidates"]:
        km = KMeans(n_clusters=k, random_state=SEED, n_init=20).fit(x)
        trials.append({"k": k, "silhouette": float(silhouette_score(x, km.labels_)),
                       "species_ari_description_only": float(adjusted_rand_score(agg.species, km.labels_))})
    trials_df = pd.DataFrame(trials)
    trials_df.to_csv(OUT / "dafif_cluster_trials.csv", index=False)
    k = int(trials_df.loc[trials_df.silhouette.idxmax(), "k"])
    km = KMeans(n_clusters=k, random_state=SEED, n_init=20).fit(x)
    agg["cluster"] = km.labels_
    agg.to_csv(OUT / "dafif_workbook_features_clusters.csv", index=False)
    joblib.dump({"features": features, "scaler": scaler, "pca": pca, "kmeans": km,
                "scope": "unsupervised 63 workbook clusters; no measured freshness targets"},
                MODELS / "exploration/dafif_workbooks.joblib")
    plt.figure(figsize=(6, 4))
    for species, g in agg.groupby("species"):
        plt.scatter(g.pc1, g.pc2, label=species, s=20 + g.storage_age_days*3, alpha=.7)
    plt.xlabel("PC1")
    plt.ylabel("PC2")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG / "dafif_workbook_pca.png", dpi=180)
    plt.close()
    result = {"n_sensor_readings": len(d), "n_workbooks": len(agg),
              "biological_fish_ids": 0, "selected_k": k,
              "silhouette": float(trials_df.loc[trials_df.k.eq(k), "silhouette"].iloc[0]),
              "pca_variance_explained": pca.explained_variance_ratio_.tolist(),
              "status": "unsupervised descriptive; no spoilage validation"}
    (OUT / "dafif_exploration.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def audit() -> dict:
    dafif = pd.read_parquet(ROOT / "data/curated/fish_sensor_observations.parquet")
    sensory = pd.read_parquet(ROOT / "data/curated/freshness_observed_labels.parquet")
    trout_sensor = pd.read_parquet(ROOT / "data/curated/trout_sensor_observations.parquet")
    trout_tvc = pd.read_parquet(ROOT / "data/curated/trout_microbiology_outcomes.parquet")
    catfish = pd.read_parquet(ROOT / "data/curated/fish_temperature_quality_experiments.parquet")
    result = {
        "dafif_sensor_rows": len(dafif), "dafif_workbooks": int(dafif.recording_group_id.nunique()),
        "dafif_fish_ids_nonnull": int(dafif.fish_or_lot_id.notna().sum()),
        "dafif_sensory_criterion_rows": len(sensory),
        "dafif_sensory_assessment_groups": int(sensory.groupby(["species_common", "storage_age_days", "session_number"]).ngroups),
        "dafif_sensory_linked_fish_ids": int(sensory.sensor_fish_id.notna().sum()),
        "dafif_official_folder_filename_conflict_rows": int(dafif.filename_session_conflict.sum()),
        "trout_sensor_rows": len(trout_sensor), "trout_sensor_fillets": int(trout_sensor.fillet_id.nunique()),
        "trout_sensor_sessions": int(trout_sensor.groupby(["fillet_id", "storage_age_days"]).ngroups),
        "trout_measured_tvc_fish": len(trout_tvc),
        "trout_tvc_paired_sensor_fish": int(trout_tvc.fish_or_fillet_id_link_to_sensor.notna().sum()),
        "trout_storage_temperature_conditions": trout_tvc.storage_temperature_protocol_c.unique().tolist(),
        "catfish_measured_rows": len(catfish), "catfish_postbaseline_rows": int(catfish.is_inferential_postbaseline.sum()),
        "catfish_product_states": catfish.product_state.unique().tolist(),
        "main_fresh_fish_supervised_sensor_classifier": "BLOCKED",
        "external_indian_shipment_validation": "BLOCKED",
    }
    assert result["dafif_sensor_rows"] == 27120 and result["dafif_workbooks"] == 63
    assert result["dafif_fish_ids_nonnull"] == 0 and result["trout_tvc_paired_sensor_fish"] == 0
    (OUT / "audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["all", "audit", "train-quality", "train-freshness", "tune-freshness", "train-thermal", "evaluate", "validate"])
    args = parser.parse_args()
    prepare()
    if args.command in ["all", "audit", "validate"]:
        print("AUDIT", json.dumps(audit(), indent=2))
    if args.command in ["all", "train-quality", "train-freshness", "tune-freshness"]:
        print("TROUT", json.dumps(trout(), indent=2))
        print("DAFIF", json.dumps(explore_dafif(), indent=2))
    if args.command in ["all", "train-thermal"]:
        print("CATFISH", json.dumps(catfish(), indent=2))
    if args.command == "evaluate":
        for filename in ["trout_results.json", "smoked_catfish_results.json", "dafif_exploration.json"]:
            print(filename, (OUT / filename).read_text(encoding="utf-8"))
    manifest = {"python": platform.python_version(), "platform": platform.platform(),
                "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__,
                "sklearn": sklearn.__version__, "matplotlib": matplotlib.__version__, "seed": SEED,
                "protocol_sha256": hashlib.sha256((ROOT / "configs/models/protocol.yaml").read_bytes()).hexdigest(),
                "curated_sha256": {p.stem: hashlib.sha256(p.read_bytes()).hexdigest() for p in (
                    ROOT / "data/curated").glob("*.parquet") if p.stem in [
                    "fish_sensor_observations", "freshness_observed_labels", "trout_sensor_observations",
                    "trout_microbiology_outcomes", "fish_temperature_quality_experiments"]},
                "artifact_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in (ROOT / "models").rglob("*") if p.is_file()}}
    (OUT / "environment_and_data.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
