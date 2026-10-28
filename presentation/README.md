# Rebuild the presentation

The checked 12-slide deck is available at the project root as `Fisheries_Cold_Chain_Project.pptx` and `Fisheries_Cold_Chain_Project.pdf`. It includes speaker notes with evidence sources.

To rebuild the editable PowerPoint after the project results are present:

```powershell
py -3.12 -m pip install -r presentation/requirements.txt
py -3.12 presentation/build_presentation.py
```

The builder reads `results/integration/scenario_comparison.parquet`, embeds an actual dashboard screenshot, writes the PPTX and checks slide structure. PDF rendering uses Microsoft PowerPoint on Windows:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File presentation/render_presentation.ps1
```

The saved PDF is included for systems without PowerPoint. See `COMPLETE_README.MD` for the scientific status behind every chart.
