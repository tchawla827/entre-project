"""Capabilities are explicit; Phase 3 never substitutes exposure for biological prediction."""
from __future__ import annotations

from src.models.inference import (UnsupportedCalibrationError, predict_quality_trajectory,
                                  predict_smoked_catfish_endpoint, predict_trout_tvc)


def capabilities() -> dict:
    return {
        "trout_tvc": {"status": "LIMITED", "scope": "age-only, nominal 4 C, one study; separate diagnostic"},
        "smoked_catfish_endpoint": {"status": "LIMITED", "scope": "categorical treatment lookup; smoked product"},
        "dafif_clusters": {"status": "DESCRIPTIVE_ONLY", "scope": "unlabeled workbook patterns"},
        "fresh_finfish_variable_temperature_quality": {"status": "NOT_CALIBRATED"},
        "spoilage_probability": {"status": "NOT_CALIBRATED"},
    }


def request_quality_trajectory(*args, **kwargs):
    return predict_quality_trajectory(*args, **kwargs)


def request_spoilage_probability(*args, **kwargs):
    raise UnsupportedCalibrationError(
        "No paired fish temperature history and measured spoilage outcome support a calibrated probability."
    )
