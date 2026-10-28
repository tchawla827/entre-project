# Numerical cross-checks

All values below came from executed `src.integration.execute` calls at 15-minute step, seed 2404, above a 2 °C **comparison reference**. Dashboard values use the same API, never Markdown constants. Tolerance used in automated fixture checks: `pytest.approx` floating tolerance (default relative 1e-6); stage-sum differences were below 1e-12 °C·h for the cases inspected.

| Route | Mode | Baseline air °C·h | Combined air °C·h | Baseline duration h | Combined duration h |
|---|---|---:|---:|---:|---:|
| Air | synthetic | 15.045518 | 128.082937 | 47 | 50 |
| Air | proxy_citrus | 15.431473 | 128.068657 | 47 | 50 |
| Air | proxy_coldroom | 15.873721 | 127.829955 | 47 | 50 |
| Sea | synthetic | 13.464000 | 140.398184 | 375 | 378 |
| Sea | proxy_citrus | 13.031453 | 140.645846 | 375 | 378 |
| Sea | proxy_coldroom | 14.267977 | 140.066679 | 375 | 378 |

The air synthetic `road_failure` live call returned **70.84803997815442 °C·h** versus matched baseline **15.045518284998254 °C·h**. Combined air adds **113.03741885146633 °C·h**. The browser showed the rounded 70.848 and 15.046 values. The assumed product-lag channel is separate: air synthetic baseline **11.880277** and combined **124.376127 °C·h**; it is not fish-core measurement. Each inspected route-stage sum equaled its API route total to floating precision. Sea's low modeled baseline exposure despite its long duration says nothing about fish viability.

The comparison Parquet has 192 rows (48 route/mode/scenario runs × two channels × two references); 1,344 stage rows; 2,400 paired assumption-draw scenario rows. Null baseline-relative percentage is rendered N/A when baseline degree-hours are zero.
