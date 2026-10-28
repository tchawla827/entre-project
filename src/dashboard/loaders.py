"""Schema-gated Phase 4 analysis artifacts."""
from pathlib import Path
import json
import pandas as pd

from src.digital_twin.routes import ROOT

DATA = ROOT / "results" / "integration"
REQUIRED = {
    "scenario_comparison": {"schema_version", "route", "mode", "scenario", "channel", "reference_c", "degree_hours", "delta_degree_hours", "relative_delta_fraction", "run_id"},
    "stage_contributions": {"schema_version", "route", "mode", "scenario", "channel", "reference_c", "stage_id", "degree_hours"},
    "intervention_attribution": {"route", "reference_c", "intervention", "shapley_degree_hours", "run_scope"},
    "standardized_interventions": {"route", "reference_c", "stage_id", "event_delta_c", "event_duration_h", "delta_degree_hours"},
    "sensitivity_draws": {"route", "draw", "scenario", "delta_degree_hours_above_2c", "delta_degree_hours_above_4c"},
    "ranking_draws": {"route", "draw", "reference_c", "dominant_intervention"},
    "stage_rank_draws": {"route", "draw", "reference_c", "channel", "top_stage_id"},
    "stress_profiles": {"route", "profile", "scenario", "reference_c", "delta_degree_hours"},
    "monte_carlo_convergence": {"route", "draws", "reference_c", "combined_median_delta_degree_hours"},
}


def artifact_stamp(name: str) -> int:
    return (DATA / f"{name}.parquet").stat().st_mtime_ns


def load_table(name: str) -> pd.DataFrame:
    if name not in REQUIRED:
        raise ValueError(f"Unknown analysis table: {name}")
    path = DATA / f"{name}.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"Phase 4 artifact missing: {path}. Regenerate with python -m src.integration.cli run/analyze --all")
    frame = pd.read_parquet(path)
    missing = REQUIRED[name] - set(frame.columns)
    if missing:
        raise ValueError(f"Phase 4 artifact {name} missing columns: {sorted(missing)}")
    if "schema_version" in frame and (frame["schema_version"] != 1).any():
        raise ValueError(f"Unsupported {name} schema version")
    return frame


def load_json(name: str) -> dict:
    if name not in {"capability_matrix", "claim_evidence_matrix", "run_manifest", "provenance_manifest"}:
        raise ValueError("Unknown manifest")
    path = DATA / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Phase 4 manifest missing: {path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("schema_version", 1) != 1:
        raise ValueError(f"Unsupported {name} schema version")
    return obj
