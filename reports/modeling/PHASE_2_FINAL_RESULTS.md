# Phase 2 — complete consolidated results

**Project:** Digital Twin of Indian Fisheries Export Cold Chain for Spoilage Risk Prediction  
**Run date:** 27 October 2026  
**Scope:** Executed modeling layer and its inference contract. The full stage-by-stage twin and dashboard are later phases.  
**Overall finding:** The curated data support a small, internally evaluated trout TVC regression, descriptive smoked-catfish treatment curves, and unsupervised DaFiF sensor exploration. They do **not** support a specimen-validated gas-sensor freshness classifier, fresh-finfish variable-temperature spoilage kinetics, calibrated spoilage probabilities, or independent Indian-export reliability claims.

## 1. What was inspected and executed

Before fitting, the Phase 2 prompt, README, Phase 1 final handoff, scientific sufficiency and quality reports, blocked-data requests, data dictionary, source registry, join and label policies, curated schemas and actual Parquet rows were inspected. The modeling command `python -m src.models.cli all` ran the source/target audit, candidate comparison and grouped cross-validation, trout final fit and post-hoc check, DaFiF clustering, smoked-catfish cell-curve construction and diagnostic checks. Results, per-fold predictions, split manifest, source hashes, environment, figures and artifacts were saved. A second-round challenger command ran separately. The modeling and Phase 1 test suites passed **10 tests**. A local joblib/NumPy deprecation warning appeared twice; no test failed. The `evaluate`, `validate`, and inference smoke commands also ran successfully.

Reproduce in this workspace:

```powershell
.venv/Scripts/python.exe -m src.models.cli all
.venv/Scripts/python.exe -m src.models.improvement
.venv/Scripts/python.exe -m src.models.cli evaluate
.venv/Scripts/python.exe -m src.models.cli validate
.venv/Scripts/python.exe -m pytest tests/models tests/data_pipeline -q
```

Dependencies are pinned in `requirements.txt`; modeling protocol parameters are in `configs/models/protocol.yaml`. The executed environment was Python 3.12.16, NumPy 2.5.4, pandas 3.1.0, SciPy 1.16.2, scikit-learn 1.7.2, Matplotlib 3.10.7, seed 47. Dataset, protocol and artifact SHA-256 hashes are in `reports/modeling/environment_and_data.json`.

## 2. Data, linkage and readiness

| Dataset or task | Actual available observations and independent units | Decision |
|---|---|---|
| DaFiF gas sensors | 27,120 readings in 63 official workbooks; individual fish identities unavailable. | **READY** for workbook-level descriptive sensor exploration; **BLOCKED** for measured-label supervised classification. |
| DaFiF expert sensory scores | 774 criterion scores in 129 species/day/session assessment groups on fish other than those with sensor readings. One source score is zero despite a stated 1–9 scale. | **BLOCKED** as specimen-level sensor targets. |
| Trout sensors | 25,200 repeated readings in 210 sessions on 59 longitudinal fillets. Embedded TVC/class fields are repeated day-level proxies. | **BLOCKED** for measured-label sensor classification. |
| Trout microbiology | 21 individually measured TVC assays across seven days at one nominal 4 °C storage condition. Filename pattern suggests 17 original fish at most, pending author confirmation; none of the assays has a direct sensor-fillet link. | **CONDITIONALLY READY** for a single-study, day-only TVC regression. |
| Smoked catfish | 336 measured rows across seven outcomes; 48 rows per outcome. For each outcome, 12 day-zero rows represent a shared baseline and 36 postbaseline rows cover six package × condition arms, two replicates per cell at days 30/60/90. Processing-run IDs unavailable. | **CONDITIONALLY READY** for descriptive treatment-cell curves, **BLOCKED** for variable-temperature kinetics or transfer to fresh fish. |
| MPEDA / thermal proxies | 10,788 annual export-statistics records; 31,140 citrus reefer proxy rows; 1,411,515 generic cold-room proxy rows. | **READY** for context or assumed simulation inputs; **BLOCKED** as fish-quality labels or Indian shipment validation. |
| Paired Indian export shipments | Zero shipment/lot-linked temperature histories with measured fish-quality outcomes. | **BLOCKED** for field validation. |

**Source reconciliation.** The DaFiF paper states 9,041 rows per fish category, 27,123 in total. The 63 official workbooks contain 9,020 Mackerel, 9,029 Tilapia and 9,071 Tuna rows, or 27,120 in total. Thus there is a three-row *net* discrepancy with larger category-level differences. No rows were invented to make the counts agree. In the local `combined_dataset.csv`, 2,298 session labels disagree with official source-folder metadata: 1,878 Day-1 rows and 420 rows from a Tongkol file named for Session 2 but located in the official Session-1 folder. The curated table follows the official folder, flags the filename conflict, and preserves the raw records. None of those disagreements was silently overwritten or discarded.

Sensory freshness, microbial counts, peroxide oxidation, safety and regulatory compliance are different endpoints. None was substituted for another. The trout sensing-chamber temperatures are measurement conditions, not measured storage or fish-core temperatures. Smoked-catfish temperature treatments are reported ranges (refrigerated 4–5 °C; ambient 25–30 °C), not per-package logger histories.

## 3. Trout measured-TVC regression

**Target and input.** The target is measured TVC in log10 CFU/g for individually assayed refrigerated rainbow-trout fillets. The only predictor is storage age in days. The model has no paired gas readings, direct product-temperature trajectory, species variation or shipment features. It is not a freshness classifier or a food-safety decision rule.

**Split and selection.** The intended final temporal check was day 6. A filename audit found that candidate original fish 18 appears at both development day 5 and check day 6, so the development assay for that fish was embargoed. The resulting development set has 17 assays in six day cohorts from 14 candidate original fish; day 6 has three assays from three candidate original fish. Each leave-one-day-out development fold also excludes training assays sharing candidate original-fish IDs with its held-out day. The inferred fish-ID mapping is unconfirmed. Five prebounded candidates were compared with the same grouped folds; the simplest model within 0.05 log units of the best CV MAE was selected.

| Model | Grouped CV MAE | Grouped CV RMSE | CV bias |
|---|---:|---:|---:|
| **Linear regression (selected)** | **0.539** | **0.727** | 0.025 |
| Quadratic ridge, alpha 10 | 0.697 | 0.772 | 0.003 |
| Quadratic ridge, alpha 1 | 0.742 | 0.908 | −0.060 |
| Quadratic ridge, alpha 0.1 | 0.754 | 0.995 | −0.111 |
| Mean baseline | 0.972 | 1.250 | 0.021 |

Units for all errors are log10 CFU/g. A 10,000-draw bootstrap resampling the **six held-out day groups**, not individual assays, gives a 95% percentile interval for linear CV MAE of **0.233–0.936**. The paired baseline-minus-linear MAE interval is **−0.267 to 1.151**, crossing zero: the apparent improvement is not robustly established across day cohorts. These intervals do not quantify new-study uncertainty. The 90th percentile of development out-of-fold absolute errors is 1.345 log units and is **not** a calibrated prediction interval.

**Important protocol failure.** An initial day-6 result was inspected before the candidate-original-fish overlap was discovered. Consequently there is **no untouched final test** in this dataset. After the embargo and corrected grouped CV, the day-6 check is explicitly **post-hoc**: MAE 0.283, RMSE 0.301, bias −0.283 on three assays; the development-mean baseline MAE there was 2.393. All three predicted values were 7.574 log10 CFU/g versus observed values 7.881, 7.968 and 7.724. These are diagnostics, not a fresh final generalization estimate. An external independent study is unavailable.

**Error mode and stopping decision.** The measured day mean drops from day 3 to day 4, then rises sharply at day 5. The selected age-only line overpredicts day 4 and underpredicts day 5 in grouped CV. Quadratic ridge did not improve overall MAE. With only six development day cohorts, a more flexible model could memorize the study curve but would not establish a temperature response or cross-study generalization. Tuning stopped at the documented five-candidate comparison.

**Artifact:** `models/freshness/trout_tvc.joblib`. This local joblib file is trusted-project serialization; do not load an arbitrary replacement. Bounded inference: `src.models.inference.predict_trout_tvc(3)` returns an expected TVC value and explicit study scope for ages 0–6 days at nominal 4 °C.

## 4. Smoked-catfish measured-outcome curves

All seven measured outcomes were preserved as **separate** package/condition cell-mean curves: coliform count, mesophilic bacteria, mould, peroxide value, water activity, yeast and pH. The fitted representation is piecewise-linear interpolation within each observed arm. For adjacent observed days (t_i,t_{i+1}), package (p), condition (c) and endpoint (e):

\[\hat q_{e,p,c}(t)=\bar q_{e,p,c}(t_i)+\frac{t-t_i}{t_{i+1}-t_i}\left[\bar q_{e,p,c}(t_{i+1})-\bar q_{e,p,c}(t_i)\right].\]

The diagnostic withholds each arm's **day-60 cell mean** and interpolates it from days 30 and 90, comparing it with a day-30 carry-forward baseline. These are six within-study treatment-cell checks per endpoint. They use a later observation and are neither prospective forecasting nor an independent processing-run test. Errors retain each source endpoint's own units and must not be compared across endpoints.

| Measured endpoint | Interpolation MAE | Interpolation RMSE | Day-30 carry-forward MAE |
|---|---:|---:|---:|
| Coliform count | 1,146.917 | 1,730.482 | **883.583** |
| Mesophilic bacteria | **1,791.792** | 2,547.096 | 2,918.000 |
| Mould | **47.417** | 60.675 | 80.833 |
| Peroxide value | **2.595** | 4.688 | 3.545 |
| Water activity | **0.001917** | 0.002336 | 0.007667 |
| Yeast | **208.750** | 371.053 | 211.667 |
| pH | **0.055** | 0.061 | 0.295 |

Peroxide interpolation had bias +2.455 source units; its largest individual cell error was an **11.125-unit overprediction** for LDPE at ambient treatment, reflecting strong late curvature. Coliform interpolation is worse than its simple baseline. There is no justified universal winner across endpoints, no independent-run error interval, and no calibrated spoilage threshold or probability.

The published conditions are only two broad temperature bands. A continuous temperature-rate relation (including Q10 or Arrhenius), thermal lag, non-isothermal integration and variable-temperature predictive validity cannot be estimated from them. The curves apply to **smoked *Clarias gariepinus*** only; they cannot stand in for fresh finfish. `predict_smoked_catfish_endpoint("pH", "Paper", "Refrigerated", 60)` is a bounded categorical-treatment lookup/interpolation, not a dynamic shipment forecast. Artifact: `models/thermal/smoked_catfish_endpoints.json`; peroxide convenience artifact: `models/thermal/smoked_catfish_peroxide.json`.

## 5. DaFiF unsupervised sensor exploration

The 27,120 repeated readings were reduced to **63 workbook-level** feature vectors using the median and interquartile range of the two raw gas channels. Standardization, PCA and k-means were applied to those workbook vectors. Among k=2–5, k=3 gave the highest silhouette, **0.305**. PCA components 1 and 2 explain **45.4%** and **29.0%** of standardized feature variation. Cluster/species adjusted Rand index was −0.024 for k=3; this is only a descriptive diagnostic. These are sensor-pattern clusters, **not** measured freshness states. Biological fish IDs are absent, and there is no independent biological-sample count to justify a spoilage accuracy estimate. Artifact: `models/exploration/dafif_workbooks.joblib`.

## 6. Validation, calibration and blocked capabilities

| Capability | Final status and evidence |
|---|---|
| Empirically validated specimen-level freshness classifier | **BLOCKED.** DaFiF sensory outcomes and trout TVC assays were measured on fish other than the sensor cohort. No Gradient Boosting classifier was fitted to ecological day labels. |
| Internal measured-outcome trout model | **CONDITIONALLY READY** for age-only, nominal-4 °C study-specific exploration. Grouped CV exists; an untouched final and external study test do not. |
| Smoked-catfish treatment descriptions | **CONDITIONALLY READY** for bounded, categorical within-study interpolation of measured endpoints. Processing-run independence, exact temperatures and dynamic-temperature validation are missing. |
| Fresh-finfish temperature-driven quality trajectory | **BLOCKED.** No fresh-fish multi-temperature replicate quality observations with product temperatures and batch IDs. |
| Calibrated spoilage probability and probability metrics | **BLOCKED.** No defensible matched binary outcome. F1, confusion matrix, ROC-AUC, Brier score and probability calibration are unavailable, not zero. |
| Scenario-driven Phase 3 twin | **CONDITIONALLY READY** for explicitly assumed thermal exposure calculations using proxy traces and bounded interfaces; those outputs would be simulated, not empirically calibrated fish spoilage risk. |
| Independent real Indian-export predictive reliability | **BLOCKED.** Zero paired shipment logger/quality records. |

The general `predict_quality_trajectory(species, product_state, initial_quality, timestamps, temperature_c, endpoint)` inference contract deliberately raises `UnsupportedCalibrationError`. It will require exact product-core/surface temperature histories, initial and follow-up quality outcomes with units and assay methods, scientific species and state, packaging, independent fish/lot/batch IDs, multiple controlled temperatures, and held-out dynamic-temperature experiments. Ambient/container air cannot silently replace product temperature. The Phase 3 twin may show an **assumed** exposure signal separately, but it must not average that signal with the trout age model or describe it as a validated spoilage probability.

## 7. Files and runnable inference

| Purpose | File |
|---|---|
| Modeling code and CLI | `src/models/cli.py` |
| Bounded inference and refusal contract | `src/models/inference.py` |
| Protocol | `configs/models/protocol.yaml` |
| Trout fitted model | `models/freshness/trout_tvc.joblib` |
| All smoked-catfish measured-outcome curves | `models/thermal/smoked_catfish_endpoints.json` |
| Peroxide convenience curve | `models/thermal/smoked_catfish_peroxide.json` |
| DaFiF descriptive clustering | `models/exploration/dafif_workbooks.joblib` |
| Split, fold predictions, candidate comparison, all endpoint checks | `reports/modeling/*.csv` |
| Audit, metrics, environment and hashes | `reports/modeling/*.json` |
| Plots | `figures/modeling/*.png` |
| Automated contract tests | `tests/models/test_model_contract.py` |

```python
from src.models.inference import predict_trout_tvc, predict_smoked_catfish_endpoint

print(predict_trout_tvc(3))
print(predict_smoked_catfish_endpoint("pH", "Paper", "Refrigerated", 60))
```

The Phase 1 acquisition and quality sources remain in `reports/data/`, with field-data specifications and **unsent** research-request drafts in `reports/data/blocked_data_requests.md`. These missing empirical measurements are the concrete next step for an independently testable fresh-fish/Indian-export model. No source was contacted, no shipment outcomes were invented, and no classifier or thermal rate was presented as validated without measured pairing.

## 8. Second-round improvement experiments and decision

After the first report, a bounded challenger experiment tested five additional trout trends under the **same six leave-one-day-out development folds and candidate-fish embargo**. The exposed day-6 check was not used to fit, rank or choose challengers. Theil–Sen robust regression had the lowest nominal CV MAE, 0.501 versus the saved linear model's 0.539 log10 CFU/g, and RMSE 0.650 versus 0.727. It won four of six day folds, but a paired six-day bootstrap interval for linear-minus-Theil–Sen MAE was **−0.066 to 0.234**, crossing zero. Most of its gain came from one late cohort. Huber and ridge changes were smaller; isotonic and spline fits were worse.

| Second-round trout method | Grouped CV MAE | Grouped CV RMSE |
|---|---:|---:|
| Theil–Sen | 0.501 | 0.650 |
| Huber | 0.530 | 0.716 |
| Ridge linear, alpha 1 | 0.535 | 0.723 |
| **Saved linear model** | **0.539** | **0.727** |
| Isotonic day means | 0.724 | 0.909 |
| Quadratic spline ridge | 0.881 | 1.147 |

A stricter **forward-only** development check trained on earlier days and predicted each of days 2–5. Mean day-level MAE was 0.722 for Theil–Sen, 0.786 for linear and 0.844 for Huber. Theil–Sen won just one of the four forward day folds; its paired bootstrap advantage interval also crossed zero (−0.132 to 0.338). These four folds do not establish a more general forecasting method. The saved linear artifact was therefore **not replaced**; its SHA-256 matched the pre-experiment artifact manifest after the challenger run.

For smoked-catfish cells, second-round diagnostics compared the existing linear interpolation, day-30 carry-forward, shape-preserving cubic interpolation (PCHIP) and a quadratic through the day-0/30/90 anchors, always withholding day 60. Peroxide PCHIP reduced six-cell MAE from **2.595 to 1.124** source units and RMSE from **4.688 to 1.556**, but won only three of six arms. Most of its gain was correcting the LDPE-ambient error; a paired six-arm bootstrap interval for linear-minus-PCHIP MAE was **−0.076 to 4.195**, crossing zero. It was worse than linear for mould, water activity and pH, and the coliform carry-forward baseline still beat all three interpolation methods. Peroxide PCHIP is an exploratory within-study improvement, **not** an independent-run or variable-temperature validation, so the saved categorical curves remain simple linear interpolation.

| Endpoint | Existing linear MAE | PCHIP MAE | Quadratic MAE | Day-30 carry MAE |
|---|---:|---:|---:|---:|
| Coliform count | 1,146.917 | 1,201.541 | 1,329.417 | **883.583** |
| Mesophilic bacteria | **1,791.792** | 2,718.080 | 3,290.556 | 2,918.000 |
| Mould | **47.417** | 47.833 | 52.778 | 80.833 |
| Peroxide value | 2.595 | **1.124** | 1.288 | 3.545 |
| Water activity | **0.001917** | 0.001977 | 0.002833 | 0.007667 |
| Yeast | 208.750 | **183.025** | 201.111 | 211.667 |
| pH | **0.055** | 0.063 | 0.068 | 0.295 |

For a genuinely forward peroxide check, using only days 0/30/60 to predict day 90 across six arms, a quadratic had MAE **3.863**, last-interval linear extrapolation **5.189**, and carrying day 60 forward **8.456** source units. The quadratic still missed LDPE ambient by **13.525** units; there are no independent run IDs or additional timepoints to validate such extrapolation. No day-90 forecast artifact was promoted.

The executed challenger predictions and fold/cell comparisons are `reports/modeling/improvement_trout_cv_predictions.csv`, `improvement_trout_comparison.csv`, `improvement_trout_forward_folds.csv`, `improvement_catfish_cell_predictions.csv`, `improvement_catfish_comparison.csv`, and `improvement_catfish_forward_day90.csv`. Paired bootstrap summaries are saved as `improvement_trout_bootstrap.json`, `improvement_trout_forward_bootstrap.json`, and `improvement_catfish_peroxide_bootstrap.json`. The concrete route to reliable gains is independent biological/batch data and paired fish temperature–quality measurements, not a larger search over these same few cohorts.
