from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path

import yaml

from .schemas import Route, Scenario, Stage, ThermalEvent, TwinInputError


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs/digital_twin/experiment.yaml"


def load_config(path: Path = DEFAULT_CONFIG) -> dict:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if "extends" in raw:
        config = deepcopy(load_config(path.parent / raw["extends"]))
        rename = raw.get("stage_rename", {})
        for stage in config["stages"]:
            stage["id"] = rename.get(stage["id"], stage["id"])
        for item in config["scenarios"].values():
            for change in item["changes"]:
                change["stage"] = rename.get(change["stage"], change["stage"])
        config["scenarios"] = {
            raw.get("scenario_rename", {}).get(key, key): value for key, value in config["scenarios"].items()}
        for stage in config["stages"]:
            stage.update(raw.get("stage_overrides", {}).get(stage["id"], {}))
        config["scenarios"].update(raw.get("scenario_overrides", {}))
        for key in ["route_id", "context"]:
            if key in raw:
                config[key] = raw[key]
    else:
        config = raw
    if config.get("schema_version") != 1:
        raise TwinInputError("unsupported experiment schema version")
    ids = [x["id"] for x in config["stages"]]
    if len(ids) != len(set(ids)):
        raise TwinInputError("duplicate stage ID in config")
    if any(change["stage"] not in set(ids) for s in config["scenarios"].values() for change in s["changes"]):
        raise TwinInputError("scenario change refers to unknown stage after route resolution")
    return config


def make_route(config: dict, species: str = "Mackerel", scenario_id: str = "baseline",
               perturb: dict | None = None, custom_changes: list[dict] | None = None) -> tuple[Route, Scenario]:
    if species not in config["species_options"]:
        raise TwinInputError(f"unsupported source common-name category: {species}")
    if scenario_id not in config["scenarios"] and custom_changes is None:
        raise TwinInputError(f"unknown scenario: {scenario_id}")
    changes = custom_changes if custom_changes is not None else config["scenarios"][scenario_id]["changes"]
    stage_ids = {s["id"] for s in config["stages"]}
    if any(c["stage"] not in stage_ids for c in changes):
        raise TwinInputError("scenario refers to unknown stage")
    if len({c["stage"] for c in changes}) != len(changes):
        raise TwinInputError("multiple change blocks for same stage")
    by_stage = {c["stage"]: c for c in changes}
    p = perturb or {}
    stages = []
    for source in config["stages"]:
        c = by_stage.get(source["id"], {})
        duration = (float(source["duration_h"]) * float(p.get("duration_multiplier", 1.0))
                    + float(c.get("duration_delta_h", 0)))
        setpoint = (float(source["setpoint_c"]) + float(p.get("setpoint_offset_c", 0))
                    + float(c.get("setpoint_delta_c", 0)))
        ambient = float(source["ambient_c"]) + float(p.get("ambient_offset_c", 0))
        event_scale = float(p.get("event_duration_multiplier", 1))
        events = tuple(ThermalEvent(kind=e["kind"], start_h=float(e["start_h"]),
                                    duration_h=float(e["duration_h"]) * event_scale,
                                    delta_c=float(e.get("delta_c", 0))) for e in c.get("events", []))
        stages.append(Stage(id=source["id"], name=source["name"], mode=source["mode"],
                            duration_h=duration, setpoint_c=setpoint, ambient_c=ambient,
                            assumption_type=source["assumption_type"], rationale=source["rationale"],
                            events=events))
    route = Route(id=config["route_id"], start_utc=datetime.fromisoformat(config["start_utc"]),
                  product_state=config["product_state"], species_common=species,
                  stages=tuple(stages), context=config["context"])
    return route, Scenario(id=scenario_id, changes=tuple(changes))
