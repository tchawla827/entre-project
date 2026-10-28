## Slide 1

The title is the original research objective. What has been delivered is a thermal-exposure research prototype, not a calibrated fish-spoilage predictor. The examples are hypothetical configured routes. This distinction will be explained on slide 11.

Evidence / sources:
COMPLETE_README.MD
reports/integration/final_handoff.md

## Slide 2

Walk through a shipment in everyday language: landing and icing, packing, chilled holding, road transfer, airport handling, international transit and arrival inspection. These are stages of the configured example, not a reconstructed observed shipment. The system also includes a conditional hypothetical sea stress configuration. MPEDA supports Indian export context but its item, market and port tables are separate marginals; they do not prove this specific route.

Evidence / sources:
configs/digital_twin/experiment.yaml
reports/digital_twin/final_handoff.md
https://mpeda.gov.in/?page_id=438

## Slide 3

Warmer conditions and longer exposure can affect fish quality, but the effect depends on species, product state, initial quality and biological response. This project tests thermal consequences of plausible disruptions. It has not measured these failure frequencies on Indian shipments or quantified resulting spoilage/safety outcomes.

Evidence / sources:
reports/digital_twin/final_handoff.md
configs/digital_twin/experiment.yaml

## Slide 4

The current answerable research question is about modeled thermal exposure and stage sensitivity. The longer-term objective is biological prediction. A sensor model alone cannot learn a new temperature response, and thermal exposure alone cannot be presented as spoilage probability.

Evidence / sources:
reports/digital_twin/final_handoff.md
reports/integration/final_handoff.md

## Slide 5

This is an actual saved screenshot of the implemented Streamlit dashboard, not a mock-up. Users choose route, scenario, temperature source, reference and channel, run a simulation, compare saved scenarios and download results. The simulator is a configured digital-twin prototype, not a live data-connected replica of an observed shipment. The visible product-lag option is assumed, not measured fish-core temperature.

Evidence / sources:
app.py
reports/dashboard/final_handoff.md
figures/dashboard/redesign/02_road_failure_desktop.png

## Slide 6

Phase 1 curated 27,120 DaFiF readings from 63 workbooks, 774 separate sensory criterion scores, 25,200 trout sensor readings and 21 individual trout TVC assays. Sensor and quality cohorts are different fish; repeated readings are not independent fish. MPEDA has 10,788 annual marginal statistics rows. Proxy tables have 31,140 citrus and 1,411,515 cold-room rows. A separate smoked-catfish study supplies 336 long-format measured endpoint rows; it supports only within-study treatment curves, not fresh-fish kinetics. The model branches are deliberately not fused into a biologically invalid target table. DaFiF source counts and 2,298 local session-label conflicts are documented in the data-quality report; use counted workbook rows, not published descriptions, for totals.

Evidence / sources:
reports/data/data_quality_report.md
reports/data/scientific_sufficiency_report.md
https://data.mendeley.com/datasets/vx4ptwk3pb/1
https://zenodo.org/records/23600663
https://mpeda.gov.in/?page_id=438
https://data.mendeley.com/datasets/mvr7m6mcgp/2
https://zenodo.org/records/15130001

## Slide 7

The simulator carries temperature state through stages using an illustrative first-order response: nominal air lag 0.75 h and assumed product lag 1.5 h. The degree-hour indicator integrates max(temperature minus reference, 0) over time. The simple constant-temperature example gives (5 minus 2) °C × 2 hours = 6 °C·h. This is a teaching example, not a measured shipment or a spoilage threshold. References 2 °C and 4 °C are comparisons, not universal legal or spoilage cutoffs. The current model does not translate degree-hours to biological deterioration. The stable Python API is src.integration.execute; the UI delegates to it rather than implementing separate calculations.

Evidence / sources:
reports/digital_twin/final_handoff.md
reports/integration/architecture_and_contracts.md
src/digital_twin/exposure.py

## Slide 8

The configured air baseline lasts 47 h: landing/icing 3, processing 5, storage 12, road 5, airport 6, flight 12 and destination 4 h. Eight scenarios include baseline, processing delay, storage setpoint, road failure, airport delay/door, flight excursion, destination delay and combined. Combined is 50 h because the airport stage gains 3 h. The sea configuration is a conditional 375 h software stress case with a 14-day voyage and no evidence that chilled fish remains viable. Phase 4 ran 48 route/mode/scenario simulations: 2 routes × 3 modes × 8 scenarios. Only the air synthetic example is foregrounded here to avoid conflating distinct domains.

Evidence / sources:
configs/digital_twin/experiment.yaml
configs/digital_twin/sea_route.yaml
reports/integration/final_handoff.md

## Slide 9

All plotted values are additional simulated-air degree-hours above 2 °C relative to the same synthetic-air route baseline. Road 55.8025, airport 37.3003, storage 24.5202, flight 19.9999, destination 4.4946, processing 2.9993. Baseline total is 15.0455 °C·h; road-failure total is 70.8480. The combined case adds 113.0374 and totals 128.0829 but is excluded from this single-disruption chart. Airport and delay cases have longer durations; differences include added hours. This ranks intervention effects, not exposure physically occurring inside each stage. These indicators are neither spoilage percentages nor causal field estimates.

Evidence / sources:
results/integration/scenario_comparison.parquet
reports/integration/scenario_experiments.md

## Slide 10

The paired assumption exercise varies stage durations ×0.85–1.15, setpoints ±0.5 °C, ambient ±3 °C, air response 0.4–1.2 h, assumed product response 0.75–3 h and event duration ×0.75–1.25. Road is the largest single intervention in 197/200 air draws at 2 °C, 193/200 at 4 °C, and 100/100 sea draws for either reference. Those counts are sensitivity within assumed ranges, not confidence levels or real-world probabilities. Under equal 2 h/+3 °C events, airport and flight each add 6.0 °C·h above 2 °C, while storage adds 2.9018. At 4 °C, the dominant standardized stage changes to destination. The engineering suite also checked deterministic replay, stage-to-route conservation, trace reload, Shapley conservation and numerical step-size sensitivity; the full rebuild passed 41 tests. None of this validates fish biology or field performance.

Evidence / sources:
reports/integration/robustness_and_uncertainty.md
reports/integration/stage_ranking_and_attribution.md
reports/setup/final_handoff.md

## Slide 11

There is no validated freshness classifier, fish-specific variable-temperature deterioration model, spoilage probability, shelf-life forecast, food-safety decision or regulatory-compliance engine. The planned Gradient Boosting classifier was not trained because the specimen-level labels are unavailable; saying only “unvalidated” could imply a fitted classifier exists. Phase 2 did produce a separate age-only trout TVC linear model (17 development assays, grouped-CV MAE 0.539 log10 CFU/g). Its three-assay temporal check is post-hoc after a candidate fish overlap was discovered, so no untouched final test exists. Smoked-catfish treatment curves and DaFiF unsupervised clusters also remain separate diagnostics. These are not coupled into the route to claim fish spoilage. The API returns prediction null/NOT_CALIBRATED and explicitly refuses unsupported biological targets.

Evidence / sources:
reports/modeling/PHASE_2_FINAL_RESULTS.md
reports/integration/model_capabilities_and_blockers.md
reports/data/scientific_sufficiency_report.md

## Slide 12

The delivered contribution is an auditable data pipeline, evidence-scoped study diagnostics, configurable thermal simulation, integrated experiment service and actual dashboard. The immediate research upgrade is linked specimen/lot/logger/assay data at multiple product temperatures and independent exporter/route/later-shipment holdouts. A pilot must determine sample size by independent biological lots and outcome rate, not sensor-row count. The dashboard is already delivered; the next task is biological calibration and field evaluation. Publication is a future research step, not an accepted or submitted paper claim. Full information, provenance, metrics, run commands and limitations are in COMPLETE_README.MD.

Evidence / sources:
COMPLETE_README.MD
configs/integration/field_linkage_schema.yaml
reports/data/blocked_data_requests.md