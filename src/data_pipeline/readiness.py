"""Scientific data-readiness gate; this does not train or score a model."""
import json
import pandas as pd
from src.data_pipeline.cli import CUR,META

def assess():
 dafif=pd.read_parquet(CUR/'fish_sensor_observations.parquet')
 trout=pd.read_parquet(CUR/'trout_sensor_observations.parquet')
 tvc=pd.read_parquet(CUR/'trout_microbiology_outcomes.parquet')
 catfish=pd.read_parquet(CUR/'fish_temperature_quality_experiments.parquet')
 split=pd.read_csv(META/'split_manifest.csv') if (META/'split_manifest.csv').exists() else None
 result={
  'dafif_sensor_recording_groups':int(dafif.recording_group_id.nunique()),
  'dafif_known_independent_biological_sensor_groups':0,
  'dafif_measured_product_temperature_rows':int(dafif.product_temperature_c.notna().sum()),
  'dafif_specimen_matched_quality_rows':0,
  'trout_sensor_fillets':int(trout.fillet_id.nunique()),
  'trout_separate_measured_tvc_fillets':int(tvc.microbiology_sample_id.nunique()),
  'trout_sensor_tvc_specimen_overlap':len(set(trout.fillet_id)&set(tvc.microbiology_sample_id)),
  'trout_storage_temperature_treatments':1,
  'smoked_catfish_treatment_conditions':int(catfish.storage_condition.nunique()),
  'independent_indian_export_shipments_with_paired_quality':0,
  'exploratory_day_split_group_overlap':bool(split.groupby('day').proposed_role.nunique().gt(1).any()) if split is not None else False,
  'measured_freshness_classifier':'BLOCKED',
  'primary_chilled_finfish_thermal_calibration':'BLOCKED',
  'independent_export_reliability':'BLOCKED',
  'scenario_inputs':'CONDITIONALLY_READY',
 }
 assert result['trout_sensor_tvc_specimen_overlap']==0
 assert not result['exploratory_day_split_group_overlap']
 (META/'readiness_smoke.json').write_text(json.dumps(result,indent=2))
 return result

if __name__=='__main__': print(json.dumps(assess(),indent=2))
