"""Escalate DTLN once from smallest128 to author's challenge512, same controls."""
from pathlib import Path
import hashlib
import json
import shutil
import urllib.request
import datetime as dt

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-dtln180'
out.mkdir(exist_ok=False)
folder=Path('D:/BAXYRuntime/experiments/voice/dtln180')
folder.mkdir(exist_ok=False)
previous=Path('D:/BAXYRuntime/experiments/voice/dtln179')
revision='9d24e128b4f409db18227b8babb343016625921f'
def get(url):
    with urllib.request.urlopen(url,timeout=60) as f:return f.read()
def save(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
save(out/'PREREG.json',{'utc':dt.datetime.now(dt.timezone.utc).isoformat(),'hypothesis':'Smallest128 fails mixed words179 at low CPU cost. Contrast author challenge512 once; no intermediate256 collection or VAD/gain tuning.',
 'difference':'Only published512 weights; same exact author process_file, sameLiteRT2.2.0 CPU1/XNNPACK, same five174 controls, same raw/normalizedParakeet window.',
 'revision':revision,'source':f'https://github.com/breizhn/DTLN-aec/tree/{revision}',
 'criteria':'Echo rejection, near-only and mixed word preservation, CPU cost below hop budget; no adoption from suppression alone. Still synthetic/offline, not physical/human acceptance.'})
downloads=[]
files=json.loads(get(f'https://api.github.com/repos/breizhn/DTLN-aec/contents/pretrained_models?ref={revision}'))
selected=[r for r in files if r['name'] in ['dtln_aec_512_1.tflite','dtln_aec_512_2.tflite']]
assert len(selected)==2
for row in selected:
    data=get(row['download_url'])
    assert hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()==row['sha']
    path=folder/row['name'];path.write_bytes(data)
    downloads.append({'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'gitBlob':row['sha'],'url':row['download_url']})
for name in ['run_aec.py','LICENSE','README.md']:
    shutil.copyfile(previous/name,folder/name)
    path=folder/name
    downloads.append({'path':str(path),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'copiedFrom':str(previous/name)})
save(out/'DOWNLOADS.json',downloads)
code=(root/'scratchpad/c03-evaluate179.py').read_text(encoding='utf-8')
code=code.replace('astra-dtln179','astra-dtln180').replace('voice/dtln179','voice/dtln180').replace('C03-dtln179-private','C03-dtln180-private').replace('dtln_aec_128_','dtln_aec_512_').replace('-dtln128.wav','-dtln512.wav')
code=code.replace("str(folder/'python')","'D:/BAXYRuntime/experiments/voice/dtln179/python'")
with (root/'scratchpad/c03-evaluate180.py').open('x',encoding='utf-8') as f:f.write(code)
print(json.dumps({'modelBytes':sum(r['bytes'] for r in downloads[:2]),'runtimeReused':str(previous/'python')}))
