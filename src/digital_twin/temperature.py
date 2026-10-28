"""Two independent trace generators: exact first-order synthetic state and attributed proxy residual replay."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .schemas import TwinInputError
from .routes import ROOT


class ProxyReplay:
    def __init__(self, kind: str, config: dict):
        if kind not in {"citrus", "coldroom"}:
            raise TwinInputError("proxy must be citrus or coldroom")
        self.kind = kind
        self.config = config["proxy_replay"][kind]
        if kind == "citrus":
            d = pd.read_parquet(ROOT / "data/curated/citrus_reefer_temperature_proxy.parquet",
                                columns=["source_file", "sensor_position_source", "elapsed_hours", "temperature_c"])
            d = d[d.source_file.eq(self.config["source_file"]) &
                  d.sensor_position_source.eq(self.config["sensor_position_source"]) &
                  d.elapsed_hours.ge(self.config["discard_first_h"])].sort_values("elapsed_hours")
            if d.empty or d.temperature_c.isna().any():
                raise TwinInputError("selected citrus proxy unavailable or missing")
            spacing = float(d.elapsed_hours.diff().dropna().median())
            if not np.allclose(d.elapsed_hours.diff().dropna(), spacing):
                raise TwinInputError("irregular citrus proxy interval")
            window = max(3, round(float(self.config["detrend_window_h"]) / spacing) + 1)
            baseline = d.temperature_c.rolling(window, center=True, min_periods=1).mean()
            residual = (d.temperature_c - baseline).to_numpy(dtype=float)
            self.source = f"berry_citrus_v2:{self.config['source_file']}:{self.config['sensor_position_source']}"
            self.original_unit = "source package-position temperature C; not fish or air"
            self.original_spacing_h = spacing
            self.raw_window = [float(d.temperature_c.min()), float(d.temperature_c.max())]
        else:
            d = pd.read_parquet(ROOT / "data/curated/coldroom_temperature_proxy.parquet",
                                columns=["sensor_id", "local_timestamp", "temperature_c"])
            d = d[d.sensor_id.eq(self.config["sensor_id"])].copy()
            d["local_timestamp"] = pd.to_datetime(d.local_timestamp)
            d = d.sort_values("local_timestamp")
            start = d.local_timestamp.min() + pd.Timedelta(hours=float(self.config["discard_first_h"]))
            end = start + pd.Timedelta(hours=float(self.config["window_h"]))
            d = d[d.local_timestamp.between(start, end, inclusive="left")]
            series = d.set_index("local_timestamp").temperature_c.resample(
                f"{int(self.config['resample_minutes'])}min").median()
            expected = round(float(self.config["window_h"]) * 60 / int(self.config["resample_minutes"]))
            series = series.iloc[:expected]
            if series.empty or series.isna().any():
                raise TwinInputError("selected coldroom replay window has missing intervals")
            residual = (series - series.median()).to_numpy(dtype=float)
            self.source = f"zenodo_15130001:{self.config['sensor_id']}:after_{self.config['discard_first_h']}h"
            self.original_unit = "generic cold-room local sensor C; timezone/location unknown"
            self.original_spacing_h = float(self.config["resample_minutes"]) / 60
            self.raw_window = [float(series.min()), float(series.max())]
        if len(residual) < 4 or not np.isfinite(residual).all():
            raise TwinInputError("proxy replay lacks finite samples")
        self.residual = residual
        self.hours = np.arange(len(residual), dtype=float) * self.original_spacing_h
        self.period_h = len(residual) * self.original_spacing_h

    def offset_c(self, elapsed_route_h: float) -> float:
        """Cycles source residual shape on the synthetic route clock; source times are not shipment times."""
        x = elapsed_route_h % self.period_h
        return float(np.interp(x, np.r_[self.hours, self.period_h],
                               np.r_[self.residual, self.residual[0]]))

    def manifest(self) -> dict:
        return {"kind": self.kind, "source": self.source, "source_channel": self.original_unit,
                "transform": self.config["replay_policy"], "offset_to_synthetic_setpoint": True,
                "stage_local_cycle": False, "route_clock_cycle": True,
                "source_timezone": "unknown_or_not_applicable_relative_time",
                "source_window_c": self.raw_window,
                "residual_quantiles_c": np.quantile(self.residual, [0, .05, .5, .95, 1]).tolist(),
                "spacing_h": self.original_spacing_h, "period_h": self.period_h,
                "warning": self.config["source_channel_warning"]}
