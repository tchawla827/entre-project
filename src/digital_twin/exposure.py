"""Duration-weighted thermal indicators. All temperatures here are Celsius, all times hours."""
from __future__ import annotations

from datetime import timedelta
from math import isfinite

import numpy as np

from .schemas import TemperatureSample, TwinInputError


def linear_exceedance(t0: float, t1: float, duration_h: float, reference_c: float) -> tuple[float, float]:
    """Hours above reference and degree-hours for a linearly interpolated interval."""
    if not all(isfinite(float(v)) for v in [t0, t1, duration_h, reference_c]) or duration_h < 0:
        raise TwinInputError("nonfinite temperature/reference or negative duration")
    if duration_h == 0:
        return 0.0, 0.0
    a, b = t0 - reference_c, t1 - reference_c
    if a >= 0 and b >= 0:
        return duration_h, duration_h * (a + b) / 2
    if a <= 0 and b <= 0:
        return 0.0, 0.0
    crossing = abs(a) / (abs(a) + abs(b))
    if a > 0:
        hours = duration_h * crossing
        return hours, hours * a / 2
    hours = duration_h * (1 - crossing)
    return hours, hours * b / 2


def summarize(samples: list[TemperatureSample], references_c: list[float], channel: str) -> dict:
    if channel not in {"air", "estimated_product"}:
        raise TwinInputError("unknown temperature channel")
    start_attr, end_attr = (("air_start_c", "air_end_c") if channel == "air" else
                            ("estimated_product_start_c", "estimated_product_end_c"))
    total_h = 0.0
    temperatures = []
    result = {"channel": channel, "duration_h": 0.0, "peak_c": None,
              "mean_c": None, "references": {}}
    integral_temp = 0.0
    previous_end = None
    for s in samples:
        if previous_end is not None and s.start_utc != previous_end:
            raise TwinInputError("sample sequence has a gap, overlap or duplicate timestamp")
        h = (s.end_utc - s.start_utc).total_seconds() / 3600
        if h < 0:
            raise TwinInputError("negative sample interval")
        a, b = getattr(s, start_attr), getattr(s, end_attr)
        total_h += h
        integral_temp += (a+b)/2*h
        temperatures.extend([a, b])
        previous_end = s.end_utc
    result["duration_h"] = total_h
    result["peak_c"] = max(temperatures) if temperatures else None
    result["mean_c"] = integral_temp / total_h if total_h else None
    for ref in references_c:
        ref = float(ref)
        above = degree = current = maximum = 0.0
        for s in samples:
            h = (s.end_utc - s.start_utc).total_seconds()/3600
            a, b = getattr(s, start_attr), getattr(s, end_attr)
            ah, dh = linear_exceedance(a, b, h, ref)
            above += ah
            degree += dh
            if ah >= h - 1e-12 and h > 0:
                current += h
            elif ah > 0:
                if a > ref:
                    current += ah
                    maximum = max(maximum, current)
                    current = 0
                else:
                    current = ah
            else:
                maximum = max(maximum, current)
                current = 0
            maximum = max(maximum, current)
        result["references"][str(ref)] = {"hours_above": above,
                                           "percent_time_above": 100*above/total_h if total_h else None,
                                           "degree_hours": degree,
                                           "max_continuous_excursion_h": maximum}
    return result
