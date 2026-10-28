"""Strict inference contracts for the two empirical Phase 2 branches."""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]


class UnsupportedCalibrationError(ValueError):
    pass


def predict_trout_tvc(storage_age_days: float, artifact: Path | None = None) -> dict:
    """Expected log10 CFU/g for this one nominal-4 C trout study, ages 0-6 only."""
    if not np.isfinite(storage_age_days) or not 0 <= storage_age_days <= 6:
        raise UnsupportedCalibrationError("Trout storage age must be 0-6 days.")
    path = artifact or ROOT / "models" / "freshness" / "trout_tvc.joblib"
    saved = joblib.load(path)
    value = float(saved["estimator"].predict(pd.DataFrame({"storage_age_days": [storage_age_days]}))[0])
    return {
        "expected_tvc_log10_cfu_g": value,
        "study": "zenodo_23600663_v4",
        "scope": "internal exploratory regression; rainbow trout fillet at nominal 4 C",
        "not_a_spoilage_probability": True,
    }


def predict_smoked_catfish_peroxide(
    package_type: str, storage_condition: str, storage_age_days: float,
    artifact: Path | None = None,
) -> dict:
    """Treatment-cell interpolation; cannot accept arbitrary temperatures."""
    if not np.isfinite(storage_age_days) or not 0 <= storage_age_days <= 90:
        raise UnsupportedCalibrationError("Smoked-catfish age must be 0-90 days.")
    path = artifact or ROOT / "models" / "thermal" / "smoked_catfish_peroxide.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    key = f"{package_type}|{storage_condition}"
    if key not in data["curves"]:
        raise UnsupportedCalibrationError("Unsupported packaging/condition; see saved curve keys.")
    curve = data["curves"][key]
    val = float(np.interp(storage_age_days, curve["days"], curve["means"]))
    return {
        "estimated_peroxide_value_source_units": val,
        "study": "mendeley_tvsw53j89z_v1",
        "scope": "smoked catfish, categorical ambient 25-30 C or refrigerated 4-5 C; interpolation only",
        "not_a_spoilage_probability": True,
    }


def predict_smoked_catfish_endpoint(
    endpoint: str, package_type: str, storage_condition: str, storage_age_days: float,
    artifact: Path | None = None,
) -> dict:
    """Interpolate one of seven measured smoked-catfish endpoint cell curves."""
    if not np.isfinite(storage_age_days) or not 0 <= storage_age_days <= 90:
        raise UnsupportedCalibrationError("Smoked-catfish age must be 0-90 days.")
    path = artifact or ROOT / "models" / "thermal" / "smoked_catfish_endpoints.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    key = f"{package_type}|{storage_condition}"
    try:
        curve = data["curves_by_endpoint"][endpoint][key]
    except KeyError as e:
        raise UnsupportedCalibrationError("Unsupported smoked-catfish endpoint, packaging or condition.") from e
    return {"estimated_source_value": float(np.interp(storage_age_days, curve["days"], curve["means"])),
            "endpoint": endpoint, "source": data["source"],
            "scope": "smoked catfish categorical-treatment interpolation; not variable-temperature kinetics",
            "not_a_spoilage_probability": True}


def predict_quality_trajectory(
    species: str, product_state: str, initial_quality: float,
    timestamps: list, temperature_c: list[float], endpoint: str,
) -> dict:
    """Reserved Phase 3 interface; refuses unsupported variable-temperature inference."""
    raise UnsupportedCalibrationError(
        "No fish-specific, independently validated variable-temperature trajectory calibration "
        "is available. Smoked-catfish categorical treatment interpolation is exposed separately."
    )
