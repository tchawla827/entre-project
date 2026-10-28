# Dashboard handoff — focused interface

The dashboard was simplified after UI review. It now has two tabs: **Simulation** and **Compare scenarios**. The sidebar contains only route, scenario, temperature source, comparison reference, channel and **Run simulation**. The first tab shows three useful numbers, the temperature trace, physical-stage exposure, a matched baseline comparison for disruptions, and a download for the current run. The second tab shows saved Phase 4 scenario deltas for the sidebar selection. Run provenance and limitations are available in one collapsed detail panel. Research diagnostics, capability tables, Shapley analysis and Monte Carlo material remain in the reports and machine-readable artifacts rather than the main UI.

Launch from the repository root:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open `http://localhost:8501`. A fresh environment needs `pip install -r requirements.txt`; see the [README](../../README.md). The page uses `src.integration.execute` through `src/dashboard/service.py`, with no copied thermal calculations. A changed selection hides the old live result and download until rerun. The comparison chart reads schema-checked `results/integration/scenario_comparison.parquet`. The ZIP carries the current trace, stages, events, summary, complete API result, matched baseline and source provenance.

The live air synthetic road-failure result above a 2 °C comparison reference is **70.848039978 °C·h**, versus **15.045518285 °C·h** for baseline; the UI rounds these to **70.85** and **15.05**. Phase 4's 48 saved runs and original scientific results remain intact. [Numerical cross-checks](numerical_cross_checks.md) list both routes and all three source modes.

Playwright Chromium clicked through baseline, road failure, the scenario chart, sea/citrus-proxy/product-lag/4 °C, and a current-selection ZIP download. Five final screenshots are in [`figures/dashboard/redesign/`](../../figures/dashboard/redesign/). The downloaded JSON was parsed to verify route, mode, channel and reference. At 390 px mobile width the sidebar starts collapsed and document width is 390 px; no page errors occurred. [UI QA](ui_qa_results.md) records the run. The full suite passed **38 tests, 0 failures**; the eight warnings are existing dependency deprecations. Phase 4's `validate --all` passed after the redesign.

The sole persistent scope label states that this is simulation and fish spoilage is not calibrated. The plotted product-lag channel is assumed, proxy modes use nonfish temperature patterns, and the configured reference is a comparison value. No food-safety, shelf-life, regulatory or shipment-validity result is shown. Paired fresh-fish temperature/quality and independent Indian shipment outcomes are still missing; see the [scientific claim check](scientific_claims_check.md). The app remains local, with no public deployment.
