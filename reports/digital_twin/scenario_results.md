# Executed scenario results

Air-route scenario metrics are saved in [synthetic scenario_summary.csv](../../results/digital_twin/synthetic/scenario_summary.csv), stage metrics in [stage_exposure.csv](../../results/digital_twin/synthetic/stage_exposure.csv), event windows in [event_window_deltas.csv](../../results/digital_twin/synthetic/event_window_deltas.csv), and full traces/JSON alongside them. Values below are simulated **air degree-hours above 2 °C**; differences use the same configured route and baseline parameters. Changed-duration scenarios report both absolute increase and duration change.

| Scenario | Intervention | Duration h | Route °C·h | Increase °C·h |
|---|---|---:|---:|---:|
| Baseline | Well refrigerated | 47 | 15.0455 | 0 |
| Processing | +3 h processing | 50 | 18.0448 | 2.9993 |
| Storage | +3 °C cold-storage setpoint | 47 | 39.5658 | 24.5202 |
| Road | Refrigeration off for 2 h | 47 | 70.8480 | 55.8025 |
| Airport | +3 h handling and 0.75 h door opening | 50 | 52.3458 | 37.3003 |
| Flight | +5 °C setpoint for 4 h | 47 | 35.0454 | 19.9999 |
| Destination | +3 h unloading | 50 | 19.5401 | 4.4946 |
| Combined | Road + airport + flight | 50 | 128.0829 | 113.0374 |

The baseline 2 °C indicator is 15.431 °C·h under citrus residual replay and 15.874 °C·h under cold-room residual replay; combined is 128.069 and 127.830 °C·h, respectively. These changes show generator-shape sensitivity, not independent route replication. The separate hypothetical [sea-route summary](../../results/digital_twin/sea_synthetic/scenario_summary.csv) shows a 375 h baseline of 13.4640 °C·h, 34.7802 °C·h additional for an 8 h vessel setpoint excursion, and 126.9342 °C·h additional for combined disruption. Sea and air totals have different durations and configurations; compare their exposure rates and full time series, not a simplistic “better transport” claim.

Event-specific extra degree-hours are narrower than whole-route effects: road event interval 36.0940, airport door interval 14.3256, flight setpoint event interval 16.2336. Their remaining effects persist downstream during cooling. Road recovery is censored at the end of its stage; the airport door and flight event recover in approximately 2.98 and 1.73 h under the assumed 0.5 °C-from-setpoint criterion. Combined event-window comparisons include upstream state carryover and are explicitly flagged.
