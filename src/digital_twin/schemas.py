from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from math import isfinite


class TwinInputError(ValueError):
    pass


def finite(name: str, value: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TwinInputError(f"{name} must be finite numeric") from exc
    if not isfinite(number):
        raise TwinInputError(f"{name} must be finite")
    return number


@dataclass(frozen=True)
class ThermalEvent:
    kind: str
    start_h: float
    duration_h: float
    delta_c: float = 0.0

    def __post_init__(self):
        if self.kind not in {"refrigeration_off", "door_open", "setpoint_offset"}:
            raise TwinInputError(f"unsupported event kind: {self.kind}")
        if finite("event start_h", self.start_h) < 0 or finite("event duration_h", self.duration_h) <= 0:
            raise TwinInputError("event start must be >=0 and duration >0")
        finite("event delta_c", self.delta_c)


@dataclass(frozen=True)
class Stage:
    id: str
    name: str
    mode: str
    duration_h: float
    setpoint_c: float
    ambient_c: float
    assumption_type: str
    rationale: str
    events: tuple[ThermalEvent, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if not self.id or not self.name or not self.mode or not self.assumption_type or not self.rationale:
            raise TwinInputError("stage identity and assumption provenance are required")
        if finite("stage duration_h", self.duration_h) < 0:
            raise TwinInputError("stage duration cannot be negative")
        if not -40 <= finite("setpoint_c", self.setpoint_c) <= 60:
            raise TwinInputError("setpoint outside supported illustrative range")
        if not -40 <= finite("ambient_c", self.ambient_c) <= 60:
            raise TwinInputError("ambient outside supported illustrative range")
        for event in self.events:
            if event.start_h + event.duration_h > self.duration_h + 1e-9:
                raise TwinInputError(f"event extends beyond stage {self.id}")
        ordered = sorted(self.events, key=lambda e: e.start_h)
        if any(left.start_h + left.duration_h > right.start_h + 1e-9
               for left, right in zip(ordered, ordered[1:])):
            raise TwinInputError(f"overlapping events in stage {self.id}")


@dataclass(frozen=True)
class Route:
    id: str
    start_utc: datetime
    product_state: str
    species_common: str
    stages: tuple[Stage, ...]
    context: str

    def __post_init__(self):
        if self.start_utc.tzinfo is None or self.start_utc.utcoffset() is None:
            raise TwinInputError("route start must be timezone-aware")
        if self.start_utc.utcoffset() != timedelta(0):
            raise TwinInputError("route start must be expressed in UTC")
        if self.product_state != "ice_stored_chilled_finfish":
            raise TwinInputError("Phase 3 route supports chilled finfish only")
        if not self.stages or len({s.id for s in self.stages}) != len(self.stages):
            raise TwinInputError("route needs unique ordered stages")
        if not self.context:
            raise TwinInputError("route context required")


@dataclass(frozen=True)
class Scenario:
    id: str
    changes: tuple[dict, ...]


@dataclass(frozen=True)
class Shipment:
    id: str
    route: Route
    scenario: Scenario
    provenance_type: str = "hypothetical_synthetic_scenario"


@dataclass(frozen=True)
class TemperatureSample:
    start_utc: datetime
    end_utc: datetime
    stage_id: str
    air_start_c: float
    air_end_c: float
    estimated_product_start_c: float
    estimated_product_end_c: float
    source_type: str
    event_kind: str | None

    def __post_init__(self):
        if self.start_utc.tzinfo is None or self.end_utc.tzinfo is None:
            raise TwinInputError("temperature interval timestamps must be timezone-aware")
        if self.end_utc <= self.start_utc:
            raise TwinInputError("temperature interval must have positive elapsed time")
        for name in ["air_start_c", "air_end_c", "estimated_product_start_c", "estimated_product_end_c"]:
            finite(name, getattr(self, name))


@dataclass(frozen=True)
class SimulationRun:
    run_id: str
    shipment: Shipment
    temperature_mode: str
    step_minutes: int
    seed: int


@dataclass
class SimulationResult:
    run: SimulationRun
    samples: list[TemperatureSample]
    stage_metrics: list[dict]
    route_metrics: dict
    event_metrics: list[dict]
