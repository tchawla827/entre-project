"""Versioned request contract. Temperatures are Celsius; elapsed times are hours."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from math import isfinite


class IntegrationInputError(ValueError):
    pass


TARGETS = {"thermal_exposure", "trout_tvc_within_domain", "smoked_catfish_endpoint_within_domain",
           "fresh_fish_quality_trajectory", "spoilage_probability"}
MODES = {"synthetic", "proxy_citrus", "proxy_coldroom"}


@dataclass(frozen=True)
class IntegrationRequest:
    target: str = "thermal_exposure"
    route: str = "air"
    scenario: str = "baseline"
    mode: str = "synthetic"
    species: str = "Mackerel"
    product_state: str = "ice_stored_chilled_finfish"
    temperature_unit: str = "C"
    references_c: tuple[float, ...] = (2.0, 4.0)
    step_minutes: int = 15
    seed: int = 0
    start_utc: str | None = None
    stage_overrides: dict = field(default_factory=dict)
    perturb: dict = field(default_factory=dict)
    storage_age_days: float | None = None
    endpoint: str | None = None
    package_type: str | None = None
    storage_condition: str | None = None

    def __post_init__(self):
        if self.target not in TARGETS:
            raise IntegrationInputError("unsupported target")
        if self.route not in {"air", "sea"} or self.mode not in MODES:
            raise IntegrationInputError("unsupported route or temperature source")
        if self.temperature_unit != "C":
            raise IntegrationInputError("temperature_unit must be C; no implicit conversion")
        if type(self.step_minutes) is not int or not 1 <= self.step_minutes <= 60:
            raise IntegrationInputError("step_minutes must be integer in 1..60")
        if type(self.seed) is not int or self.seed < 0:
            raise IntegrationInputError("seed must be nonnegative integer")
        if not self.references_c or any(not isfinite(float(x)) or not -40 <= float(x) <= 60
                                        for x in self.references_c):
            raise IntegrationInputError("references_c must be finite Celsius values in -40..60")
        if len(set(map(float, self.references_c))) != len(self.references_c):
            raise IntegrationInputError("duplicate temperature reference")
        if self.start_utc is not None:
            try:
                start = datetime.fromisoformat(self.start_utc)
            except (TypeError, ValueError) as exc:
                raise IntegrationInputError("invalid ISO start_utc") from exc
            if start.tzinfo is None or start.utcoffset() != timedelta(0):
                raise IntegrationInputError("start_utc must include UTC offset +00:00")
        if self.product_state != "ice_stored_chilled_finfish" and self.target == "thermal_exposure":
            raise IntegrationInputError("only chilled-finfish routes are configured")
        if self.target == "trout_tvc_within_domain":
            if self.species != "Rainbow trout" or self.product_state != "trout_fillet_nominal_4c":
                raise IntegrationInputError("trout TVC requires rainbow trout fillet at nominal 4 C")
        if self.target == "smoked_catfish_endpoint_within_domain":
            if self.species != "Smoked catfish" or self.product_state != "smoked_catfish":
                raise IntegrationInputError("smoked endpoint requires smoked catfish product state")
        if self.target in {"trout_tvc_within_domain", "smoked_catfish_endpoint_within_domain"}:
            if self.storage_age_days is None or not isfinite(float(self.storage_age_days)):
                raise IntegrationInputError("storage_age_days is required")
        if self.target == "smoked_catfish_endpoint_within_domain" and not all(
                [self.endpoint, self.package_type, self.storage_condition]):
            raise IntegrationInputError("endpoint, package_type and storage_condition are required")
        if not isinstance(self.stage_overrides, dict) or not isinstance(self.perturb, dict):
            raise IntegrationInputError("stage_overrides and perturb must be objects")

    @classmethod
    def from_dict(cls, data: dict) -> "IntegrationRequest":
        if not isinstance(data, dict) or data.get("schema_version", 1) != 1:
            raise IntegrationInputError("unsupported request schema version")
        allowed = set(cls.__dataclass_fields__) | {"schema_version"}
        unknown = set(data) - allowed
        if unknown:
            raise IntegrationInputError(f"unknown request fields: {sorted(unknown)}")
        values = {k: v for k, v in data.items() if k != "schema_version"}
        if "references_c" in values:
            values["references_c"] = tuple(values["references_c"])
        return cls(**values)
