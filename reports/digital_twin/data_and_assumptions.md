# Data and assumptions

The [Phase 1 handoff](../data/final_handoff.md), [quality report](../data/data_quality_report.md), [sufficiency report](../data/scientific_sufficiency_report.md), [dictionary](../../metadata/data_dictionary.csv), and [dataset registry](../../metadata/dataset_registry.csv) define source scope. Phase 2's [handoff](../modeling/final_handoff.md) confirms no fresh-finfish temperature–quality calibration. The exact local source counts and MPEDA marginals are in [data_audit.json](data_audit.json). MPEDA source: <https://mpeda.gov.in/?page_id=438>; it supplies aggregate context only. Its item, market, and port totals cannot be joined into individual routes. The sea configuration's Cochin SEZ category does not establish a seaport departure or vessel voyage.

| Input | Assumption type and scope | Nominal | Tested range |
|---|---|---:|---:|
| Air-stage response time | Illustrative equipment dynamics; no fitted coefficient | 0.75 h | 0.4–1.2 h |
| Door-open response | Illustrative faster air exchange | min(air lag, 0.2 h) | Varies with air lag |
| Estimated-product response | Illustrative lag, **not fish core** | 1.5 h | 0.75–3 h |
| Initial air/product | Illustrative starting state | 1.5/1 °C | Fixed in main Monte Carlo |
| Ambient | Stage-specific hypothetical 22–30 °C | Configured per stage | ±3 °C |
| Stage duration | Hypothetical air or sea route | Configured per stage | ×0.85–1.15 |
| Setpoints | Hypothetical chilled handling | 1–3.5 °C air route | ±0.5 °C |
| Event length | Hypothetical disruption | Configured per scenario | ×0.75–1.25 |
| Indicator references | Operational comparisons, **not universal limits** | 2 and 4 °C | Both analyzed |

Air and sea stage durations, setpoints, ambient values, and event schedules are individually named and justified in [experiment.yaml](../../configs/digital_twin/experiment.yaml) and [sea_route.yaml](../../configs/digital_twin/sea_route.yaml). No observational uncertainty distribution exists for a Kochi–EU fish route; Monte Carlo ranges are bounded *stress assumptions*, not fitted confidence intervals. The 14-day sea scenario is a software/operations stress case and cannot answer whether chilled fish remains saleable.

The 31,140-row citrus reefer source has 36 package-position streams, selected `10C_OP.csv:P1_mean` at 0.5 h spacing, with no missing temperatures or duplicate stream-time rows in the curated table. Source: <https://data.mendeley.com/datasets/mvr7m6mcgp/2>. The 1,411,515-row generic cold-room source has nine sensors at roughly 5 s spacing, 328,893 missing temperature entries, unknown sensor placement/timezone, and 2,240 SENSOR02 readings above 30 °C in the full record. Source: <https://zenodo.org/records/15130001>. A stable selected SENSOR02 window is replayed after discarding 120 h; no inference is made about what caused excluded anomalies. [Proxy manifests](proxy_replay_manifests.json) give windows, residual quantiles, transformation, spacing, and warnings. Relative source time is used only; source timestamps are never claimed to be shipment times.
