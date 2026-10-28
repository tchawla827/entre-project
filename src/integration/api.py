"""One Phase 5-facing API; delegates all simulation and inference to prior phases."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from src.digital_twin.phase2_adapter import capabilities, request_quality_trajectory, request_spoilage_probability
from src.digital_twin.routes import ROOT, load_config
from src.digital_twin.simulation import result_tables, simulate
from src.digital_twin.temperature import ProxyReplay
from src.models.inference import (UnsupportedCalibrationError, predict_smoked_catfish_endpoint,
                                  predict_trout_tvc)

from .schemas import IntegrationInputError, IntegrationRequest


class ArtifactUnavailableError(RuntimeError):
    """The pinned Phase 2 artifact is missing or changed; refuse loading it."""


def _verified_artifact(relative: str) -> Path:
    path = ROOT / relative
    manifest_path = ROOT / "reports/modeling/environment_and_data.json"
    if not path.is_file() or not manifest_path.is_file():
        raise ArtifactUnavailableError(f"Phase 2 artifact or integrity manifest missing: {relative}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = manifest.get("artifact_sha256", {}).get(relative.replace("/", "\\"))
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected is None or actual != expected:
        raise ArtifactUnavailableError(f"Phase 2 artifact hash mismatch or unknown version: {relative}")
    return path


def _configured(request: IntegrationRequest) -> dict:
    path = ROOT / "configs/digital_twin" / ("sea_route.yaml" if request.route == "sea" else "experiment.yaml")
    config = deepcopy(load_config(path))
    if request.scenario not in config["scenarios"]:
        raise IntegrationInputError("scenario is not configured for selected route")
    if request.start_utc:
        config["start_utc"] = request.start_utc
    config["air_reference_c"] = list(map(float, request.references_c))
    config["step_minutes"] = request.step_minutes
    valid_stage = {s["id"] for s in config["stages"]}
    for stage_id, changes in request.stage_overrides.items():
        if stage_id not in valid_stage or not isinstance(changes, dict):
            raise IntegrationInputError("invalid stage override")
        if set(changes) - {"duration_h", "setpoint_c", "ambient_c"}:
            raise IntegrationInputError("unsupported stage override field")
        next(s for s in config["stages"] if s["id"] == stage_id).update(changes)
    if set(request.perturb) - {"duration_multiplier", "setpoint_offset_c", "ambient_offset_c",
                                "air_tau_h", "product_tau_h", "event_duration_multiplier"}:
        raise IntegrationInputError("unsupported perturbation field")
    return config


def execute(request: IntegrationRequest | dict, *, include_trace: bool = True) -> dict:
    """Return v1 result. Unsupported biological targets raise, never fall back to exposure."""
    if isinstance(request, dict):
        request = IntegrationRequest.from_dict(request)
    if not isinstance(request, IntegrationRequest):
        raise IntegrationInputError("request must be IntegrationRequest or v1 dict")
    if request.target == "fresh_fish_quality_trajectory":
        return request_quality_trajectory(request.species, request.product_state, 0, [], [], "TVC")
    if request.target == "spoilage_probability":
        return request_spoilage_probability()
    if request.target == "trout_tvc_within_domain":
        if request.stage_overrides or request.perturb:
            raise IntegrationInputError("trout age-only diagnostic cannot accept route temperature perturbations")
        prediction = predict_trout_tvc(request.storage_age_days,
                                        artifact=_verified_artifact("models/freshness/trout_tvc.joblib"))
        return {"schema_version": 1, "target": request.target, "status": "LIMITED_WITHIN_STUDY",
                "prediction": prediction, "thermal_exposure": None, "trace": None,
                "reason": "age-only nominal-4 C study; no route or variable-temperature inference",
                "capabilities": capabilities()}
    if request.target == "smoked_catfish_endpoint_within_domain":
        if request.stage_overrides or request.perturb:
            raise IntegrationInputError("categorical smoked-product lookup cannot accept route perturbations")
        prediction = predict_smoked_catfish_endpoint(
            request.endpoint, request.package_type, request.storage_condition, request.storage_age_days,
            artifact=_verified_artifact("models/thermal/smoked_catfish_endpoints.json"))
        return {"schema_version": 1, "target": request.target, "status": "LIMITED_WITHIN_STUDY",
                "prediction": prediction, "thermal_exposure": None, "trace": None,
                "reason": "smoked-catfish categorical treatment; no route or fresh-fish inference",
                "capabilities": capabilities()}
    config = _configured(request)
    proxy = None if request.mode == "synthetic" else ProxyReplay(request.mode.split("_")[1], config)
    result = simulate(config, request.scenario, request.species, request.mode, proxy,
                      request.step_minutes, request.perturb, seed=request.seed)
    provenance = proxy.manifest() if proxy else {"type": "hypothetical_synthetic_first_order_air",
                                                  "observed_indian_shipment": False}
    return {"schema_version": 1, "target": "thermal_exposure", "status": "SIMULATED_EXPOSURE_ONLY",
            "request": asdict(request), "run_id": result.run.run_id,
            "route_id": result.run.shipment.route.id, "source_provenance": provenance,
            "source_class": "nonfish_proxy_shaped_synthetic" if proxy else "fully_synthetic",
            "thermal_exposure": {"route": result.route_metrics, "stages": result.stage_metrics,
                                 "events": result.event_metrics},
            "trace": result_tables(result) if include_trace else None,
            "trace_available": True, "prediction": None,
            "unavailable_reason": "no calibrated variable-temperature fresh-fish quality or spoilage model",
            "capabilities": capabilities()}
