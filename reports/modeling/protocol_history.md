# Protocol change log

1. Initial run: temporal day-6 holdout; leave-one-day-out development CV, **without** candidate-original-fish embargo. The linear model had CV MAE 0.606 log10 CFU/g. Its inspected day-6 MAE was 0.116. Filename inspection then revealed that `F4F18` at development day 5 and `F1F18` at test day 6 may derive from the same original fish. The original final-test claim was invalidated and is retained here only as a diagnostic record.
2. Corrected run: embargo `F4F18` from fitting, and embargo candidate-fish overlaps within every CV fold. The resulting 17-assay/14-candidate-fish development CV selects linear regression with MAE 0.539. The day-6 three-assay check has MAE 0.283, explicitly **post-hoc** because day-6 outcomes were already seen. There is no replacement untouched source in the workspace.

The candidate original-fish mapping is inferred from filename structure, not confirmed by the data authors. The conservative exclusion prevents a plausible leakage route; it does not prove that the remaining fillets are independent batches. New assayed trout from a separate study/batch are needed for a clean prospective test.
