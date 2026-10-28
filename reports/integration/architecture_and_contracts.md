# Architecture and contracts

`src.integration.api.execute()` is the single Python entry point for Phase 5. `IntegrationRequest` and its JSON-compatible `schema_version: 1` dictionary form validate route (`air`/`sea`), configured scenario, source mode, species metadata, chilled product state, UTC start, Celsius units, references, step, seed, stage overrides and bounded perturbation keys. Invalid inputs fail explicitly. The service delegates simulation to `src.digital_twin.simulation.simulate`, source replay to `ProxyReplay`, and biological within-study diagnostics to `src.models.inference`; it duplicates none of their prediction algorithms.

For `target: thermal_exposure`, the v1 response contains `status: SIMULATED_EXPOSURE_ONLY`, original request, run ID, route ID, source class and provenance, nested route/stage/event exposure, optional trace rows, `prediction: null`, `unavailable_reason`, and capability registry. Both air and estimated-product channels are named separately; the latter is *assumed lag*, never `measured_fish_core`. Species is metadata and does not adjust physics. A source mode named `proxy_*` yields a transformed synthetic trace marked `nonfish_proxy_shaped_synthetic`, not measured shipment temperatures. The output trace can be omitted from the in-memory response with `include_trace=False`, while saved experiment traces remain available.

For `trout_tvc_within_domain`, the request must identify rainbow-trout fillet at nominal 4 °C and age 0–6 days; the response is `LIMITED_WITHIN_STUDY`, with no thermal trace. `smoked_catfish_endpoint_within_domain` requires smoked-catfish product state, a known endpoint, categorical package/condition, and age 0–90 days; it also has no route trace. Prior to loading either artifact, the service compares SHA-256 with Phase 2's recorded manifest and refuses missing or modified files. Both responses explicitly mark that they are not spoilage probabilities. `fresh_fish_quality_trajectory` and `spoilage_probability` raise `UnsupportedCalibrationError` end to end; there is no exposure fallback.

Example:

```python
from src.integration import execute
r = execute({"schema_version": 1, "target": "thermal_exposure",
             "route": "air", "scenario": "road_failure",
             "mode": "synthetic", "references_c": [2.0, 4.0]}, include_trace=False)
print(r["run_id"], r["thermal_exposure"]["route"]["air"]["references"]["2.0"]["degree_hours"])
```

The CLI writes v1 Parquet/JSON datasets in `results/integration/`; paths, schemas and commands are in the [final handoff](final_handoff.md). Phase 3 CLI and result schemas remain intact.
