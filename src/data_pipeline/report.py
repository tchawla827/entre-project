"""Generate source, lineage, coverage and scientific sufficiency reports from curated files."""
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from src.data_pipeline.cli import ROOT,RAW,CUR,META,REP,SOURCE,filehash

def md(path,body):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(body.strip()+'\n',encoding='utf-8')
def csv(path,rows): pd.DataFrame(rows).to_csv(path,index=False)
def fingerprint():
 paths=list((RAW/'local').glob('*'))+list((RAW/'dafif_official').glob('*'))+list((RAW/'mpeda').glob('*'))+list((RAW/'external').glob('*'))+[p for p in (RAW/'trout_selected').rglob('*') if p.is_file()]
 rows=[]
 for p in sorted(paths): rows.append({'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':filehash(p)})
 md(META/'checksums.sha256','\n'.join(f"{r['sha256']}  {r['path']}" for r in rows))
 return rows
def local_comparison(sensor):
 local=pd.read_csv(ROOT/'combined_dataset.csv')
 official={filehash(p):p.name.split('_',1)[0] for p in (RAW/'dafif_official').glob('*.xlsx')}
 mapping={p.name:official.get(filehash(p)) for p in (RAW/'local').glob('*.xlsx')}
 local['source_file_id']=local.source_file.map(mapping)
 source=sensor[['source_file_id','source_row','mq135_raw','tgs2602_raw','local_timestamp']].copy()
 source['sample_index']=source.source_row-2
 merged=local.merge(source,on=['source_file_id','sample_index'],how='left',indicator=True,validate='one_to_one')
 match=(merged['_merge'].eq('both') & merged.mq1_reading.eq(merged.mq135_raw) & merged.tgs1_reading.eq(merged.tgs2602_raw))
 return {'local_rows':len(local),'local_files':local.source_file.nunique(),'matched_raw_sensors':int(match.sum()),
  'unmatched_or_changed':int((~match).sum()),'local_missing':local.drop(columns='source_file_id').isna().sum().loc[lambda s:s.gt(0)].to_dict(),
  'local_session_metadata_mismatch':int((merged['_merge'].eq('both') & merged.session.ne(pd.to_numeric(merged.source_file_id.map(sensor.groupby('source_file_id').session_number.first()),errors='coerce'))).sum()),
  'local_exact_duplicates':int(local.duplicated().sum())}
def dictionary(sensor,labels,stats,catfish,berry,cold):
 descriptions={
 'observation_id':'Stable source file UUID and one-based Excel row, or source-specific row ID',
 'source_file_id':'Official Mendeley file UUID',
 'recording_group_id':'One DaFiF workbook; not an independent biological fish',
 'fish_type_source':'Raw filename spelling; preserve misspellings',
 'species_common':'Source repository common-name category; scientific species unresolved for DaFiF',
 'storage_day_one_based':'Published day number 1 through 11',
 'storage_age_days':'Published day minus one; not measured post-harvest hours',
 'local_timestamp':'Clock time as recorded, timezone unspecified',
 'mq135_raw':'Instrument output in unknown physical units; not calibrated ammonia concentration',
 'tgs2602_raw':'Instrument output in unknown physical units; not calibrated gas concentration',
 'sensory_score':'Observed criterion score on separate expert-assessed fish; paper includes one 0 despite scale described as 1–9',
 'temperature_c':'Observed proxy logger/product-position series depending on source; no relation to DaFiF fish',
 'product_temperature_c':'Unavailable for DaFiF',
 'value':'Original MPEDA annual aggregate value in specified measure_unit',
 'temperature_min_c':'Published treatment lower bound; no per-package logger',
 'temperature_max_c':'Published treatment upper bound; no per-package logger',
 'fillet_id':'Trout longitudinal fillet identifier from source filename',
 'candidate_original_fish_id':'Filename component inferred as fish ID; requires author confirmation',
 'mq135_adc':'Trout MQ135 raw 10-bit Arduino ADC value, 0–1023; no gas calibration',
 'measurement_chamber_temperature_c':'Trout sensor measurement chamber temperature, not storage product core',
 'embedded_day_tvc_proxy_log10_cfu_g':'Repeated daily mean proxy embedded by source in each sensor row; not a fillet assay',
 'embedded_day_label_proxy':'Source day-level TVC threshold class; not individual fillet ground truth',
 'tvc_cfu_g':'Observed TVC from destructively assessed trout fillet, CFU/g',
 'tvc_log10_cfu_g':'Observed log10 TVC from destructively assessed trout fillet, log10 CFU/g',
 'storage_temperature_protocol_c':'Nominal 4 °C storage protocol, not observed per-fillet logger',
 }
 units={'elapsed_seconds':'seconds','elapsed_hours':'hours','storage_age_days':'days','sensory_score':'published ordinal points',
  'mq135_raw':'uncalibrated source units','tgs2602_raw':'uncalibrated source units','temperature_c':'°C',
  'temperature_min_c':'°C','temperature_max_c':'°C','relative_humidity_pct':'percent',
  'value':'see measure_unit'}
 units.update({'mq135_adc':'raw 10-bit ADC','measurement_chamber_temperature_c':'°C',
  'embedded_day_tvc_proxy_log10_cfu_g':'log10 CFU/g','tvc_cfu_g':'CFU/g',
  'tvc_log10_cfu_g':'log10 CFU/g','storage_temperature_protocol_c':'°C'})
 tables={'fish_sensor_observations':sensor,'freshness_observed_labels':labels,'mpeda_export_statistics':stats,
 'fish_temperature_quality_experiments':catfish,'citrus_reefer_temperature_proxy':berry,'coldroom_temperature_proxy':cold,
 'trout_sensor_observations':pd.read_parquet(CUR/'trout_sensor_observations.parquet'),
 'trout_microbiology_outcomes':pd.read_parquet(CUR/'trout_microbiology_outcomes.parquet'),
 'trout_modality_availability':pd.read_parquet(CUR/'trout_modality_availability.parquet'),
 'coldroom_actions_proxy':pd.read_parquet(CUR/'coldroom_actions_proxy.parquet'),
 'regulatory_reference':pd.read_parquet(CUR/'regulatory_reference.parquet'),
 'route_stage_catalog':pd.read_parquet(CUR/'route_stage_catalog.parquet'),
 'thermal_deterioration_evidence':pd.read_parquet(CUR/'thermal_deterioration_evidence.parquet')}
 rows=[]
 permissions={'fish_sensor_observations':'DaFiF CC BY 4.0','freshness_observed_labels':'Article table; verify article reuse rights',
 'trout_sensor_observations':'Zenodo CC BY 4.0; selected ZIP members',
 'trout_microbiology_outcomes':'Zenodo CC BY 4.0; selected ZIP member',
 'trout_modality_availability':'Zenodo CC BY 4.0; selected ZIP member',
 'mpeda_export_statistics':'MPEDA public download; confirm redistribution terms',
 'fish_temperature_quality_experiments':'Mendeley CC BY 4.0',
 'citrus_reefer_temperature_proxy':'Mendeley CC BY 4.0',
 'coldroom_temperature_proxy':'Zenodo record license; verify terms',
 'coldroom_actions_proxy':'Zenodo record license; verify terms',
 'regulatory_reference':'EU official legal reference',
 'route_stage_catalog':'project scenario assumptions',
 'thermal_deterioration_evidence':'source-derived metadata; cite Mendeley CC BY 4.0'}
 for table,df in tables.items():
  for col in df:
   rows.append({'table':table,'column':col,'dtype':str(df[col].dtype),'nullable':bool(df[col].isna().any()),
    'null_count':int(df[col].isna().sum()),'unit':units.get(col,''),'definition':descriptions.get(col,'Source field or documented transform; see column_lineage.csv'),
    'provenance':'observed; proxy products identified by table/source','primary_key':col in {'observation_id','assessment_id','statistic_id'},
    'source_permission':permissions[table]})
 csv(META/'data_dictionary.csv',rows)
 lineage=[]
 for r in rows:
  table=r['table'];col=r['column'];source={'fish_sensor_observations':'DaFiF official v1 workbook',
   'freshness_observed_labels':'Prasetyo et al. 2024 Table 3','mpeda_export_statistics':'MPEDA 2025-26 XLSX',
   'fish_temperature_quality_experiments':'Ansong et al. 2026 Mendeley package CSV',
   'citrus_reefer_temperature_proxy':'Berry et al. 2020 six CSV files',
   'coldroom_temperature_proxy':'Zenodo 15130001 Preprocessed.zip',
   'trout_sensor_observations':'Zenodo 23600663 selected sensor CSV members',
   'trout_microbiology_outcomes':'Zenodo 23600663 tvc_individual_measurements.csv',
   'trout_modality_availability':'Zenodo 23600663 multimodal_fillet_day_matrix.csv',
   'coldroom_actions_proxy':'Zenodo 15130001 experiment_actions.csv',
   'regulatory_reference':'EU 853/2004 current consolidation 2026-05-07',
   'route_stage_catalog':'proposed stages based on Indian case context',
   'thermal_deterioration_evidence':'Mendeley smoked catfish treatment definitions'}[table]
  lineage.append({'table':table,'column':col,'source':source,'transformation':r['definition'] if col in descriptions else 'source value retained or source-specific rename','source_record_pointer':'source_file plus source_row/record ID where available'})
 csv(META/'column_lineage.csv',lineage)
 return tables
def registry(counts):
 sources=[
 ('dafif_official','fish sensors','Mendeley DaFiF v1','https://data.mendeley.com/datasets/vx4ptwk3pb/1','10.17632/vx4ptwk3pb.1','CC BY 4.0','downloaded',counts['sensor_rows'],'Indonesia; 2024-01-19 to 2024-01-29','recording_group_id, source_row','sensor training features only; fish ID and temperature absent'),
  ('dafif_article','quality scores','Prasetyo et al. Table 3','https://pmc.ncbi.nlm.nih.gov/articles/PMC11528684/','','article rights; source data CC BY 4.0','downloaded',counts['sensory_criterion_rows'],'Indonesia; storage days 1–11','species_common, storage day, session only','assessed different fish; ecological link, no individual target'),
  ('trout','fish sensors and measured microbiology','Rainbow trout multimodal v4','https://zenodo.org/records/23600663','10.5281/zenodo.23600663','CC BY 4.0','selected_tabular_members_downloaded',counts['trout_sensor_rows']+counts['trout_individual_tvc_rows'],'7 days at nominal 4 °C','fillet_id for sensors; separate microbiology_sample_id','21 TVC measured on distinct fillets; embedded sensor labels are day-level proxies'),
 ('mpeda','India context','MPEDA 2025-26 annual exports','https://mpeda.gov.in/?page_id=438','','official public download; reuse terms review','downloaded',counts['mpeda_statistic_rows'],'India FY1995-96 to 2025-26','dimension + financial_year + measure','separate item/market/port marginals; no shipment rows'),
 ('berry','thermal proxy','Berry citrus reefer v2','https://data.mendeley.com/datasets/mvr7m6mcgp/2','10.17632/mvr7m6mcgp.2','CC BY 4.0','downloaded',counts['citrus_temperature_rows'],'six experiments','file + elapsed_hours + position','citrus, not seafood; no fish quality'),
 ('coldroom','operations proxy','Henrichs cold room Zenodo','https://zenodo.org/records/15130001','10.5281/zenodo.15130001','CC BY 4.0 per record; verify','downloaded',counts['coldroom_temperature_rows'],'2024-09','sensor_id + local_timestamp','generic cold room; no fish quality'),
 ('catfish','thermal quality experiment','smoked catfish package data','https://data.mendeley.com/datasets/tvsw53j89z/1','10.17632/tvsw53j89z.1','CC BY 4.0','downloaded',counts['smoked_catfish_outcome_rows'],'90 days','package_type, storage_condition, time, replicate_index, outcome','smoked catfish; treatment temperature ranges; processing run unavailable'),
 ('seabream_2022','thermal quality candidate','Gilthead sea bream fillets','https://pmc.ncbi.nlm.nih.gov/articles/PMC9367857/','','article open access','article_obtained',0,'0,4,8,12 °C experiment','no machine-readable replicate table identified','published model metrics; raw paired observations needed'),
 ('horse_mackerel','thermal quality candidate','Japanese horse mackerel microbiology','https://pmc.ncbi.nlm.nih.gov/articles/PMC9391519/','','article open access','article_obtained',0,'4/20 °C experiments','paper table only','not source-level rows; different species'),
 ('hammond','general thermal evidence','Hammond Dryad supplemental','https://datadryad.org/dataset/doi:10.5061/dryad.6708r','10.5061/dryad.6708r','Dryad page; check file license','access_restricted_403',0,'general food microbe','none','not fish-specific; file download 403'),
 ('noaa','thermal reference','Doyle seafood shelf life 1989','https://repository.library.noaa.gov/view/noaa/34680','','public domain','downloaded',0,'literature summary','none','compiled shelf-life estimates, not replicate observations'),
 ('india_operations','route evidence','Indian seafood cold chain case study','https://dmeo.gov.in/sites/default/files/2021-08/Package1_Fisheries_CaseStudy1.pdf','','official report; review reuse','downloaded',0,'India case study','none','company practice, not export event logs'),
 ('eu853','regulatory','EU Regulation 853/2004 current consolidation','https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=celex%3A32004R0853','','EU legal text','reference_verified',0,'consolidation 2026-05-07','none','current provisions are product/state specific'),
 ('shipment_validation','external validation','Indian exporter shipment and destination quality','', '', 'private; permission needed','blocked',0,'unavailable','shipment_id, lot_id','no independent paired records found'),
 ]
 rows=[]
 for sid,req,name,url,doi,license,status,n,coverage,join,lim in sources:
  rows.append({'source_id':sid,'requirement':req,'candidate_source':name,'url':url,'doi':doi,'license':license,
   'date_accessed_utc':'2026-10-27','acquisition_status':status,'number_of_records':n,'time_coverage':coverage,
   'join_keys':join,'limitation':lim,'grain':join,'required_columns_and_units':'see docs/data_requirements_matrix.md',
   'target_species_state_region':'chilled finfish / India–EU primary scenario; source-specific deviations noted',
   'priority':'critical' if sid in {'dafif_official','dafif_article','shipment_validation'} else 'supporting',
   'confidence':'high' if status in {'downloaded','selected_tabular_members_downloaded'} else 'low',
   'supports_training':'features only; no paired measured target' if sid in {'dafif_official','trout'} else 'no',
   'supports_calibration':'smoked-catfish-only' if sid=='catfish' else 'no',
   'supports_scenario_input':sid in {'berry','coldroom','mpeda','india_operations','eu853'},
   'supports_external_validation':False})
 csv(META/'dataset_registry.csv',rows)
 return rows

def split_manifest(groups):
 roles={1:'train_exploratory',2:'train_exploratory',3:'train_exploratory',4:'train_exploratory',5:'train_exploratory',6:'train_exploratory',7:'train_exploratory',8:'validation_exploratory',9:'validation_exploratory',10:'test_exploratory',11:'test_exploratory'}
 d=groups.copy();d['proposed_role']=d.day.map(roles)
 d['leakage_warning']='fish identity not recorded; likely same fish across days; split is NOT specimen-independent'
 d['eligibility']='blocked_for_measured_freshness_ML'
 d.to_csv(META/'split_manifest.csv',index=False)
 trout=pd.read_parquet(CUR/'trout_sensor_observations.parquet')
 tr=trout[['fillet_id','candidate_original_fish_id','fish_id_status']].drop_duplicates().copy()
 tr['candidate_fish_number']=pd.to_numeric(tr.candidate_original_fish_id,errors='coerce')
 tr['proposed_role']=tr.candidate_fish_number.map(lambda n:'train_exploratory' if n<=12 else 'validation_exploratory' if n<=16 else 'test_exploratory')
 tr['eligibility']='blocked_for_specimen_matched_quality_ML'
 tr['leakage_warning']='candidate original-fish ID inferred from filename; confirm with authors; TVC fish are separate'
 tr.to_csv(META/'trout_split_manifest.csv',index=False)

def main():
 REP.mkdir(parents=True,exist_ok=True);META.mkdir(exist_ok=True)
 counts=json.loads((META/'build_counts.json').read_text())
 sensor=pd.read_parquet(CUR/'fish_sensor_observations.parquet');labels=pd.read_parquet(CUR/'freshness_observed_labels.parquet')
 stats=pd.read_parquet(CUR/'mpeda_export_statistics.parquet');catfish=pd.read_parquet(CUR/'fish_temperature_quality_experiments.parquet')
 berry=pd.read_parquet(CUR/'citrus_reefer_temperature_proxy.parquet');cold=pd.read_parquet(CUR/'coldroom_temperature_proxy.parquet')
 groups=pd.read_csv(META/'recording_groups.csv');local=local_comparison(sensor)
 files=fingerprint();tables=dictionary(sensor,labels,stats,catfish,berry,cold);sources=registry(counts);split_manifest(groups)
 (META/'source_manifest.json').write_text(json.dumps({'generated_utc':datetime.now(timezone.utc).isoformat(),
  'raw_files':files,'sources':sources,'curated_tables':{k:len(v) for k,v in tables.items()}},indent=2))
 coverage=sensor.groupby(['species_common','storage_age_days']).size().reset_index(name='observations')
 coverage['product_state']='ice_stored_whole_fish';coverage['geography']='Indonesia';coverage['measured_temperature_c_available']=False
 coverage['specimen_matched_outcome_available']=False
 trout=pd.read_parquet(CUR/'trout_sensor_observations.parquet')
 trout_coverage=trout.groupby('storage_age_days').size().reset_index(name='observations')
 trout_coverage['species_common']='Rainbow trout';trout_coverage['product_state']='refrigerated_fillet'
 trout_coverage['geography']='source study; country not confirmed from metadata'
 trout_coverage['measured_temperature_c_available']=False
 trout_coverage['specimen_matched_outcome_available']=False
 coverage=pd.concat([coverage,trout_coverage[coverage.columns]],ignore_index=True)
 coverage.to_csv(META/'coverage_matrix.csv',index=False)
 md(META/'label_policy.md',f'''# Label policy

DaFiF [Table 3]({SOURCE}) was scored on other fish than those used for gas readings. The {len(labels)} criterion scores represent {counts['sensory_assessment_groups']} species/day/session assessments, not {len(sensor)} independent targets. No row-level label is assigned to sensor observations. Score 0 appears once in the source despite the described SNI 1–9 scale; it is retained and flagged for source clarification. The biological replicate and individual fish IDs are unavailable. No spoiled/fresh threshold is imposed, and `model_ready_freshness` is deliberately absent.

The [rainbow trout record](https://zenodo.org/records/23600663) has 21 individually measured TVC outcomes on a destructive subset and 25,200 sensor observations from 59 other fillets. Its sensor CSVs embed a repeated daily mean TVC and day-level Fresh/Spoiled flag; those are ecological proxies, **not** individual sensor-fillet quality measurements. The source explicitly states no one-to-one pairing. Chamber temperature is measured during gas sensing; the nominal 4 °C storage protocol is not a fish-product temperature trace. Fillet IDs are longitudinal, but the original-fish grouping inferred from filename pattern needs author confirmation.

The smoked catfish measurements have laboratory outcomes but belong to a different product process. Day-zero values are shared baselines; `is_inferential_postbaseline` is false. Temperature treatments are ranges, not per-package readings.
''')
 md(META/'join_policy.md','''# Join policy

DaFiF sensor and sensory scores may be compared descriptively at species, storage day and session. They must not be joined as specimen-matched training examples. The sensor recording group is a workbook, not a fish ID. Trout sensor fillets and destructive TVC fillets are disjoint biological subsets; the repeated TVC and class embedded in sensor CSVs are day-level proxies. MPEDA item, market and port tables are separate annual marginal totals, so a product × destination × port join is invalid. Citrus and generic cold-room traces cannot be linked to fish quality as observed journeys. Catfish package treatment outcomes cannot be joined to DaFiF. Only a real shared fish/lot/shipment key with documented provenance may establish evaluation pairs.
''')
 md(META/'provenance_graph.md','''# Provenance

DaFiF official 63 XLSX → `fish_sensor_observations` (raw output, source row, file UUID). DaFiF article XML Table 3 → `freshness_observed_labels` (separate fish). Zenodo trout 21 GB ZIP, selected tabular members via HTTP Range → `trout_sensor_observations`, `trout_microbiology_outcomes`, `trout_modality_availability` (separate biological subsets). MPEDA three original XLSX → `mpeda_export_statistics` (three distinct annual grains). Mendeley smoked-catfish CSV → `fish_temperature_quality_experiments` (smoked only). Berry citrus six CSV → `citrus_reefer_temperature_proxy`. Zenodo cold-room Preprocessed.zip → `coldroom_temperature_proxy`; experiment_actions.csv → `coldroom_actions_proxy`. No edge between these experiments denotes shared subjects. `metadata/source_manifest.json` records acquired source hashes.
''')
 md(REP/'data_quality_report.md',f'''# Data quality and row reconciliation

Generated 2026-10-27. Official DaFiF: **{len(sensor):,} rows**, {len(groups)} workbook groups, by source common-name category: {sensor.groupby('species_common').size().to_dict()}. The article Table 1 reports 9,041 per species (27,123 total); workbooks contain 9,020 Mackerel, 9,029 Tilapia and 9,071 Tuna (27,120 total). This is a **three-row net discrepancy** with substantial species-level redistribution; source files are preserved, and no balancing rows were invented.

Local `combined_dataset.csv`: {local['local_rows']:,} rows from {local['local_files']} recording groups, {local['matched_raw_sensors']:,} matching official file-hash/row/sensor tuples, {local['unmatched_or_changed']} raw sensor mismatches, {local['local_exact_duplicates']} exact duplicate rows. Its `session` field disagrees with the official repository folder for {local['local_session_metadata_mismatch']:,} rows, including Day 1 records and the ambiguous Tongkol filename. Local missing values: {local['local_missing']}. Its full-session z-scores and session progress use future data and are excluded from the curated feature table. Curated rolling/delta fields are recomputed in workbook order with past/current readings only; first delta and sample-standard-deviation per workbook are null, expected {len(groups)} each.

Official sensor raw ranges: MQ135 {sensor.mq135_raw.min()}–{sensor.mq135_raw.max()}, TGS2602 {sensor.tgs2602_raw.min()}–{sensor.tgs2602_raw.max()}; physical units and calibration metadata unavailable. Timestamps are source-local with unknown timezone. Missing fish/lot IDs, actual product temperatures, stages and shipments: all {len(sensor):,} rows. There are {int(groups.filename_session_conflict.sum())} filename/folder session conflicts (`24-01-2024(TongkolSesi2).xlsx` is in Session 1); curated session follows repository folder, conflict flagged. Workbooks' dates and time order are checked; no rows dropped.

Sensory Table 3: {len(labels)} criterion observations across {counts['sensory_assessment_groups']} source assessment groups; score counts {labels.sensory_score.value_counts().sort_index().to_dict()}. One zero contradicts the described 1–9 scale. Trout: {counts['trout_sensor_rows']:,} sensor points in 210 CSVs from 59 longitudinal fillets, plus **21 individual TVC measurements on different fillets** and {counts['trout_modality_rows']} modality-availability rows. Embedded source TVC/class columns are repeated day-level proxies and are excluded from individual-ground-truth claims. Its chamber temperature readings span {pd.read_parquet(CUR/'trout_sensor_observations.parquet').measurement_chamber_temperature_c.min():.2f}–{pd.read_parquet(CUR/'trout_sensor_observations.parquet').measurement_chamber_temperature_c.max():.2f} °C; this is measurement-chamber temperature, not the 4 °C storage treatment. Catfish: {len(catfish)} measured smoked-fish outcome rows; {int((~catfish.is_inferential_postbaseline).sum())} day-zero shared-baseline rows excluded from inferential use. MPEDA: {len(stats):,} financial-year × dimension × measure rows across three distinct marginal sheets; {int(stats.value.isna().sum())} missing values. Proxies: {len(berry):,} citrus temperature/position rows ({int(berry.temperature_c.isna().sum())} missing, {berry.temperature_c.min():.2f}–{berry.temperature_c.max():.2f} °C), {len(cold):,} generic cold-room sensor rows ({int(cold.temperature_c.isna().sum()):,} missing temperatures, {cold.temperature_c.min():.1f}–{cold.temperature_c.max():.1f} °C), and {counts['coldroom_event_rows']} logged actions. Missing cold-room values are retained as null; SENSOR05 and SENSOR09 have extensive gaps. None of these proxy records is fish-shipment telemetry.
''')
 md(REP/'acquisition_report.md',f'''# Acquisition and inspection

Downloaded or extracted {len(files)} immutable source files with SHA-256 checksums in `metadata/checksums.sha256`. The authoritative sensor repository is [DaFiF v1](https://data.mendeley.com/datasets/vx4ptwk3pb/1), DOI 10.17632/vx4ptwk3pb.1. Its API inventory lists 63 XLSX files and 2,536 JPEGs. All 63 spreadsheets were downloaded and verified against publisher SHA-256. Images are inventoried with file IDs and expected hashes in `metadata/dafif_official_inventory.json`; their ~10 MB each are unnecessary for gas-sensor data readiness. The local combined CSV and 33 workbook files are copied byte-for-byte under raw/local. The second combined CSV inside `Data_IIT2023150/Data/Dataset` has the same SHA-256 as the top-level copy. The README mentioned `Data_IIT2023150.zip`, but that ZIP was not present in the workspace; the extracted tree was audited instead.

The [rainbow trout v4 record](https://zenodo.org/records/23600663), DOI 10.5281/zenodo.23600663, packages 21.1 GB mainly of images. Its server supports HTTP byte ranges, allowing retrieval of **214 tabular/metadata ZIP members totaling ~1.2 MB** without the image payload. Every selected member passed ZIP CRC/size checks and has a SHA-256 in `metadata/trout_selected_manifest.json`; the full ZIP MD5 and central-directory inventory are recorded. Extracted files include 210 sensor CSVs, 21 individual laboratory TVC outcomes and a fillet-day availability matrix. Its CC BY 4.0 license permits reuse with attribution. The full 21 GB ZIP was not downloaded.

The [DaFiF article]({SOURCE}) XML supplies expert Table 3. Three current [MPEDA item, market and port workbooks](https://mpeda.gov.in/?page_id=438) cover FY1995-96 through 2025-26; each is an independent annual aggregate. [Berry citrus reefer data](https://data.mendeley.com/datasets/mvr7m6mcgp/2), DOI 10.17632/mvr7m6mcgp.2, supplied six CSVs. [Zenodo cold-room record](https://zenodo.org/records/15130001), DOI 10.5281/zenodo.15130001, supplied nine preprocessed sensor files in ZIP and an action log. [Smoked catfish package data](https://data.mendeley.com/datasets/tvsw53j89z/1), DOI 10.17632/tvsw53j89z.1, supplied a measured two-treatment outcome CSV and source analysis script. [NOAA shelf-life report](https://repository.library.noaa.gov/view/noaa/34680) and an [Indian cold-chain case study](https://dmeo.gov.in/sites/default/files/2021-08/Package1_Fisheries_CaseStudy1.pdf) were saved for bounded reference.

Investigated [Hammond Dryad](https://datadryad.org/dataset/doi:10.5061/dryad.6708r), DOI 10.5061/dryad.6708r; its `Supplemental_1.xlsx` endpoint returned HTTP 403, and general food-microbe data would not validate fresh fish. [Gilthead sea bream 0/4/8/12 °C study](https://pmc.ncbi.nlm.nih.gov/articles/PMC9367857/) and [horse mackerel 4/20 °C study](https://pmc.ncbi.nlm.nih.gov/articles/PMC9391519/) were inspected; machine-readable source-level paired replicate data were not located in their articles. The [spectroscopy companion](https://zenodo.org/records/3237542) was inspected separately; its article supplement contained classifier probabilities rather than temperature × quality observations. Search and candidate limitations are recorded in `metadata/dataset_registry.csv`. No public Indian export series pairing product temperature with terminal spoilage was located.
''')
 md(REP/'scientific_sufficiency_report.md',f'''# Claim readiness

| Planned claim | Verdict | Evidence and upgrade |
|---|---|---|
| Freshness classification on measured experiments | **BLOCKED** | {len(sensor):,} DaFiF gas readings and {counts['trout_sensor_rows']:,} trout sensor points, but outcomes were measured on separate fish in both studies. Trout adds 21 individual TVC observations, yet their fillets have no paired sensor records. Obtain specimen/lot-matched outcomes and identities. Ecological day-level proxy analysis can be labeled exploratory only. |
| Species/product-specific temperature-driven spoilage forecast for chilled DaFiF fish | **BLOCKED** | No temperature series in DaFiF. Trout is nominally stored at one 4 °C treatment; its chamber temperature is a measurement condition. Smoked catfish has two temperature ranges and measured outcomes, but another species/state; cannot transfer kinetics. Obtain fresh finfish multi-temperature replicate quality trajectories. |
| End-to-end India→EU stage simulation | **CONDITIONALLY READY** | MPEDA context, Indian operational case study and nonfish proxy traces permit explicitly assumed scenarios; route event logs and measured temperatures are absent. |
| Ranking stages under interventions and uncertainty | **CONDITIONALLY READY** | Can rank modeled sensitivity after a specified assumed thermal model; real operational risk ranking needs observed stage histories and calibrated fish kinetics. |
| Predictive reliability on independent real export journeys | **BLOCKED** | No independent paired Indian shipment temperature and endpoint quality records. |
| Chilled finfish branch | **CONDITIONALLY READY** | Data schema, sensory reference and scenario context prepared; measured predictive claims blocked. |
| Frozen fish/shrimp branches | **BLOCKED** | MPEDA aggregate trade totals are not kinetics. Separate product-specific observed calibration and validation needed. |
| Reproducible curation and lawful reuse | **READY for acquired CC BY datasets; CONDITIONAL for redistribution** | Original hashes, scripts, lineage and tests. Verify MPEDA/official report terms before republishing raw files; article full text carries publisher rights. |

Ready development activities: exploratory DaFiF sensor feature analysis, descriptive expert-score trajectories, MPEDA context plots, transparent simulation framework and proxy thermal pattern exploration. `model_ready_freshness` and `model_ready_thermal` are intentionally absent because their scientific linkage gates fail. No simulated or ecological-label score should be described as field validation.
''')
 md(REP/'coverage_matrix.md',f'''# Coverage

The machine-readable grid is `metadata/coverage_matrix.csv`: three DaFiF common-name categories × 11 ice-storage days in Indonesia and rainbow trout fillets × seven days at nominal 4 °C. Neither study has specimen-matched sensor and measured quality outcomes or fish-product temperature trajectories. Trout has 21 TVC values on a distinct destructive subset and 59 longitudinal sensor fillets. The smoked-catfish experiment spans nominal refrigerated 4–5 °C and ambient 25–30 °C, 0/30/60/90 days, across three packages and seven outcomes; it is not a fresh-fish calibration. MPEDA item, market and port grains are annual Indian totals. Its FY2025-26 item table reports 13,056.73922 metric tonnes of broad `CHILLED ITEMS`; its separate market table reports 297,517.86592 metric tonnes to the `EUROPEAN UNION` across all items. Those marginals cannot establish chilled-finfish exports to the EU. Berry covers citrus reefer package positions, while Zenodo covers a generic cold room. Independent India→EU fish shipment and terminal quality coverage is zero.
''')
 md(REP/'blocked_data_requests.md','''# Field data acquisition protocol and unsent request templates

## Required paired study

Recruit Indian chilled-finifish exporters and their receiving EU laboratories through MPEDA/EIC or direct research agreements. For each real lot/shipment collect: a stable anonymized shipment and lot ID; scientific species; whole/fillet and ice/packaging state; harvest and processing times; route, stage start/end and handling events; logger model, calibration, placement and synchronized UTC timestamps; product core/surface and ambient °C at preferably ≤15-minute cadence; ice replenishment and reefer setpoint; delays and refrigeration failures; pre-departure and destination sensory score by a documented species-specific method plus microbial TVC and TVB-N/TMA-N when appropriate, units, detection limits, assay laboratory, biological replicate IDs, and blind assessment. Keep specimen/lot linkage and source permissions. Record exclusions and loss to follow-up. These are planning fields, not existing observations.

Plan sample size with a pilot across routes, seasons, exporters, temperature excursions and quality classes; calculate required independent lots/shipments from anticipated event rate and target confidence interval, then reserve entire exporters/routes or later shipments for external testing. Repeated logger points within a shipment do not increase independent sample size. Obtain exporter consent, appropriate data-sharing agreements, privacy review if personnel/location data are included, and permissions for quality samples and cross-border data transfer.

## Draft message to MPEDA/EIC/export partners (do not send)

Subject: Research request for anonymized chilled-finifish export temperature and quality records

We are preparing an academic study of Indian seafood export cold chains. Could your organization provide anonymized shipment/lot-linked logger time series, handling stage and delay events, species/product state, and paired dispatch/arrival quality measurements with assay methods and units? We would agree scope, security, retention, redistribution and publication permissions before access. Aggregate MPEDA statistics are already used only as context. We can share an exact field schema and proposed pilot protocol.

## Draft message to DaFiF authors (do not send)

Subject: DaFiF specimen identity, Table 3 score scale and sensor-count clarification

We curated the 63 public sensor workbooks and found 27,120 paired rows versus Table 1's 27,123 stated per-sensor total. Can you clarify the three-row discrepancy, the score 0 in Table 3 despite the stated 1–9 scale, whether gas readings can be linked to individual sensor fish, and whether assessed organoleptic fish have independent IDs? The local files include one Tongkol Sesi2 filename in a Session 1 folder. We would cite any clarification and preserve your distinction between fish cohorts.

## Draft message to fresh-fish study authors (do not send)

Subject: Request for replicate-level fish temperature × quality observations

For an academic temperature-dependent freshness model, could you share deidentified per-fish or per-lot temperature, storage duration, species/product condition, packaging, microbial/sensory/biochemical measurements, replicate and batch IDs, and calibration uncertainty behind the published multi-temperature study? We seek a data-use agreement and will not redistribute restricted raw files.

## Draft message to rainbow trout dataset authors (do not send)

Subject: Original-fish ID structure and independently paired quality in Zenodo 23600663

We extracted the CC BY 4.0 tabular members from your v4 archive and preserved the distinction between 59 sensor-monitored fillets and 21 separately assayed fillets. Could you confirm how filename components map to the 20 original fish, whether any direct paired sensor/TVC assays exist outside the release, and how the daily mean TVC embedded in sensor CSVs was rounded? We will keep day-level classes as proxy labels unless a genuine specimen link is documented.
''')
 md(REP/'final_handoff.md',f'''# Data handoff

Install Python 3.11+ and `pip install -r requirements.txt`. Then run `python -m src.data_pipeline.cli fetch --all`, `python -m src.data_pipeline.cli build --all`, `python -m src.data_pipeline.cli validate --all`, `python -m src.data_pipeline.cli report --all`, and `python -m pytest tests/data_pipeline -q`. On this Windows workspace the ready interpreter is `.venv/Scripts/python.exe`.

Curated Parquet tables: {', '.join(f'`{k}` ({len(v):,})' for k,v in tables.items())}. Additional `coldroom_actions_proxy` has {counts['coldroom_event_rows']} rows. CSV samples are alongside each Parquet file. `metadata/data_dictionary.csv` gives types, nullability and units; `column_lineage.csv`, `source_manifest.json`, `checksums.sha256` and `dataset_registry.csv` give audit paths. Proposed exploratory day-group roles are in `split_manifest.csv`, but unknown repeated fish IDs prevent a specimen-independent evaluation claim.

Scope for further development: scenario-driven chilled finfish, with DaFiF common-name categories as Indonesian ice-storage analogues, a separate rainbow trout 4 °C cohort, and MPEDA as India context. Trout's 21 measured TVC results come from other fillets than its gas-sensor cohort. Species names for DaFiF, actual routes and durations, product temperatures and deterioration kinetics must be supplied or treated as assumptions. For the primary study, measured-label ML and thermal calibration are blocked; independent Indian field reliability is blocked. Smoked catfish is a separate measured experimental branch. Frozen exports and shrimp require their own models. See scientific sufficiency and blocked requests for upgrade conditions.
''')
 print(json.dumps({'status':'reported','files':len(files),'counts':counts,'local_comparison':local},indent=2))
