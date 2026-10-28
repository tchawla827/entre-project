"""Read selected public ZIP members through ordinary HTTP byte ranges."""
from collections import OrderedDict
import io, requests, zipfile, json, time
from pathlib import Path

class RangeFile(io.RawIOBase):
 def __init__(self,url,chunk_size=1024*1024):
  self.url=url;self.chunk_size=chunk_size;self.pos=0;self.cache=OrderedDict();self.session=requests.Session()
  r=self.session.head(url,timeout=90,allow_redirects=True);r.raise_for_status()
  self.size=int(r.headers['content-length'])
 def readable(self):return True
 def seekable(self):return True
 def tell(self):return self.pos
 def seek(self,offset,whence=0):
  self.pos=offset if whence==0 else self.pos+offset if whence==1 else self.size+offset
  if self.pos<0:raise ValueError('negative seek')
  return self.pos
 def read(self,n=-1):
  if n<0:n=self.size-self.pos
  if n==0 or self.pos>=self.size:return b''
  end=min(self.pos+n,self.size);pieces=[]
  while self.pos<end:
   index=self.pos//self.chunk_size
   if index not in self.cache:
    start=index*self.chunk_size;last=min(start+self.chunk_size,self.size)-1
    for attempt in range(5):
     try:
      r=self.session.get(self.url,headers={'Range':f'bytes={start}-{last}'},timeout=90)
      if r.status_code==206 and len(r.content)==last-start+1:break
      raise IOError(f'Range status {r.status_code}, bytes {len(r.content)}')
     except Exception:
      if attempt==4:raise
      time.sleep(2**attempt)
    self.cache[index]=r.content
    if len(self.cache)>8:self.cache.popitem(last=False)
   block=self.cache[index];begin=self.pos-index*self.chunk_size;take=min(end-self.pos,len(block)-begin)
   pieces.append(block[begin:begin+take]);self.pos+=take
  return b''.join(pieces)

if __name__=='__main__':
 d=json.loads(Path('data/raw/discovery/trout_retry.bin').read_text())
 with zipfile.ZipFile(RangeFile(d['files'][0]['links']['self'])) as z:
  rows=[{'name':m.filename,'size':m.file_size,'compressed_size':m.compress_size} for m in z.infolist()]
  Path('metadata/trout_zip_inventory.json').write_text(json.dumps(rows,indent=2))
  print('members',len(rows),'selected',json.dumps([x for x in rows if x['name'].lower().endswith(('.csv','.xlsx','.json','.txt','.md'))][:100],indent=2))
