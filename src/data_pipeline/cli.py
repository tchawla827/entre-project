"""Rebuild curated observed data. No synthetic rows or class labels are created."""
import argparse, hashlib, json, re, zipfile
from pathlib import Path
from datetime import date
import pandas as pd
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[2]
RAW=ROOT/'data/raw'; CUR=ROOT/'data/curated'; META=ROOT/'metadata'; REP=ROOT/'reports/data'
SOURCE='https://pmc.ncbi.nlm.nih.gov/articles/PMC11528684/'
def write_table(df,name):
 CUR.mkdir(parents=True,exist_ok=True)
 df.to_parquet(CUR/(name+'.parquet'),index=False)
 df.head(100).to_csv(CUR/(name+'_sample.csv'),index=False)
 return len(df)
def filehash(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def path_for(f): return RAW/'dafif_official'/(f['id']+'_'+f['filename'])
def sensor_table():
 inv=json.loads((META/'dafif_official_inventory.json').read_text())
 folders={f['id']:f for f in inv['folders']}; frames=[]; groups=[]
 for f in inv['files']:
  if not f['filename'].lower().endswith('.xlsx'): continue
  p=path_for(f)
  if not p.exists(): raise FileNotFoundError(f'Official source missing: {p}; run fetch first')
  if filehash(p)!=f['content_details']['sha256_hash']: raise ValueError(f'Official checksum mismatch: {p}')
  parts=[]; fid=f['folder_id']
  while fid in folders:
   folder=folders[fid];parts.append(folder['name']);fid=folder.get('parent_id')
  parts=parts[::-1]
  if len(parts)!=3: raise ValueError(f'Unexpected folder path: {parts}')
  day=int(parts[0].split()[1]);session=int(parts[1].split()[1]);species=parts[2]
  x=pd.read_excel(p)
  required={'Date','Time','MQ1','TGS1'}
  if set(x)!=required: raise ValueError(f'{p}: fields {list(x)}')
  source_date=pd.to_datetime(x['Date'],errors='coerce')
  source_time=x['Time'].astype(str)
  timestamps=pd.to_datetime(source_date.dt.strftime('%Y-%m-%d')+' '+source_time,errors='coerce')
  if timestamps.isna().any(): raise ValueError(f'{p}: unparseable timestamps')
  if not timestamps.is_monotonic_increasing: raise ValueError(f'{p}: nonmonotonic time')
  g=pd.DataFrame({'observation_id':[f['id']+':'+str(i+2) for i in range(len(x))],
   'source_id':'dafif_official_v1','source_file':f['filename'],'source_file_id':f['id'],
   'source_row':[i+2 for i in range(len(x))], 'recording_group_id':f['id'],
   'fish_type_source':f['filename'].split('(')[-1].split('Sesi')[0].split(')')[0],
   'species_common':species,'storage_day_one_based':day,'storage_age_days':day-1,
   'session_number':session,'date_source':x['Date'].astype(str),'time_source':source_time,
   'local_timestamp':timestamps.astype(str),
   'mq135_raw':pd.to_numeric(x['MQ1'],errors='coerce'),
   'tgs2602_raw':pd.to_numeric(x['TGS1'],errors='coerce')})
  if g[['mq135_raw','tgs2602_raw']].isna().any().any(): raise ValueError(f'{p}: nonnumeric sensor values')
  g['elapsed_seconds']=(timestamps-timestamps.iloc[0]).dt.total_seconds().to_numpy()
  for col in ['mq135_raw','tgs2602_raw']:
   g[col+'_delta']=g[col].diff()
   g[col+'_roll_mean_10']=g[col].rolling(10,min_periods=1).mean()
   g[col+'_roll_std_10']=g[col].rolling(10,min_periods=2).std()
  g['measurement_unit']='raw instrument output; physical calibration unavailable'
  g['product_state']='ice_stored_whole_fish'
  g['provenance_type']='observed'
  g['timestamp_timezone']='unknown_source_local'
  g['fish_or_lot_id']=pd.NA
  g['product_temperature_c']=pd.NA
  g['stage_id']=pd.NA
  g['filename_session_conflict']=bool(re.search(r'Sesi\s*([12])',f['filename'],flags=re.I) and int(re.search(r'Sesi\s*([12])',f['filename'],flags=re.I).group(1))!=session)
  groups.append({'recording_group_id':f['id'],'file':f['filename'],'day':day,'session':session,'species':species,'rows':len(g),'filename_session_conflict':bool(g['filename_session_conflict'].iloc[0])})
  frames.append(g)
 df=pd.concat(frames,ignore_index=True)
 if df.observation_id.duplicated().any(): raise ValueError('Duplicate sensor IDs')
 write_table(df,'fish_sensor_observations')
 pd.DataFrame(groups).to_csv(META/'recording_groups.csv',index=False)
 return df,pd.DataFrame(groups)

def sensory_table():
 xml=(RAW/'discovery/dafif_article.bin').read_bytes()
 t=BeautifulSoup(xml,'xml').find('table-wrap',id='tbl0003')
 if not t: raise ValueError('DaFiF article Table 3 missing')
 rows=[]; day=None
 for idx,tr in enumerate(t.find('tbody').find_all('tr'),start=1):
  cells=[c.get_text(' ',strip=True) for c in tr.find_all('td')]
  if len(cells)==19: cells=['']+cells
  if len(cells)!=20: raise ValueError(f'Table 3 row {idx}: {len(cells)} cells')
  if cells[0]: day=int(cells[0])
  session=int(cells[1]); vals=cells[2:]
  for j,species in enumerate(['Mackerel','Tilapia','Tuna']):
   six=vals[j*6:(j+1)*6]
   if all(v=='-' for v in six): continue
   for criterion,value in zip(['eyes','gills','body_surface_mucus','meat','smell','body_texture'],six):
    if value=='-': continue
    score=int(value)
    if not 0<=score<=9: raise ValueError(f'Unexpected sensory score {value}')
    rows.append({'assessment_id':f'dafif_table3_r{idx}_{species}_{criterion}',
      'source_id':'dafif_article_table3','source_table':'Table 3','source_table_row':idx,
      'species_common':species,'storage_day_one_based':day,'storage_age_days':day-1,
      'session_number':session,'criterion':criterion,'sensory_score':score,
      'source_scale':'SNI 2729:2013 referenced; article table includes score 0 although Table 2 lists 1-9',
      'expert_fish_id':pd.NA,'biological_replicate_id':pd.NA,'sensor_fish_id':pd.NA,
      'link_to_sensor':'ecological_species_day_session_only',
      'provenance_type':'observed_on_separate_expert_fish','source_url':SOURCE})
 df=pd.DataFrame(rows);write_table(df,'freshness_observed_labels')
 return df

def mpeda_table():
 files=sorted((RAW/'mpeda').glob('*.xlsx'))
 if len(files)<3: raise FileNotFoundError('Three MPEDA spreadsheets required; run fetch')
 summary=[]; records=[]
 unit={'Q':'metric_tonnes','V':'INR_crore','$':'USD_million','UV$':'USD_per_kg'}
 for p in files:
  x=pd.ExcelFile(p)
  for sheet in x.sheet_names:
   d=pd.read_excel(p,sheet_name=sheet,header=None,dtype=str)
   summary.append({'source_file':p.name,'sheet':sheet,'rows':len(d),'columns':len(d.columns),'preview':d.head(5).fillna('').values.tolist()})
   years=d.iloc[2,2:].tolist(); entity=None
   for rowi in range(3,len(d)):
    label=d.iat[rowi,0]; code=d.iat[rowi,1]
    if isinstance(label,str) and label.strip(): entity=label.strip()
    if code not in unit: continue
    if not entity: raise ValueError(f'{p}: measure without category row {rowi+1}')
    for col,year in enumerate(years,start=2):
     if not isinstance(year,str) or not re.fullmatch(r'\d{4}-\d{2}',year.strip()): continue
     raw=d.iat[rowi,col]
     if pd.isna(raw) or str(raw).strip() in {'','-'}: value=None
     else:
      value=pd.to_numeric(str(raw).replace(',',''),errors='coerce')
      if pd.isna(value): raise ValueError(f'MPEDA nonnumeric value {p}:{rowi+1}:{col+1}: {raw}')
     records.append({'statistic_id':f'{sheet}:{rowi+1}:{col+1}','aggregation_grain':sheet.lower()+'_financial_year',
      'dimension_type':sheet.lower(),'dimension_source':entity,'financial_year':year.strip(),
      'measure_code':code,'measure_unit':unit[code],'value':value,
      'source_file':p.name,'source_sheet':sheet,'source_excel_row':rowi+1,'source_excel_column':col+1,
      'provenance_type':'observed_aggregate','source_url':'https://mpeda.gov.in/?page_id=438'})
 (META/'mpeda_sheet_inspection.json').write_text(json.dumps(summary,indent=2,default=str))
 out=pd.DataFrame(records)
 if out.statistic_id.duplicated().any(): raise ValueError('Duplicate MPEDA key')
 write_table(out,'mpeda_export_statistics')
 return summary,out

def catfish_table():
 p=RAW/'external/catfish_storage_stability_package_level_data.csv'
 if not p.exists(): raise FileNotFoundError(p)
 raw=pd.read_csv(p); d=raw.loc[raw.meat.eq('Catfish')].copy()
 if len(raw)!=672 or len(d)!=336: raise ValueError('Smoked catfish source count changed')
 if not d.row_type.eq('measured').all(): raise ValueError('Unexpected catfish row type')
 d=d.rename(columns={'package':'package_type','storage':'storage_condition','time':'storage_age_days','outcome':'quality_outcome','value':'outcome_value','row_in_group':'replicate_index'})
 d.insert(0,'observation_id',['catfish:'+str(i+2) for i in d.index])
 d['species_common']='African catfish';d['species_scientific']='Clarias gariepinus'
 d['product_state']='smoked';d['source_id']='mendeley_tvsw53j89z_v1'
 d['temperature_min_c']=d.storage_condition.map({'Ambient':25.0,'Refrigerated':4.0})
 d['temperature_max_c']=d.storage_condition.map({'Ambient':30.0,'Refrigerated':5.0})
 d['temperature_precision']='reported_condition_range; not per-package logger'
 d['experimental_unit_note']='package-level post-baseline; processing run IDs not retained; day 0 shared baseline'
 d['is_inferential_postbaseline']=d.storage_age_days.gt(0)
 d['provenance_type']='observed_package_level'
 d['source_file']=p.name;d['source_url']='https://data.mendeley.com/datasets/tvsw53j89z/1'
 write_table(d,'fish_temperature_quality_experiments')
 return d

def trout_tables():
 base=RAW/'trout_selected'
 paths=sorted(base.rglob('sensors/*.csv'))
 if len(paths)!=210: raise ValueError(f'Expected 210 selected trout sensor CSVs, found {len(paths)}')
 frames=[]
 for p in paths:
  d=pd.read_csv(p,encoding='utf-8-sig')
  day=int(p.parent.parent.name.removeprefix('day'))
  fillet=p.stem[8:]
  if len(d)!=120 or not fillet.startswith('F'): raise ValueError(f'Unexpected trout sensor file {p}')
  temperature=next((c for c in d if c.startswith('Temperature')),None)
  tvc_col=next((c for c in d if c.startswith('TVC(')),None)
  required=['MQ3','MQ5','MQ9','MQ135','MQ137','Humidity(%)','Label']
  if not temperature or not tvc_col or not all(c in d for c in required): raise ValueError(f'Unexpected trout fields: {p}')
  rows=pd.DataFrame({'observation_id':[f'trout:{day}:{fillet}:{i}' for i in range(len(d))],
   'source_id':'zenodo_23600663_v4','source_member':p.relative_to(base).as_posix(),
   'storage_day_one_based':day,'storage_age_days':day-1,'fillet_id':fillet,
   'candidate_original_fish_id':fillet.rsplit('F',1)[-1],
   'fish_id_status':'inferred_from_filename_pattern_not_verified',
   'sample_index_in_session':range(len(d)),
   'mq3_adc':d.MQ3,'mq5_adc':d.MQ5,'mq9_adc':d.MQ9,'mq135_adc':d.MQ135,'mq137_adc':d.MQ137,
   'measurement_chamber_temperature_c':pd.to_numeric(d[temperature],errors='coerce'),
   'measurement_chamber_humidity_pct':pd.to_numeric(d['Humidity(%)'],errors='coerce'),
   'embedded_day_tvc_proxy_log10_cfu_g':pd.to_numeric(d[tvc_col],errors='coerce'),
   'embedded_day_label_proxy':d.Label.astype(str),
   'storage_temperature_protocol_c':4.0,'storage_temperature_status':'nominal_protocol_not_product_logger',
   'species_scientific':'Oncorhynchus mykiss','product_state':'refrigerated_fillet',
   'provenance_type':'observed_sensor_with_repeated_day_level_outcome_proxy'})
  frames.append(rows)
 sensor=pd.concat(frames,ignore_index=True)
 if sensor.observation_id.duplicated().any(): raise ValueError('Duplicate trout sensor ID')
 if not sensor[['mq3_adc','mq5_adc','mq9_adc','mq135_adc','mq137_adc']].apply(lambda s:s.between(0,1023).all()).all(): raise ValueError('Trout ADC out of bounds')
 tvc=pd.read_csv(base/'tvc_individual_measurements.csv')
 if len(tvc)!=21 or tvc.Microbiology_Sample_ID.duplicated().any(): raise ValueError('Trout microbiology count/identity changed')
 tvc=tvc.rename(columns={'Storage_Day':'storage_day_one_based','Microbiology_Sample_ID':'microbiology_sample_id',
  'TVC_CFU_g':'tvc_cfu_g','TVC_log10_CFU_g':'tvc_log10_cfu_g',
  'Analysis_Date':'analysis_date','Certificate_URL':'certificate_url'})
 tvc.insert(0,'outcome_id','trout_tvc:'+tvc.microbiology_sample_id.astype(str))
 tvc['species_scientific']='Oncorhynchus mykiss';tvc['product_state']='refrigerated_fillet'
 tvc['storage_age_days']=tvc.storage_day_one_based-1
 tvc['storage_temperature_protocol_c']=4.0
 tvc['fish_or_fillet_id_link_to_sensor']=pd.NA
 tvc['link_to_sensor']='storage_day_only_separate_biological_specimens'
 tvc['source_id']='zenodo_23600663_v4';tvc['provenance_type']='observed_individual_microbiology'
 matrix=pd.read_csv(base/'multimodal_fillet_day_matrix.csv')
 matrix['source_id']='zenodo_23600663_v4';matrix['provenance_type']='observed_availability_metadata'
 write_table(sensor,'trout_sensor_observations')
 write_table(tvc,'trout_microbiology_outcomes')
 write_table(matrix,'trout_modality_availability')
 return sensor,tvc,matrix

def proxy_thermal_tables():
 frames=[]
 for p in sorted((RAW/'external').glob('*C_*.csv')):
  d=pd.read_csv(p)
  if 'days' not in d: raise ValueError(f'{p}: missing days')
  d=d.melt(id_vars=['days'],value_vars=[c for c in d if c.endswith('_mean')],var_name='sensor_position_source',value_name='temperature_c')
  d['elapsed_hours']=pd.to_numeric(d['days'])*24
  d['source_file']=p.name;d['source_id']='berry_citrus_v2';d['commodity']='citrus'
  d['sensor_position_type']='source package position; verify paper for air/product interpretation'
  d['provenance_type']='observed_nonfish_proxy'
  frames.append(d[['source_id','source_file','commodity','sensor_position_source','sensor_position_type','elapsed_hours','temperature_c','provenance_type']])
 berry=pd.concat(frames,ignore_index=True)
 if berry.temperature_c.isna().all(): raise ValueError('Empty Berry temperatures')
 write_table(berry,'citrus_reefer_temperature_proxy')
 z=zipfile.ZipFile(RAW/'external/coldroom_preprocessed.zip');frames=[]
 for name in z.namelist():
  d=pd.read_csv(z.open(name),sep=';')
  if set(d)!={'Date','Time','Temperature','Humidity'}: raise ValueError(f'{name}: unexpected fields')
  ts=pd.to_datetime(d['Date']+' '+d['Time'],format='%d.%m.%Y %H:%M:%S',errors='coerce')
  if ts.isna().any() or not ts.is_monotonic_increasing: raise ValueError(f'{name}: invalid time')
  d=pd.DataFrame({'source_id':'zenodo_15130001','source_file':'coldroom_preprocessed.zip/'+name,
   'sensor_id':name.split('_')[0],'local_timestamp':ts.astype(str),
   'temperature_c':pd.to_numeric(d['Temperature'],errors='coerce'),
   'relative_humidity_pct':pd.to_numeric(d['Humidity'],errors='coerce'),
   'provenance_type':'observed_nonfish_coldroom_proxy'})
  frames.append(d)
 cold=pd.concat(frames,ignore_index=True)
 write_table(cold,'coldroom_temperature_proxy')
 actions=pd.read_csv(RAW/'external/coldroom_actions.csv',sep=';')
 actions['source_id']='zenodo_15130001';actions['provenance_type']='observed_nonfish_coldroom_event'
 write_table(actions,'coldroom_actions_proxy')
 return berry,cold,actions

def reference_tables():
 legal_url='https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=celex%3A32004R0853'
 reg=pd.DataFrame([
  {'reference_id':'eu853_fresh_ice','jurisdiction':'European Union','product_state':'fresh_fishery_products',
   'criterion':'temperature approaching that of melting ice','operator':'qualitative','value':pd.NA,'unit':'°C',
   'legal_location':'Annex III Section VIII Chapter VII; also Chapter III Part A',
   'consolidation_date':'2026-05-07','source_url':legal_url,'interpretation':'not a numeric universal spoilage threshold'},
  {'reference_id':'eu853_frozen_18','jurisdiction':'European Union','product_state':'frozen_fishery_products',
   'criterion':'temperature in all parts of product','operator':'<=','value':-18.0,'unit':'°C',
   'legal_location':'Annex III Section VIII Chapter VII; exception for whole frozen fish in brine for canning',
   'consolidation_date':'2026-05-07','source_url':legal_url,'interpretation':'not applicable to chilled fish; exceptions require full legal review'}])
 write_table(reg,'regulatory_reference')
 stage_names=['landing_and_icing','receiving_and_processing','cold_storage','road_to_export_hub',
  'port_handling_and_loading','international_refrigerated_transport','destination_inspection']
 routes=pd.DataFrame([{'stage_id':f'proposed_{i+1:02d}','stage_name':name,
  'origin_region':'India unspecified','destination_region':'EU unspecified',
  'duration_h':pd.NA,'product_temperature_c':pd.NA,'temporal_resolution':'none',
  'status':'proposed_scenario_stage_not_observed','source_url':'https://dmeo.gov.in/sites/default/files/2021-08/Package1_Fisheries_CaseStudy1.pdf',
  'source_applicability':'general Indian seafood cold-chain case context, not a measured India-EU route'}
  for i,name in enumerate(stage_names)])
 write_table(routes,'route_stage_catalog')
 evidence=pd.DataFrame([
  {'evidence_id':'smoked_catfish_ambient','species':'Clarias gariepinus','product_state':'smoked',
   'temperature_min_c':25.0,'temperature_max_c':30.0,'duration_min_days':0,'duration_max_days':90,
   'quality_endpoint':'7 reported outcomes; package-level CSV','parameter_value':pd.NA,'parameter_unit':pd.NA,
   'uncertainty':'temperature reported as range; processing-run ID unavailable',
   'status':'observed_outcomes_not_fitted_to_primary_chilled_model','doi':'10.17632/tvsw53j89z.1'},
  {'evidence_id':'smoked_catfish_refrigerated','species':'Clarias gariepinus','product_state':'smoked',
   'temperature_min_c':4.0,'temperature_max_c':5.0,'duration_min_days':0,'duration_max_days':90,
   'quality_endpoint':'7 reported outcomes; package-level CSV','parameter_value':pd.NA,'parameter_unit':pd.NA,
   'uncertainty':'temperature reported as range; processing-run ID unavailable',
   'status':'observed_outcomes_not_fitted_to_primary_chilled_model','doi':'10.17632/tvsw53j89z.1'}])
 write_table(evidence,'thermal_deterioration_evidence')
 return reg,routes,evidence

def build():
 META.mkdir(exist_ok=True); REP.mkdir(parents=True,exist_ok=True)
 sensor,groups=sensor_table(); labels=sensory_table(); mpeda,stats=mpeda_table();catfish=catfish_table();trout,trout_tvc,trout_matrix=trout_tables();berry,cold,actions=proxy_thermal_tables();reg,routes,evidence=reference_tables()
 counts={'sensor_rows':len(sensor),'recording_groups':len(groups),'sensory_criterion_rows':len(labels),
  'sensory_assessment_groups':labels.groupby(['species_common','storage_day_one_based','session_number']).ngroups,
  'mpeda_sheets':len(mpeda),'mpeda_statistic_rows':len(stats),'official_sensor_files':len(groups),
  'smoked_catfish_outcome_rows':len(catfish),'trout_sensor_rows':len(trout),'trout_individual_tvc_rows':len(trout_tvc),
  'trout_modality_rows':len(trout_matrix),'citrus_temperature_rows':len(berry),
  'coldroom_temperature_rows':len(cold),'coldroom_event_rows':len(actions),
  'regulatory_reference_rows':len(reg),'route_stage_catalog_rows':len(routes),'thermal_evidence_rows':len(evidence)}
 roles={day:('train_exploratory' if day<=7 else 'validation_exploratory' if day<=9 else 'test_exploratory') for day in range(1,12)}
 split=groups.copy();split['proposed_role']=split.day.map(roles)
 split['leakage_warning']='fish identity not recorded; likely same fish across days; split is NOT specimen-independent'
 split['eligibility']='blocked_for_measured_freshness_ML'
 split.to_csv(META/'split_manifest.csv',index=False)
 trout_split=trout[['fillet_id','candidate_original_fish_id','fish_id_status']].drop_duplicates().copy()
 trout_split['candidate_fish_number']=pd.to_numeric(trout_split.candidate_original_fish_id)
 trout_split['proposed_role']=trout_split.candidate_fish_number.map(lambda n:'train_exploratory' if n<=12 else 'validation_exploratory' if n<=16 else 'test_exploratory')
 trout_split['eligibility']='blocked_for_specimen_matched_quality_ML'
 trout_split['leakage_warning']='candidate original-fish ID inferred from filename; confirm with authors; TVC fish are separate'
 trout_split.to_csv(META/'trout_split_manifest.csv',index=False)
 raw_paths=sorted(list((RAW/'local').glob('*'))+list((RAW/'dafif_official').glob('*'))+
  list((RAW/'mpeda').glob('*'))+list((RAW/'external').glob('*'))+
  [p for p in (RAW/'trout_selected').rglob('*') if p.is_file()])
 (META/'checksums.sha256').write_text('\n'.join(f'{filehash(p)}  {p.relative_to(ROOT).as_posix()}' for p in raw_paths)+'\n')
 (META/'build_counts.json').write_text(json.dumps(counts,indent=2))
 return counts
def validate():
 counts=json.loads((META/'build_counts.json').read_text())
 sensors=pd.read_parquet(CUR/'fish_sensor_observations.parquet')
 labels=pd.read_parquet(CUR/'freshness_observed_labels.parquet')
 assert len(sensors)==counts['sensor_rows'] and sensors.observation_id.is_unique
 assert sensors.recording_group_id.nunique()==63
 assert sensors.groupby('recording_group_id').elapsed_seconds.min().eq(0).all()
 assert sensors.groupby('recording_group_id').elapsed_seconds.apply(lambda s:s.is_monotonic_increasing).all()
 assert sensors.groupby('recording_group_id').mq135_raw_delta.apply(lambda s:s.isna().sum()).eq(1).all()
 assert sensors.groupby('recording_group_id').tgs2602_raw_roll_std_10.apply(lambda s:s.isna().sum()).eq(1).all()
 assert (sensors[['mq135_raw','tgs2602_raw']]>=0).all().all()
 assert (labels.sensory_score.between(0,9)).all()
 assert labels.assessment_id.is_unique
 assert sensors['product_temperature_c'].isna().all() and sensors.fish_or_lot_id.isna().all()
 stats=pd.read_parquet(CUR/'mpeda_export_statistics.parquet')
 assert len(stats)==counts['mpeda_statistic_rows'] and stats.statistic_id.is_unique
 assert stats.aggregation_grain.str.endswith('_financial_year').all()
 catfish=pd.read_parquet(CUR/'fish_temperature_quality_experiments.parquet')
 assert len(catfish)==336 and catfish.observation_id.is_unique
 assert set(catfish.product_state)=={'smoked'} and set(catfish.storage_condition)=={'Ambient','Refrigerated'}
 assert catfish.loc[catfish.storage_age_days.eq(0),'is_inferential_postbaseline'].eq(False).all()
 trout=pd.read_parquet(CUR/'trout_sensor_observations.parquet')
 tvc=pd.read_parquet(CUR/'trout_microbiology_outcomes.parquet')
 assert len(trout)==25200 and trout.observation_id.is_unique and trout.fillet_id.nunique()==59
 assert len(tvc)==21 and tvc.outcome_id.is_unique
 assert set(trout.fillet_id).isdisjoint(set(tvc.microbiology_sample_id))
 assert tvc.fish_or_fillet_id_link_to_sensor.isna().all()
 for line in (META/'checksums.sha256').read_text().splitlines():
  expected,relative=line.split('  ',1)
  p=ROOT/relative
  if not p.exists() or filehash(p)!=expected: raise ValueError(f'Raw source integrity failure: {relative}')
 assert not (CUR/'model_ready_freshness.parquet').exists()
 assert not (CUR/'model_ready_thermal.parquet').exists()
 from src.data_pipeline.readiness import assess
 return {'status':'PASS','counts':counts,'scientific_readiness':assess()}
def main():
 parser=argparse.ArgumentParser();parser.add_argument('command',choices=['fetch','build','validate','report','all']);parser.add_argument('--all',action='store_true');a=parser.parse_args()
 if a.command=='fetch':
  from scripts.fetch_sources import main as fetch;fetch()
 elif a.command=='build': print(json.dumps(build(),indent=2))
 elif a.command=='validate': print(json.dumps(validate(),indent=2))
 elif a.command=='all':
  from scripts.fetch_sources import main as fetch
  from src.data_pipeline.report import main as report
  fetch();print(json.dumps(build(),indent=2));print(json.dumps(validate(),indent=2));report()
 else:
  from src.data_pipeline.report import main as report;report()
if __name__=='__main__': main()
