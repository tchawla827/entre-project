# Sensitivity and uncertainty

`analyze --all` executes **200 paired draws**, seed **2403**. For each draw, baseline and every intervention share duration multiplier 0.85–1.15, setpoint offset −0.5 to +0.5 °C, ambient offset −3 to +3 °C, air time constant 0.4–1.2 h, illustrative product time constant 0.75–3 h, and event-length multiplier 0.75–1.25. Draws are bounded scenario-assumption variations, **not** estimates from Indian fish shipments. See [draws](../../results/digital_twin/assumption_draws.parquet), [quantiles](monte_carlo_quantiles.csv), [assumption sensitivity](assumption_sensitivity.csv), and [figure](../../figures/digital_twin/assumption_uncertainty.png).

| One-stage/combined scenario | Median added air °C·h >2 °C | 5th–95th draw quantiles |
|---|---:|---:|
| Road failure | 56.265 | 41.074–70.533 |
| Airport delay/door | 39.271 | 26.453–51.528 |
| Storage setpoint | 24.505 | 17.927–32.337 |
| Flight excursion | 19.160 | 13.903–24.084 |
| Destination delay | 4.458 | 3.102–5.831 |
| Processing delay | 2.985 | 1.623–4.361 |
| Combined | 115.902 | 83.889–139.681 |

Road is the dominant **one-stage** intervention in 197/200 draws at the 2 °C reference and 193/200 at 4 °C; airport dominates the others. These frequencies describe this bounded artificial draw design and are not calibrated probabilities about real operations. The paired-draw Spearman association with combined 2 °C extra exposure is strongest for event-length multiplier (~0.856), then ambient offset (~0.468), setpoint offset (~0.267), and air lag (~0.250). Correlations are descriptive and not causal effects or fitted uncertainty. Estimated-product lag has minimal association with the *air* indicator by design; it affects the separately reported estimated-product channel.

An accumulating-draw [convergence table](monte_carlo_convergence.csv) records the combined median and road-dominant fraction at 25, 50, 100, 150, and 200 draws. At 2 °C the combined median moves from **107.605** at 25 to **115.902 °C·h** at 200, while road dominance moves from **1.000** to **0.985**. The median is not fully stable at the smallest sample; 100-to-200 changes by about **1.32 °C·h**. This is a convergence diagnostic for the chosen random draws, not external validation or an error bound.

Stress cases vary event magnitude beyond the main bounded draws. At nominal magnitudes, road ranks first at both 2 and 4 °C. At 0.5 h road failure, airport ranks first at both references. At +8 °C for 8 h flight excursion, flight ranks first at 2 °C while road remains first at 4 °C. See [event magnitude table](event_magnitude_sensitivity.csv). Proxy replay yields modest baseline differences but cannot test route validity, since both source datasets are nonfish and outside the modeled shipment. No biological prediction interval, parameter-estimation uncertainty, or external-validation uncertainty is claimed.
