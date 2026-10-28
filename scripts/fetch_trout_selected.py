"""Extract only tabular members from the 21 GB public Zenodo ZIP via HTTP Range."""
import hashlib,json,zipfile
from pathlib import Path
from scripts.remote_zip import RangeFile

URL='https://zenodo.org/api/records/23600663/files/dataset.zip/content'
ROOT=Path('data/raw/trout_selected')
def main():
 ROOT.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(RangeFile(URL)) as z:
  chosen=[m for m in z.infolist() if m.filename.startswith('dataset/') and
   (m.filename.endswith('/sensors/'+m.filename.rsplit('/',1)[-1]) and m.filename.lower().endswith('.csv') and '/sensors/' in m.filename
    or m.filename in {'dataset/README.txt','dataset/tvc_individual_measurements.csv','dataset/multimodal_fillet_day_matrix.csv','dataset/image_exif_metadata.csv'})]
  rows=[]
  for i,m in enumerate(chosen,1):
   relative=Path(m.filename).relative_to('dataset')
   p=ROOT/relative;p.parent.mkdir(parents=True,exist_ok=True)
   if not p.exists(): p.write_bytes(z.read(m))
   if p.stat().st_size!=m.file_size or (zipfile.crc32(p.read_bytes())&0xffffffff)!=m.CRC: raise ValueError(f'CRC/size mismatch: {m.filename}')
   rows.append({'member':m.filename,'file':str(p),'bytes':p.stat().st_size,'zip_crc32':f'{m.CRC:08x}','sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
    'source_url':URL,'source_zip_size':21134589045,'source_zip_md5':'8a0868331fc041fafe82aa0ccf249938'})
   if i%30==0: print('extracted',i,'/',len(chosen),flush=True)
 Path('metadata/trout_selected_manifest.json').write_text(json.dumps(rows,indent=2))
 print('extracted selected',len(rows),'total bytes',sum(r['bytes'] for r in rows))
if __name__=='__main__':main()
