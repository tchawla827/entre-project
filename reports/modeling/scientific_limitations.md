# Scientific limitations and Phase 3/4 handoff

- **Experimentally validated spoilage model:** none. No independent batch/study or Indian shipment test exists.
- **Internally evaluated observed-outcome model:** trout nominal-4 °C day-to-TVC regression. It predicts cohort mean tendency, not individual safety, sensory freshness or shipment spoilage probability. The corrected temporal check is post-hoc because an initial holdout was inspected before candidate-fish leakage was discovered.
- **Internally checked observed treatment curve:** smoked-catfish peroxide cell-mean interpolation. It describes a different processed product and cannot calibrate fresh-fish kinetics.
- **Unsupervised exploration:** DaFiF workbook clusters. They have no measured class labels or freshness accuracy.
- **Uncalibrated/literature-based simulation:** none was fitted in Phase 2. Future simulations must carry their assumptions visibly and remain separate from empirical models.
- **Blocked:** measured-label DaFiF/trout sensor classifier, calibrated fresh-finfish variable-temperature kinetics, calibrated spoilage probability, cross-study generalization, and Indian export field reliability.

For Phase 3, `src.models.inference` provides strictly bounded trout and smoked-catfish study-specific calls. The general trajectory call raises `UnsupportedCalibrationError`; the twin should catch this and show a blocked empirical-risk signal, while it may separately compute clearly named assumed thermal exposure. Phase 4 must not average an age-only TVC estimate with a thermal risk score or count storage age twice. Model provenance, domain and state must remain attached to any displayed output. Stage sensitivity of an assumed simulator is distinct from measured shipment reliability. New paired data requirements and unsent source requests are in `reports/data/blocked_data_requests.md`.
