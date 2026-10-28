"""Focused UI for the Phase 4 thermal-exposure service.

Run from the repository root: python -m streamlit run app.py
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.export import selected_files, zip_bytes
from src.dashboard.loaders import artifact_stamp, load_table
from src.dashboard.service import (channel_summary, event_rows, make_request,
                                   options, request_key, run_pair, stage_rows)
from src.integration.schemas import IntegrationInputError
from src.models.inference import UnsupportedCalibrationError


st.set_page_config(page_title="Cold Chain | Thermal Simulator", layout="wide", initial_sidebar_state="auto")
st.markdown("""<style>
  .block-container {max-width: 1180px; padding-top: 2.2rem; padding-bottom: 3rem}
  [data-testid="stSidebar"] {border-right: 1px solid #e2e8ee}
  [data-testid="stMetricValue"] {font-size: 2.05rem}
  [data-testid="stMetricDelta"] {font-size: .86rem}
  .title {font-size:2.4rem; font-weight:650; letter-spacing:-.04em; line-height:1.1; margin:0}
  .subtitle {color:#55707f; font-size:1rem; margin:.55rem 0 1.3rem}
  .scope {display:inline-block; color:#87571d; background:#fbf4e9; border:1px solid #eadbc3;
          font-size:.8rem; font-weight:600; border-radius:30px; padding:.28rem .7rem; margin-bottom:1.3rem}
  .section-label {font-size:1.15rem; font-weight:650; margin:1.6rem 0 .4rem; color:#173547}
  .fine {color:#607887; font-size:.82rem}
  [data-testid="stVerticalBlockBorderWrapper"] {border-color:#e5ebef}
</style>""", unsafe_allow_html=True)


def label(value: str) -> str:
    return value.replace("_", " ").title()


def num(value: float | None, unit: str = "") -> str:
    return "N/A" if value is None else f"{value:,.2f}{unit}"


def chart_style(fig: go.Figure, height=360) -> go.Figure:
    fig.update_layout(template="plotly_white", height=height, margin=dict(l=5, r=10, t=20, b=30),
                      font=dict(family="Arial, sans-serif", color="#314b59", size=12),
                      legend=dict(orientation="h", y=1.13, x=0), hovermode="x unified",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    fig.update_xaxes(showgrid=False, linecolor="#dce4e8", zeroline=False)
    fig.update_yaxes(gridcolor="#eaf0f2", zeroline=False)
    return fig


@st.cache_data(show_spinner=False)
def saved_comparison(stamp: int) -> pd.DataFrame:
    return load_table("scenario_comparison")


with st.sidebar:
    st.markdown("### Configure run")
    route = st.selectbox("Route", ["air", "sea"], format_func=str.title, key="route")
    scenario = st.selectbox("Scenario", options(route)["scenarios"], format_func=label, key=f"scenario_{route}")
    mode = st.selectbox("Temperature source", ["synthetic", "proxy_citrus", "proxy_coldroom"],
                        format_func=lambda x: {"synthetic":"Synthetic", "proxy_citrus":"Citrus proxy shape",
                                               "proxy_coldroom":"Cold-room proxy shape"}[x], key="mode")
    reference = st.selectbox("Comparison reference", [2.0, 4.0], format_func=lambda x: f"{x:g} °C", key="reference")
    channel = st.selectbox("Channel", ["air", "estimated_product"],
                           format_func=lambda x: "Simulated air" if x == "air" else "Assumed product lag", key="channel")
    run_clicked = st.button("Run simulation", type="primary", width="stretch")

try:
    request = make_request(route, scenario, mode, reference, channel, seed=2404, step=15)
    key = request_key(request, channel)
except (ValueError, IntegrationInputError) as exc:
    st.error(f"Check the input settings: {exc}")
    st.stop()

if "run_key" not in st.session_state:
    initial = make_request()
    st.session_state.run_result, st.session_state.baseline_result = run_pair(initial)
    st.session_state.run_key = request_key(initial, "air")
if run_clicked:
    try:
        with st.spinner("Running simulation…"):
            result, base = run_pair(request)
        st.session_state.run_result = result
        st.session_state.baseline_result = base
        st.session_state.run_key = key
    except (ValueError, IntegrationInputError, UnsupportedCalibrationError, FileNotFoundError, OSError) as exc:
        st.error(f"Run unavailable: {exc}")

current = st.session_state.run_key == key
result = st.session_state.run_result if current else None
base = st.session_state.baseline_result if current else None

st.markdown('<h1 class="title">Thermal exposure simulator</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Explore how a configured disruption changes a hypothetical chilled route.</p>', unsafe_allow_html=True)
st.markdown('<div class="scope">Simulation only · Fish spoilage is not calibrated</div>', unsafe_allow_html=True)

run_tab, compare_tab = st.tabs(["Simulation", "Compare scenarios"])

with run_tab:
    if not current:
        st.info("Settings changed. Run the simulation to update this view.")
    else:
        summary = channel_summary(result, channel, reference)
        baseline = channel_summary(base, channel, reference)
        delta = summary["degree_hours"] - baseline["degree_hours"]
        top = st.columns(3)
        top[0].metric(f"Exposure above {reference:g} °C", num(summary["degree_hours"], " °C·h"))
        top[1].metric("Change from baseline", num(delta, " °C·h"))
        top[2].metric("Peak temperature", num(summary["peak_c"], " °C"))
        st.markdown(f'<p class="fine">{label(route)} route · {label(scenario)} · {summary["duration_h"]:g} h · '
                    f'{summary["hours_above"]:.1f} h above reference · '
                    f'{summary["degree_hours_per_route_hour"]:.2f} °C·h per route hour</p>',
                    unsafe_allow_html=True)

        trace = pd.DataFrame(result["trace"])
        if trace.empty:
            st.warning("No temperature intervals were returned for this run.")
        else:
            start = pd.Timestamp(trace.iloc[0]["start_utc"])
            elapsed = [(pd.Timestamp(t) - start).total_seconds() / 3600 for t in trace["end_utc"]]
            selected_column = "air_end_c" if channel == "air" else "estimated_product_end_c"
            selected_start = "air_start_c" if channel == "air" else "estimated_product_start_c"
            x = [0.0, *elapsed]
            y = [trace.iloc[0][selected_start], *trace[selected_column].tolist()]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name="Air" if channel == "air" else "Product lag (assumed)",
                                     line=dict(color="#147a85", width=3), hovertemplate="%{x:.1f} h · %{y:.2f} °C<extra></extra>"))
            fig.add_hline(y=reference, line_color="#b47848", line_dash="dash", line_width=1.5)
            for stage in result["thermal_exposure"]["stages"][1:]:
                h = (pd.Timestamp(stage["start_utc"]) - start).total_seconds() / 3600
                fig.add_vline(x=h, line_color="#dce5e8", line_width=1)
            for event in result["thermal_exposure"]["events"]:
                h0 = (pd.Timestamp(event["start_utc"]) - start).total_seconds() / 3600
                h1 = (pd.Timestamp(event["end_utc"]) - start).total_seconds() / 3600
                fig.add_vrect(x0=h0, x1=h1, fillcolor="#e5b571", opacity=.22, line_width=0)
            fig.update_xaxes(title="Hours from route start")
            fig.update_yaxes(title="Temperature (°C)")
            st.markdown('<div class="section-label">Temperature through the route</div>', unsafe_allow_html=True)
            st.plotly_chart(chart_style(fig, 385), width="stretch")
            st.caption("Vertical lines: stage changes · Shaded areas: disruption events · Dashed line: comparison reference")

        rows = pd.DataFrame(stage_rows(result, channel, reference))
        if scenario == "baseline":
            left, right = st.container(), None
        else:
            left, right = st.columns([1.45, 1], gap="large")
        with left:
            st.markdown('<div class="section-label">Where exposure occurs</div>', unsafe_allow_html=True)
            if rows.empty:
                st.info("No stages to display.")
            else:
                ordered = rows.iloc[::-1]
                bars = go.Figure(go.Bar(x=ordered["degree_hours"], y=ordered["stage"], orientation="h",
                                        marker_color="#147a85", hovertemplate="%{y}<br>%{x:.2f} °C·h<extra></extra>"))
                bars.update_xaxes(title="Exposure (°C·h)")
                st.plotly_chart(chart_style(bars, 335), width="stretch")
        if right is not None:
            with right:
                st.markdown('<div class="section-label">Against baseline</div>', unsafe_allow_html=True)
                chart = go.Figure(go.Bar(x=[baseline["degree_hours"], summary["degree_hours"]],
                                         y=["Baseline", label(scenario)], orientation="h",
                                         marker_color=["#a9bbc4", "#147a85"],
                                         hovertemplate="%{y}<br>%{x:.2f} °C·h<extra></extra>"))
                chart.update_xaxes(title="Exposure (°C·h)")
                st.plotly_chart(chart_style(chart, 245), width="stretch")
                st.caption(f"Baseline {baseline['duration_h']:g} h · selected {summary['duration_h']:g} h")

        files = selected_files(result, base, channel, reference)
        st.download_button("Download this run", zip_bytes(files),
                           file_name=f"{result['run_id']}_thermal_exposure.zip", mime="application/zip")
        with st.expander("Run details and limitations"):
            st.write(f"Run ID: `{result['run_id']}` · source: `{mode}` · channel: `{channel}` · seed: `2404` · step: `15 min`")
            st.write("This is simulated thermal exposure, not a spoilage or safety estimate. The product-lag channel is "
                     "assumed, not measured fish core. Proxy sources are nonfish temperature patterns. "
                     "The reference temperature is a comparison setting, not a legal cutoff.")
            st.dataframe(rows[["stage", "duration_h", "setpoint_c", "degree_hours"]], width="stretch", hide_index=True)
            events = event_rows(result)
            if events:
                st.dataframe(pd.DataFrame(events), width="stretch", hide_index=True)

with compare_tab:
    st.markdown('<div class="section-label">Configured scenarios</div>', unsafe_allow_html=True)
    st.caption("Same route, source, channel and comparison reference as your settings")
    try:
        data = saved_comparison(artifact_stamp("scenario_comparison"))
    except (FileNotFoundError, ValueError, OSError) as exc:
        st.error(f"Comparison data unavailable: {exc}")
    else:
        subset = data[(data["route"] == route) & (data["mode"] == mode) &
                      (data["channel"] == channel) & (data["reference_c"] == reference)].copy()
        if subset.empty:
            st.info("No saved comparisons match these settings.")
        else:
            subset["display"] = subset["scenario"].map(label)
            subset = subset.sort_values("delta_degree_hours")
            colors = ["#a9bbc4" if x == "baseline" else "#147a85" for x in subset["scenario"]]
            fig = go.Figure(go.Bar(x=subset["delta_degree_hours"], y=subset["display"], orientation="h",
                                   marker_color=colors, customdata=subset[["degree_hours", "duration_h"]],
                                   hovertemplate="%{y}<br>Additional %{x:.2f} °C·h<br>Total %{customdata[0]:.2f} °C·h"
                                                 "<br>Duration %{customdata[1]:.0f} h<extra></extra>"))
            fig.update_xaxes(title="Additional exposure vs baseline (°C·h)")
            st.plotly_chart(chart_style(fig, 430), width="stretch")
            st.caption("Comparison is within one hypothetical route. These are thermal indicators, not spoilage rankings.")
