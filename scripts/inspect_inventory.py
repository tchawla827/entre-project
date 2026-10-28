import json
d=json.load(open('metadata/dafif_official_inventory.json'))
fs={f['id']:f for f in d['folders']}
for x in [x for x in d['files'] if x['filename'].endswith('xlsx')][:15]:
 fid=x['folder_id']; parts=[]
 while fid in fs:
  folder=fs[fid];parts.append(folder['name']);fid=folder.get('parent_id')
 print(x['filename'],'/'.join(parts[::-1]))
