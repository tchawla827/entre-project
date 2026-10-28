"""Source inspection, saved verbatim for reproducible extraction decisions."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests, json

URLS = {
 'dafif_inventory':'https://data.mendeley.com/public-api/datasets/vx4ptwk3pb/files?folder_id=root&version=1&$limit=1000',
 'berry_inventory':'https://data.mendeley.com/public-api/datasets/mvr7m6mcgp/files?folder_id=root&version=2&$limit=1000',
 'spectroscopy_api':'https://zenodo.org/api/records/3237542',
 'spectroscopy_supplement':'https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41598-020-68156-2/MediaObjects/41598_2020_68156_MOESM2_ESM.xlsx',
 'dafif_api':'https://data.mendeley.com/public-api/datasets/vx4ptwk3pb/versions/1',
 'dafif_files':'https://data.mendeley.com/public-api/datasets/vx4ptwk3pb/versions/1/files',
 'berry_api':'https://data.mendeley.com/public-api/datasets/mvr7m6mcgp/versions/2',
 'berry_files':'https://data.mendeley.com/public-api/datasets/mvr7m6mcgp/versions/2/files',
 'dafif_article':'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11528684/fullTextXML',
 'horse_mackerel_article':'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9391519/fullTextXML',
 'spectroscopy_article':'https://www.nature.com/articles/s41598-020-68156-2',
 'mpeda':'https://mpeda.gov.in/?page_id=438',
 'dryad':'https://datadryad.org/api/v2/datasets/doi:10.5061/dryad.6708r',
 'coldroom':'https://zenodo.org/api/records/15130001',
 'trout':'https://zenodo.org/api/records/23600663',
 'catfish':'https://data.mendeley.com/public-api/datasets/tvsw53j89z/versions/1/files',
 'eu853':'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02004R0853',
 'noaa':'https://repository.library.noaa.gov/view/noaa/34680/noaa_34680_DS1.pdf',
 'india_operations':'https://dmeo.gov.in/sites/default/files/2021-08/Package1_Fisheries_CaseStudy1.pdf',
}
def get(kv):
 k,u=kv
 p=Path('data/raw/discovery')/f'{k}.bin'
 if p.exists(): return {'id':k,'url':u,'status':'cached','bytes':p.stat().st_size,'path':str(p)}
 try:
  r=requests.get(u,timeout=60)
  p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(r.content)
  return {'id':k,'url':u,'status':r.status_code,'content_type':r.headers.get('content-type'),'bytes':len(r.content),'path':str(p)}
 except Exception as e: return {'id':k,'url':u,'error':str(e)}
if __name__=='__main__':
 results=list(ThreadPoolExecutor(8).map(get,URLS.items()))
 Path('metadata').mkdir(exist_ok=True)
 Path('metadata/discovery.json').write_text(json.dumps(results,indent=2))
 print(json.dumps(results,indent=2))
