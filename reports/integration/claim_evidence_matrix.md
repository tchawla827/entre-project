# Claim–evidence matrix and chart captions

The [machine-readable matrix](../../results/integration/claim_evidence_matrix.json) maps supported engineering findings, limited within-study diagnostics and blocked biological claims. Each Phase 4 chart below is a hypothetical scenario display; the charts do not show real fish spoilage, legal compliance or field prediction accuracy.

| Figure | Caption and supported claim | Cannot support |
|---|---|---|
| [Air channels](../../figures/integration/air_scenario_channels.png) | Additional °C·h above 2 °C for the configured air interventions; equipment-air versus assumed product lag. | Measured fish-core difference or spoilage rate. |
| [Sea channels](../../figures/integration/sea_scenario_channels.png) | Same comparison within the conditional 375 h sea configuration. | Sea transport suitability or air-vs-sea biological ranking. |
| [Air reference](../../figures/integration/air_reference_comparison.png), [sea reference](../../figures/integration/sea_reference_comparison.png) | Combined-case simulated air °C·h at two configurable reference temperatures. | Universal safety threshold or regulatory pass/fail. |
| [Air Shapley](../../figures/integration/air_shapley.png), [sea Shapley](../../figures/integration/sea_shapley.png) | Exact allocation of the modeled three-intervention combined *thermal* effect. | Real causal contributors to fish spoilage. |
| [Standardized events](../../figures/integration/standardized_stage_events.png) | Equal-duration/equal-offset perturbation experiment; ranks conditional modeled response. | An intrinsic risk ranking independent of operating context. |
| [Assumption draws](../../figures/integration/assumption_draw_distributions.png) | Distribution of additional simulated air °C·h under bounded hypothetical parameter draws. | Biological prediction interval or parameter-confidence interval. |
| [Rank stability](../../figures/integration/road_rank_stability.png) | Fraction of bounded draws where the specified road event is the largest single intervention at 2 °C. | Probability that road is the dominant failure in real shipments. |
| [Physical-stage stability](../../figures/integration/physical_stage_rank_stability.png) | Fraction of bounded draws where each actual stage contains the most combined-case simulated air exposure above 2 °C. | Causal attribution of spoilage or equivalence to intervention effects. |

Phase 3 [temperature-time traces](../../figures/digital_twin/baseline_vs_road_failure.png), [stage decomposition](../../figures/digital_twin/stage_exposure_decomposition.png), [proxy comparison](../../figures/digital_twin/proxy_shape_replay_comparison.png), [time-step verification](../digital_twin/verification_and_validation.md) remain complementary evidence. Source types, units and limitations are visible in the titles/axes and in this caption registry.
