"""Download verified public source files once; preserve their original bytes."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import hashlib, json, time, requests, shutil
from bs4 import BeautifulSoup

ROOT=Path('data/raw'); ROOT.mkdir(parents=True,exist_ok=True)
def download(url,relative,expected=None):
 p=ROOT/relative; p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists() and p.stat().st_size>0:
  sha=hashlib.sha256(p.read_bytes()).hexdigest()
  if expected is None or sha==expected: return {'file':str(p),'bytes':p.stat().st_size,'sha256':sha,'cached':True,'url':url}
  raise ValueError(f'Existing file checksum mismatch: {p}')
 for attempt in range(4):
  try:
   r=requests.get(url,timeout=90,stream=True); r.raise_for_status()
   if 'text/html' in r.headers.get('content-type','').lower(): raise ValueError('HTML response for data file')
   tmp=p.with_suffix(p.suffix+'.part'); h=hashlib.sha256(); n=0
   with tmp.open('wb') as f:
    for chunk in r.iter_content(1024*1024): f.write(chunk);h.update(chunk);n+=len(chunk)
   if n==0: raise ValueError('empty download')
   if expected and h.hexdigest()!=expected: raise ValueError('sha256 mismatch')
   tmp.replace(p)
   return {'file':str(p),'bytes':n,'sha256':h.hexdigest(),'cached':False,'url':url}
  except Exception as e:
   if isinstance(e,requests.HTTPError) and e.response is not None and e.response.status_code in {400,401,403,404}: raise
   if attempt==3: raise
   time.sleep(2**attempt)

def inventory():
 fp=Path('data/raw/discovery/dafif_folders.json')
 if not fp.exists():
  r=requests.get('https://data.mendeley.com/public-api/datasets/vx4ptwk3pb/folders/1',timeout=60);r.raise_for_status();fp.parent.mkdir(parents=True,exist_ok=True);fp.write_bytes(r.content)
 d=json.loads(Path('data/raw/discovery/dafif_folders.json').read_text())
 folders=[{'id':'root','name':'Root','parent_id':None}]+d
 def query(f):
  u=f'https://data.mendeley.com/public-api/datasets/vx4ptwk3pb/files'
  r=requests.get(u,params={'folder_id':f['id'],'version':1,'$limit':1000},timeout=90);r.raise_for_status()
  return f['id'],r.json()
 with ThreadPoolExecutor(10) as pool:
  rows=list(pool.map(query,folders))
 files=[]
 for fid,items in rows:
  for item in items:
   item['folder_id']=fid; files.append(item)
 out={'folders':folders,'files':files}
 Path('metadata').mkdir(exist_ok=True)
 Path('metadata/dafif_official_inventory.json').write_text(json.dumps(out,indent=2))
 return out

def main():
 allfiles=[]
 discovery={'mpeda.bin':'https://mpeda.gov.in/?page_id=438',
  'dafif_article.bin':'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11528684/fullTextXML',
  'berry_inventory.bin':'https://data.mendeley.com/public-api/datasets/mvr7m6mcgp/files?folder_id=root&version=2',
  'catfish_inventory.json':'https://data.mendeley.com/public-api/datasets/tvsw53j89z/files?folder_id=root&version=1',
  'coldroom.bin':'https://zenodo.org/api/records/15130001'}
 for name,url in discovery.items():
  p=ROOT/'discovery'/name
  if not p.exists() or p.stat().st_size==0:
   p.parent.mkdir(parents=True,exist_ok=True)
   r=requests.get(url,timeout=60);r.raise_for_status();p.write_bytes(r.content)
 # Original local data are copied byte-for-byte into immutable raw storage.
 local=[Path('combined_dataset.csv')]+list(Path('Data_IIT2023150/Data/Dataset').glob('*.xlsx'))
 for p in local:
  dst=ROOT/'local'/p.name;dst.parent.mkdir(exist_ok=True)
  srcsha=hashlib.sha256(p.read_bytes()).hexdigest()
  if dst.exists() and hashlib.sha256(dst.read_bytes()).hexdigest()!=srcsha: raise ValueError(f'Raw copy drift: {dst}')
  if not dst.exists(): shutil.copyfile(p,dst)
  allfiles.append({'file':str(dst),'bytes':dst.stat().st_size,'sha256':srcsha,'url':p.resolve().as_uri()})
 inv=inventory()
 for f in inv['files']:
  name=f['filename'].lower()
  if name.endswith(('.csv','.xlsx','.xls')):
   try: allfiles.append(download(f['content_details']['download_url'],'dafif_official/'+f['id']+'_'+f['filename'],f['content_details']['sha256_hash']))
   except Exception as e: allfiles.append({'file':f['filename'],'error':str(e)})
 soup=BeautifulSoup(Path('data/raw/discovery/mpeda.bin').read_bytes(),'html.parser')
 for i,a in enumerate(a for a in soup.find_all('a') if 'DOWNLOAD FULL DATA' in a.get_text()):
  u=a['href']
  try: allfiles.append(download(u,'mpeda/'+u.rsplit('/',1)[-1]))
  except Exception as e: allfiles.append({'file':u,'error':str(e)})
 sources=[('hammond_supplement.xlsx','https://datadryad.org/downloads/file_stream/37448'),
  ('spectroscopy_supplement.xlsx','https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41598-020-68156-2/MediaObjects/41598_2020_68156_MOESM2_ESM.xlsx'),
  ('coldroom_overview.csv','https://zenodo.org/api/records/15130001/files/overview.csv/content'),
  ('coldroom_actions.csv','https://zenodo.org/api/records/15130001/files/experiment_actions.csv/content'),
  ('coldroom_preprocessed.zip','https://zenodo.org/api/records/15130001/files/Preprocessed.zip/content'),
  ('seabream_spectroscopy_code_experiment.zip','https://zenodo.org/api/records/3237542/files/code_experiment.zip/content'),
  ('noaa_shelf_life.pdf','https://repository.library.noaa.gov/view/noaa/34680/noaa_34680_DS1.pdf'),
  ('india_operations.pdf','https://dmeo.gov.in/sites/default/files/2021-08/Package1_Fisheries_CaseStudy1.pdf')]
 berry=json.loads(Path('data/raw/discovery/berry_inventory.bin').read_text())
 sources += [(f['filename'],f['content_details']['download_url']) for f in berry]
 catfish=json.loads(Path('data/raw/discovery/catfish_inventory.json').read_text())
 sources += [('catfish_'+f['filename'],f['content_details']['download_url']) for f in catfish]
 with ThreadPoolExecutor(8) as pool:
  futures={pool.submit(download,u,'external/'+n):n for n,u in sources}
  for fut in as_completed(futures):
   try: allfiles.append(fut.result())
   except Exception as e: allfiles.append({'file':futures[fut],'error':str(e)})
 try:
  from scripts.fetch_trout_selected import main as fetch_trout
  fetch_trout()
  allfiles += json.loads(Path('metadata/trout_selected_manifest.json').read_text())
 except Exception as e: allfiles.append({'file':'trout_selected_tabular_members','error':str(e)})
 Path('metadata/downloads.json').write_text(json.dumps(allfiles,indent=2))
 print('downloaded/cached',len([x for x in allfiles if 'sha256' in x]),'errors',len([x for x in allfiles if 'error' in x]),'official inventory',len(inv['files']))
 print(json.dumps([x for x in allfiles if 'error' in x],indent=2))
if __name__=='__main__': main()
