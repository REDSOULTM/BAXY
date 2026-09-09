"""Stage the smallest published DTLN-AEC and one Windows LiteRT wheel privately."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import urllib.request
import zipfile

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03/astra-dtln179'
out.mkdir(exist_ok=False)
folder=Path('D:/BAXYRuntime/experiments/voice/dtln179')
folder.mkdir(exist_ok=False)
revision='9d24e128b4f409db18227b8babb343016625921f'
def request(url):
    with urllib.request.urlopen(url,timeout=60) as f:return f.read()
def save(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
save(out/'PREREG.json',{'utc':dt.datetime.now(dt.timezone.utc).isoformat(),'candidate':'Official DTLN-AEC128 (1.8M parameters), only smallest model; fixed author revision'+revision,
 'purpose':'Change strategy after Speex physical failure and default/low-gainAEC3 mixed-speech failure. Existing identical174 controls; local CPU only, no private upload, source/runtime unchanged.',
 'referenceImplementation':'run_aec.py at pinned author revision;16k mono,512window/128hop,two states,original FFT/mask/IFFT/overlap-add. Preserve startup and delay contract before integrating512frames.',
 'runtime':'ai-edge-litert2.2.0 CPython312 Windows x64; isolated extraction, no installation in registered environment; interpreter compatibility must be verified.',
 'criteria':'Near-only/mix content, silence and echo rejection with unchanged BAXY thresholds, CPU cost; native synthetic controls are not physical/human acceptance.'})
downloads=[]
files=json.loads(request(f'https://api.github.com/repos/breizhn/DTLN-aec/contents/pretrained_models?ref={revision}'))
chosen=[r for r in files if r['name'] in ['dtln_aec_128_1.tflite','dtln_aec_128_2.tflite']]
assert len(chosen)==2
for row in chosen:
    data=request(row['download_url'])
    assert hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()==row['sha']
    path=folder/row['name'];path.write_bytes(data)
    downloads.append({'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'gitBlob':row['sha'],'url':row['download_url']})
for name in ['LICENSE','README.md','run_aec.py']:
    url=f'https://raw.githubusercontent.com/breizhn/DTLN-aec/{revision}/{name}'
    data=request(url);path=folder/name;path.write_bytes(data)
    downloads.append({'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'url':url})
meta=json.loads(request('https://pypi.org/pypi/ai-edge-litert/2.2.0/json'))
row=next(r for r in meta['urls'] if r['filename']=='ai_edge_litert-2.2.0-cp312-cp312-win_amd64.whl')
data=request(row['url']);assert hashlib.sha256(data).hexdigest()==row['digests']['sha256']
path=folder/row['filename'];path.write_bytes(data)
downloads.append({'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'url':row['url']})
with zipfile.ZipFile(path) as z:
    for name in z.namelist():assert (folder/'python'/name).resolve().is_relative_to((folder/'python').resolve())
    z.extractall(folder/'python')
    interpreter_files=[name for name in z.namelist() if 'interpreter' in name.lower()]
save(out/'DOWNLOADS.json',downloads)
save(out/'RUNTIME_METADATA.json',{'requires_dist':meta['info']['requires_dist'],'interpreterFiles':interpreter_files})
print(json.dumps({'files':len(downloads),'modelsBytes':sum(r['bytes'] for r in downloads[:2]),'interpreterFiles':interpreter_files},indent=2))
