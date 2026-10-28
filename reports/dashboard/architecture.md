# Dashboard architecture

`app.py` is a thin Streamlit presenter with two tabs. `src/dashboard/service.py` resolves route-specific scenarios from Phase 3 YAML, validates a version-1 `IntegrationRequest`, and calls `src.integration.execute` for the selected and same-context baseline runs. The UI contains no temperature dynamics or biological inference. It checks an exact request/channel key before showing live metrics or downloads, so a changed setting cannot silently export an old run.

`src/dashboard/loaders.py` checks allowed Parquet names, required columns and schema version. The saved comparison is cached by file modification timestamp; live simulations are executed on demand. `src/dashboard/export.py` packages only the current API response and its matched baseline, retaining run ID, request, source provenance and `NOT_CALIBRATED` status in the JSON. The `.streamlit/config.toml` theme supplies the restrained colors.

The previous multi-page dashboard was removed from the UI; full intervention attribution, uncertainty and Phase 2 study diagnostics remain in the Phase 4 reports, Parquets and Python API. No Phase 1–4 source, model, configuration, data or result artifact was changed for this redesign.
