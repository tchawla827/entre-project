# Executed hypothetical scenario experiments

The [v1 comparison table](../../results/integration/scenario_comparison.parquet) contains **192** route × mode × scenario × reference × channel rows from **48** full traces: two separately configured routes, three source modes, eight scenarios each, two temperature references (2 and 4 °C), and two channels (simulated equipment air and *assumed* product lag). The [run manifest](../../results/integration/run_manifest.json) records the request, run ID, trace path and provenance for each. Reference temperatures are scenario-comparison settings, not universal safety/legal limits. No measured fish-core or observed Indian shipment trace is present.

Synthetic air route, 2 °C reference (°C·h; deltas relative to same-route baseline):

| Scenario | Duration h | Air total | Air added | Assumed-product total |
|---|---:|---:|---:|---:|
| Baseline | 47 | 15.0455 | 0 | 11.8803 |
| Processing delay | 50 | 18.0448 | 2.9993 | 14.8379 |
| Cold-storage +3 °C | 47 | 39.5658 | 24.5202 | 37.1454 |
| Road refrigeration off | 47 | 70.8480 | 55.8025 | 66.7254 |
| Airport delay/door | 50 | 52.3458 | 37.3003 | 49.6660 |
| Flight excursion | 47 | 35.0454 | 19.9999 | 31.8128 |
| Destination delay | 50 | 19.5401 | 4.4946 | 16.1147 |
| Combined | 50 | 128.0829 | 113.0374 | 124.3761 |

The synthetic sea configuration has a 375 h baseline of **13.4640 °C·h** above 2 °C and a 378 h combined run of **140.3982 °C·h**, adding **126.9342**; its vessel-only 8 h setpoint excursion adds **34.7802**. The modeled air route's baseline indicator per hour is **0.3201 °C**, versus **0.0359 °C** in the modeled sea route, reflecting different assumed setpoints/durations. It does **not** imply sea carriage is biologically safer or that chilled fish remains viable for 14 days. Different-duration scenarios have both total and per-route-hour columns; baseline-temperature exposure during added hours is part of the total difference. The proposed route is not evidenced by MPEDA's separate aggregate marginals.

Shape-replay sensitivity of 2 °C simulated-air totals: air baseline **15.4315** with citrus residuals and **15.8737** with generic cold-room residuals; sea baseline **13.0315** and **14.2680**. Citrus package-position and cold-room measurements are nonfish proxy shapes offset to synthetic setpoints, not actual route-air logs. Phase 3's reference air values were reproduced exactly under the identical synthetic settings. See [air chart](../../figures/integration/air_scenario_channels.png), [sea chart](../../figures/integration/sea_scenario_channels.png), and [reference comparison](../../figures/integration/air_reference_comparison.png). All plotted series are hypothetical thermal indicators.
