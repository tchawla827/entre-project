# Executed model evaluation

Run `python -m src.models.cli all` from the repository root with the pinned environment. Experiment files and source hashes are in this directory; figures are in `figures/modeling/`.

## Rainbow trout individual TVC

Target: directly assayed TVC, log10 CFU/g. Predictor: storage age in days only. The five candidates were mean baseline, linear regression, and quadratic ridge at alpha 0.1, 1 and 10. Each development fold holds out one entire day and excludes any training assay sharing its **candidate** original-fish ID with that fold. The filename mapping has not been verified by the authors. Final fitting uses 17 assays in six day cohorts from 14 candidate original fish; one assay was embargoed because its candidate fish occurs in the day-6 cohort. No gas sensor or measurement-chamber temperature appears in the model.

| Candidate | Grouped development CV MAE | RMSE |
|---|---:|---:|
| Linear | 0.539 | 0.727 |
| Quadratic ridge 10 | See `trout_model_comparison.csv` | See CSV |
| Mean | 0.972 | 1.250 |

The linear model was chosen by the predeclared lowest-CV-MAE rule with a 0.05 log-unit simplicity margin. The first run exposed the day-6 test before candidate-original-fish overlap was discovered; that protocol was invalidated. The corrected day-6 check is **post-hoc**, not an untouched final test: three assays/three candidate original fish, MAE 0.283, RMSE 0.301, bias −0.283; the development-mean baseline MAE was 2.393. One day cohort is too small to estimate a meaningful independent-day confidence interval. The 90th percentile of development out-of-fold absolute errors is 1.345 log units, but this is not a calibrated prediction interval; apparent day-6 coverage 3/3 is not evidence of calibration. Errors peak at development days 4 and 5, where the measured mean falls and then rises sharply. This curve may reflect biological/batch variability; an age-only trend cannot capture it. There is no external study validation or classifier probability calibration.

Day-group bootstrap over the six development folds gives a wide 95% percentile interval for linear-model MAE of 0.233–0.936 log units. The paired baseline-minus-linear MAE interval is −0.267 to 1.151, crossing zero; therefore the apparent CV improvement is **not robustly established across independent day cohorts**. These intervals describe this single study's six folds, not future-study uncertainty.

## Smoked-catfish measured endpoints

All seven measured outcomes are preserved as separate categorical-treatment curves in `models/thermal/smoked_catfish_endpoints.json`. Their six-cell day-60 checks are in `smoked_catfish_all_endpoint_metrics.csv`. Interpolation is worse than day-30 carry-forward for coliform count (MAE 1,147 versus 884 source units), so these curves are descriptive and cannot be selected as general forecast models. Peroxide is the illustrative oxidative-quality endpoint below.

All 48 peroxide observations are measured on **smoked** catfish. The 12 day-zero rows are a shared baseline and do not count as independent replicate treatments; 36 postbaseline observations cover six package × categorical-temperature arms at days 30/60/90. The saved curves linearly interpolate each treatment's cell means and are bounded to days 0–90 and the exact reported conditions. The day-60 diagnostic withheld that entire cell within each arm and interpolated from day 30 and day 90: six cell means, MAE 2.595 and RMSE 4.688 source units; day-30 carry-forward baseline MAE 3.545 and RMSE 5.205. LDPE ambient is the main failure (11.125-unit overprediction), showing that simple interpolation misses nonlinear oxidation. This is a within-study interpolation check using a later measurement; it is **not** prospective forecasting or an independent processing-run test. Two broad treatment bands do not identify an Arrhenius or Q10 rate law. There is no uncertainty estimate for between-run variation because run IDs are absent.

## DaFiF unsupervised exploration

The 27,120 readings were summarized to 63 workbook-level median/IQR feature vectors. PCA and k-means were fitted without freshness labels. Three clusters maximized silhouette among k=2–5 (silhouette 0.305); the first two PCs explain 45.4% and 29.0% of standardized workbook feature variation. These clusters are descriptive sensor states and carry **no spoilage classification accuracy**. Species association in `dafif_cluster_trials.csv` is diagnostic only.

No gradient boosting classifier or spoilage probability model was fitted: no sensor record has a specimen-matched measured quality label. No probability calibration, ROC-AUC, F1, false-negative rate or confusion matrix exists for a scientifically valid freshness classifier. Sensor-only, sensor+age, and weak cohort-label ablations would estimate proxy-label replication, not fish-level generalization, so they were not presented as validated ML.
