# Model cards and allowed uses

## Trout expected TVC at nominal 4 °C

Artifact: `models/freshness/trout_tvc.joblib`. Training source: Zenodo 23600663 v4, CC BY 4.0. Input: storage age 0–6 days. Output: expected individual-assay TVC on the log10 CFU/g scale. Fitted to 17 development fillet assays (14 candidate original fish, six day cohorts), with one assay embargoed for candidate-fish overlap. Linear regression selected among five age-only candidates by grouped CV. This is an internally evaluated, single-study descriptive predictor. It cannot use gas sensors, cannot adjust temperature, cannot classify sensory freshness, cannot assess food safety, and cannot estimate a shipment spoilage probability. The corrected day-6 check is post-hoc and no external test exists. Use serialized joblib only from this trusted local repository; arbitrary joblib files can execute code when loaded.

## Smoked-catfish measured endpoint curves

Artifacts: `models/thermal/smoked_catfish_endpoints.json`, plus a peroxide-specific convenience JSON. Training source: Mendeley tvsw53j89z v1, CC BY 4.0. Input: one of seven measured endpoints, package treatment, the exact categorical reported temperature condition, and storage age 0–90 days. Output: piecewise-linear interpolation of observed treatment cell means in source-reported units. Six package × condition arms each contain two rows at days 30/60/90; day zero is shared baseline. No independent processing-run IDs or per-package temperature telemetry are available. These curves are descriptive, cannot interpolate across temperatures or predict fresh-fish endpoints, and do not convert to spoilage probabilities.

## DaFiF workbook exploration

Artifact: `models/exploration/dafif_workbooks.joblib`. Source: 63 official DaFiF workbooks (27,120 repeated readings). Median/IQR raw gas features were standardized, projected by PCA and clustered with k-means. There is no specimen-level target, so clusters are sensor-pattern groups, not freshness classes or validated model predictions.
