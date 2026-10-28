# Phase 2 handoff

Rebuild with `.venv/Scripts/python.exe -m src.models.cli all`, then `.venv/Scripts/python.exe -m pytest tests/models tests/data_pipeline -q`. See `validation_results.md` for measured metrics, `modeling_readiness.md` for evidence gates and `leakage_audit.md` for the invalidated first trout holdout.

Artifacts: `models/freshness/trout_tvc.joblib` (internally evaluated age-only regression), `models/thermal/smoked_catfish_endpoints.json` (all seven measured smoked-product categorical endpoint curves), `models/thermal/smoked_catfish_peroxide.json` (peroxide convenience artifact), and `models/exploration/dafif_workbooks.joblib` (unsupervised workbook clusters). The trout and smoked-catfish branches have direct quality endpoint measurements, but neither yields a calibrated spoilage probability. JSON/CSV predictions and comparisons, source hashes, environment and figures are under `reports/modeling/` and `figures/modeling/`.

Example:

```python
from src.models.inference import predict_trout_tvc, predict_smoked_catfish_peroxide
print(predict_trout_tvc(3))
print(predict_smoked_catfish_peroxide("Paper", "Refrigerated", 60))
```

No Gradient Boosting classifier was trained: its required specimen-matched target is absent. No fresh-fish thermal rate or real Indian export shipment model was calibrated. These capabilities require the exact paired measurements described in the Phase 1 blocked-data request before a deployment or publication-grade reliability claim.
