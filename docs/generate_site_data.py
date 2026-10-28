"""Export executed Parquet results as a compact static website dataset."""
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'assets' / 'experiment_data.json'
OUT.parent.mkdir(parents=True, exist_ok=True)

comparison = pd.read_parquet(ROOT / 'results/integration/scenario_comparison.parquet')
stages = pd.read_parquet(ROOT / 'results/integration/stage_contributions.parquet')
assert len(comparison) == 192 and len(stages) == 1344

rows = comparison[['route', 'mode', 'scenario', 'channel', 'reference_c',
                   'duration_h', 'degree_hours', 'delta_degree_hours',
                   'hours_above', 'peak_c']].copy()
stage_rows = stages[['route', 'mode', 'scenario', 'channel', 'reference_c',
                     'stage_id', 'stage_duration_h', 'degree_hours']].copy()

def clean(frame):
    frame = frame.where(pd.notnull(frame), None)
    return frame.to_dict(orient='records')

payload = {
    'scope': 'Saved, hypothetical thermal simulations; °C·h is not spoilage probability.',
    'comparison_rows': len(rows),
    'stage_rows': len(stage_rows),
    'scenarios': clean(rows),
    'stages': clean(stage_rows),
    'models': {
        'trout_tvc': {'validation': 'Grouped internal CV; no untouched final test',
                      'mae_log10_cfu_g': 0.5387176308341838,
                      'development_assays': 17},
        'dafif_clusters': {'validation': 'Descriptive only', 'workbooks': 63,
                           'silhouette_k3': 0.304779},
        'fresh_fish_spoilage': {'status': 'NOT_CALIBRATED'},
    }
}
OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')),
               encoding='utf-8')
print(f'{OUT.relative_to(ROOT)}: {OUT.stat().st_size:,} bytes')
