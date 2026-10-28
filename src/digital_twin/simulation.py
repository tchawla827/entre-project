"""Stateful stage simulation with exact first-order temperature transitions."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import timedelta
from math import exp

from .exposure import summarize, linear_exceedance
from .routes import make_route
from .schemas import (Shipment, SimulationRun, SimulationResult, TemperatureSample,
                      TwinInputError)
from .temperature import ProxyReplay


def _end_product(air0: float, product0: float, target: float, duration_h: float,
                 air_tau_h: float, product_tau_h: float) -> float:
    ea, ep = exp(-duration_h/air_tau_h), exp(-duration_h/product_tau_h)
    if abs(air_tau_h-product_tau_h) < 1e-10:
        factor = (duration_h/product_tau_h) * ep
    else:
        factor = air_tau_h/(air_tau_h-product_tau_h) * (ea-ep)
    return target + (product0-target)*ep + (air0-target)*factor


def simulate(config: dict, scenario_id: str = "baseline", species: str = "Mackerel",
             mode: str = "synthetic", proxy: ProxyReplay | None = None,
             step_minutes: int | None = None, perturb: dict | None = None,
             custom_changes: list[dict] | None = None, seed: int = 0) -> SimulationResult:
    if mode not in {"synthetic", "proxy_citrus", "proxy_coldroom"}:
        raise TwinInputError("unsupported temperature generator")
    if mode.startswith("proxy") and (proxy is None or proxy.kind != mode.split("_")[1]):
        raise TwinInputError("matching attributed ProxyReplay required")
    if mode == "synthetic" and proxy is not None:
        raise TwinInputError("synthetic mode does not accept proxy")
    step = int(step_minutes or config["step_minutes"])
    if not 1 <= step <= 60:
        raise TwinInputError("step must be 1-60 minutes")
    p = perturb or {}
    air_tau = float(p.get("air_tau_h", config["air_dynamics_tau_h"]))
    product_tau = float(p.get("product_tau_h", config["illustrative_product_lag_tau_h"]))
    if air_tau <= 0 or product_tau <= 0:
        raise TwinInputError("time constants must be positive")
    route, scenario = make_route(config, species, scenario_id, perturb, custom_changes)
    shipment = Shipment(id=f"hypothetical:{route.id}:{scenario.id}", route=route, scenario=scenario)
    signature = json.dumps({"resolved_route": asdict(route), "scenario": asdict(scenario),
                            "mode": mode, "proxy": proxy.manifest() if proxy else None,
                            "step": step, "air_tau_h": air_tau, "product_tau_h": product_tau,
                            "initial_air_c": config["initial_air_c"],
                            "initial_estimated_product_c": config["initial_estimated_product_c"],
                            "references_c": config["air_reference_c"], "seed": seed},
                           sort_keys=True, default=str)
    run_id = hashlib.sha256(signature.encode()).hexdigest()[:16]
    run = SimulationRun(run_id=run_id, shipment=shipment, temperature_mode=mode,
                        step_minutes=step, seed=seed)
    current_time = route.start_utc
    air = float(config["initial_air_c"])
    product = float(config["initial_estimated_product_c"])
    samples: list[TemperatureSample] = []
    stage_rows = []
    event_rows = []
    refs = [float(x) for x in config["air_reference_c"]]
    for stage in route.stages:
        stage_start = current_time
        stage_samples = []
        elapsed = 0.0
        boundaries = sorted({0.0, stage.duration_h} |
                            {v for e in stage.events for v in (e.start_h, e.start_h+e.duration_h)})
        while elapsed < stage.duration_h - 1e-10:
            next_boundary = min((v for v in boundaries if v > elapsed + 1e-10), default=stage.duration_h)
            dt = min(step/60, stage.duration_h-elapsed, next_boundary-elapsed)
            if dt <= 0:
                raise TwinInputError("nonprogressing simulation step")
            active = [e for e in stage.events if e.start_h <= elapsed + 1e-10 < e.start_h+e.duration_h-1e-10]
            if len(active) > 1:
                raise TwinInputError(f"overlapping events in {stage.id}")
            event = active[0] if active else None
            route_elapsed_h = (current_time-route.start_utc).total_seconds()/3600
            target = stage.setpoint_c + (proxy.offset_c(route_elapsed_h) if proxy is not None else 0.0)
            tau = air_tau
            if event:
                if event.kind == "refrigeration_off":
                    target = stage.ambient_c
                elif event.kind == "door_open":
                    target = stage.ambient_c
                    tau = min(air_tau, 0.2)  # Assumed rapid air exchange, not a measured door coefficient.
                else:
                    target += event.delta_c
            new_air = target+(air-target)*exp(-dt/tau)
            new_product = _end_product(air, product, target, dt, tau, product_tau)
            end_time = current_time + timedelta(hours=dt)
            sample = TemperatureSample(start_utc=current_time, end_utc=end_time,
                                       stage_id=stage.id, air_start_c=air, air_end_c=new_air,
                                       estimated_product_start_c=product,
                                       estimated_product_end_c=new_product,
                                       source_type=("synthetic_first_order_air" if proxy is None else
                                                    "synthetic_air_shaped_by_nonfish_proxy_residual"),
                                       event_kind=event.kind if event else None)
            samples.append(sample)
            stage_samples.append(sample)
            current_time = end_time
            elapsed += dt
            air, product = new_air, new_product
        air_metrics = summarize(stage_samples, refs, "air")
        product_metrics = summarize(stage_samples, refs, "estimated_product")
        stage_rows.append({"stage_id": stage.id, "name": stage.name, "mode": stage.mode,
                           "start_utc": stage_start.isoformat(), "end_utc": current_time.isoformat(),
                           "duration_h": stage.duration_h, "setpoint_c": stage.setpoint_c,
                           "ambient_assumed_c": stage.ambient_c, "assumption_type": stage.assumption_type,
                           "rationale": stage.rationale, "air": air_metrics,
                           "estimated_product": product_metrics})
        for event in stage.events:
            event_start = stage_start + timedelta(hours=event.start_h)
            event_end = event_start + timedelta(hours=event.duration_h)
            active_samples = [s for s in stage_samples if s.start_utc >= event_start and s.end_utc <= event_end]
            event_exposure = summarize(active_samples, refs, "air")
            recovery = None
            for s in stage_samples:
                if s.start_utc < event_end:
                    continue
                if s.air_start_c <= stage.setpoint_c + 0.5:
                    recovery = (s.start_utc-event_end).total_seconds()/3600
                    break
                if s.air_end_c <= stage.setpoint_c + 0.5:
                    frac = (s.air_start_c-(stage.setpoint_c+0.5))/(s.air_start_c-s.air_end_c)
                    recovery = (s.start_utc-event_end).total_seconds()/3600 + frac * (
                        s.end_utc-s.start_utc).total_seconds()/3600
                    break
            event_rows.append({"stage_id": stage.id, "kind": event.kind,
                               "start_utc": event_start.isoformat(), "end_utc": event_end.isoformat(),
                               "duration_h": event.duration_h, "air_exposure_during_event": event_exposure,
                               "time_to_recovery_h": recovery,
                               "recovery_censored_at_stage_end": recovery is None})
    route_air = summarize(samples, refs, "air")
    route_product = summarize(samples, refs, "estimated_product")
    for channel, whole in [("air", route_air), ("estimated_product", route_product)]:
        for ref in refs:
            key = str(ref)
            denominator = whole["references"][key]["degree_hours"]
            for stage in stage_rows:
                numer = stage[channel]["references"][key]["degree_hours"]
                stage[channel]["references"][key]["fraction_of_route_degree_hours"] = (
                    numer/denominator if denominator > 0 else None)
    metrics = {"schema_version": 1, "route_id": route.id, "scenario": scenario.id,
               "run_id": run_id, "product_state": route.product_state,
               "species_common_source_category": species, "temperature_mode": mode,
               "air": route_air, "estimated_product": route_product,
               "simulator_parameters": {"step_minutes": step, "air_tau_h": air_tau,
                                        "illustrative_product_tau_h": product_tau,
                                        "door_open_air_tau_h": "min(air_tau_h, 0.2), assumed",
                                        "initial_air_c": config["initial_air_c"],
                                        "initial_estimated_product_c": config["initial_estimated_product_c"],
                                        "reference_c": refs,
                                        "product_channel": "illustrative first-order estimate, not measured fish core"},
               "spoilage_probability_status": "NOT_CALIBRATED",
               "quality_trajectory_status": "NOT_CALIBRATED"}
    return SimulationResult(run=run, samples=samples, stage_metrics=stage_rows,
                            route_metrics=metrics, event_metrics=event_rows)


def result_tables(result: SimulationResult):
    """Small, plain records for CSV/Parquet export; times remain ISO UTC."""
    samples = []
    for s in result.samples:
        row = asdict(s)
        row["start_utc"], row["end_utc"] = s.start_utc.isoformat(), s.end_utc.isoformat()
        row["run_id"] = result.run.run_id
        row["schema_version"] = 1
        samples.append(row)
    return samples
