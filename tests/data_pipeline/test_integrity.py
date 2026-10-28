import hashlib
from pathlib import Path
import pandas as pd
import pytest
from src.data_pipeline.cli import ROOT, CUR, META, validate

def test_curated_integrity_and_gates():
 assert validate()['status']=='PASS'
 sensors=pd.read_parquet(CUR/'fish_sensor_observations.parquet')
 labels=pd.read_parquet(CUR/'freshness_observed_labels.parquet')
 assert len(sensors)==27120 and len(labels)==774
 assert sensors.groupby('recording_group_id').size().sum()==len(sensors)
 assert sensors.groupby('recording_group_id').mq135_raw_delta.apply(lambda x:x.isna().sum()).eq(1).all()
 assert sensors.groupby('recording_group_id').tgs2602_raw_roll_std_10.apply(lambda x:x.isna().sum()).eq(1).all()
 assert sensors.groupby('recording_group_id').elapsed_seconds.apply(lambda x:x.is_monotonic_increasing).all()
 assert labels.sensor_fish_id.isna().all()
 assert not (CUR/'model_ready_freshness.parquet').exists()
 assert not (CUR/'model_ready_thermal.parquet').exists()

def test_raw_checksums():
 for line in (META/'checksums.sha256').read_text().splitlines():
  digest,path=line.split('  ',1)
  assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest

def test_aggregation_and_product_boundaries():
 stats=pd.read_parquet(CUR/'mpeda_export_statistics.parquet')
 catfish=pd.read_parquet(CUR/'fish_temperature_quality_experiments.parquet')
 citrus=pd.read_parquet(CUR/'citrus_reefer_temperature_proxy.parquet')
 assert set(stats.dimension_type)=={'item','market','port'}
 assert stats.statistic_id.is_unique
 assert set(catfish.product_state)=={'smoked'}
 assert catfish.loc[catfish.storage_age_days.eq(0),'is_inferential_postbaseline'].eq(False).all()
 assert set(citrus.commodity)=={'citrus'}
 assert not any(x in citrus.columns for x in ['shipment_id','fish_quality','spoiled'])

def test_trout_sensor_assay_separation():
 sensors=pd.read_parquet(CUR/'trout_sensor_observations.parquet')
 tvc=pd.read_parquet(CUR/'trout_microbiology_outcomes.parquet')
 assert len(sensors)==25200 and sensors.fillet_id.nunique()==59
 assert len(tvc)==21 and tvc.microbiology_sample_id.nunique()==21
 assert set(sensors.fillet_id).isdisjoint(set(tvc.microbiology_sample_id))
 assert sensors.groupby('storage_day_one_based').embedded_day_label_proxy.nunique().eq(1).all()
 assert tvc.link_to_sensor.eq('storage_day_only_separate_biological_specimens').all()
 assert sensors.groupby(['storage_day_one_based','fillet_id']).size().eq(120).all()

def test_split_warning_and_no_specimen_overlap_claim():
 split=pd.read_csv(META/'split_manifest.csv')
 assert split.recording_group_id.is_unique
 assert split.groupby('day').proposed_role.nunique().eq(1).all()
 assert split.leakage_warning.str.contains('NOT specimen-independent').all()
 assert split.eligibility.eq('blocked_for_measured_freshness_ML').all()
 import json
 readiness=json.loads((META/'readiness_smoke.json').read_text())
 assert readiness['measured_freshness_classifier']=='BLOCKED'
 assert readiness['primary_chilled_finfish_thermal_calibration']=='BLOCKED'
 assert readiness['independent_indian_export_shipments_with_paired_quality']==0
