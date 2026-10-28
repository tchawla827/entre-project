# Probability and uncertainty calibration

There is no scientifically defensible specimen-matched binary freshness or spoilage classifier. Therefore no predicted class probabilities, Brier score, calibration curve, precision/recall, ROC-AUC or probability-calibration artifact were produced. The trout outcome is a continuous laboratory TVC count, and the smoked-catfish curves are continuous measured endpoints; no threshold was chosen from these data to create a proxy class.

The trout day-group bootstrap interval and out-of-fold absolute-error percentile in `trout_cv_day_bootstrap.json` are diagnostic uncertainty summaries, not calibrated prediction intervals. Six day groups from one study cannot establish coverage for a new study or shipment. Catfish replicate SDs are saved in `smoked_catfish_peroxide_cells.csv`, but unknown processing-run clustering prevents an independent-run parameter interval. No thermal model exposes a calibrated observed-spoilage probability.
