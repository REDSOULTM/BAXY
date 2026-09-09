"""Pin and download the stable release backend; never touch the registered runtime."""
from pathlib import Path
from datetime import datetime, timezone
import concurrent.futures
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import urllib.request
import zipfile

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03/astra-backend-audit448'
out.mkdir(exist_ok=False)
target=Path('D:/BAXYRuntime/assets/llama-v0.4.0-b10809-cuda12.4')
downloads=Path('D:/BAXYRuntime/assets/downloads/C03-backend448')
assert not target.exists() and not downloads.exists()
def get(url):
    request=urllib.request.Request(url,headers={'User-Agent':'BAXY-C03-backend-audit','Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(request,timeout=45) as stream:return json.load(stream)
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def write(name,value):
    (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
initial=sha(manifest)
prereg={'utc':datetime.now(timezone.utc).isoformat(),'owner_request':'Check actual llama.cpp and newer fixes across tested models; new downloads explicitly allowed. Continue full C03, no registration on download.',
 'baseline':{'version':'b9980','commit':'8014d2cf9','server_sha256':sha(Path('D:/BAXYRuntime/assets/llama-b9980-cuda12.4/llama-server.exe'))},
 'candidate':{'stable':'v0.4.0','binary_tag':'b10809','cuda':'12.4','target':str(target)},
 'hardware':'NVIDIA GeForce RTX3060 Laptop6GiB; driver581.57. BAXY ceiling remains4GiB, not the card capacity.',
 'method':'Fetch official stable/nightly metadata and bounded commit titles from b9980 to b10809. Download official WinCUDA12.4 binaries and matching runtime zip with API sha256 verification; extract only inside new target. No source changes, no manifest/profile promotion, no models during audit. Native comparison is separate, with fixed payloads/model/parameters and measured resources.',
 'manifest_sha256':initial}
write('PREREG.json',prereg)
api='https://api.github.com/repos/ggml-org/llama.cpp/'
stable=get(api+'releases/tags/v0.4.0');release=get(api+'releases/tags/b10809')
write('STABLE_RELEASE.json',stable)
write('BINARY_RELEASE.json',release)
old=get(api+'releases/tags/b9980')
recent=get(api+'releases?per_page=8')
write('RECENT_RELEASES.json',[{k:r.get(k) for k in ['tag_name','published_at','prerelease','html_url','body']} for r in recent])
comparison=get(api+'compare/b9980...b10809?per_page=100&page=1')
pages=math.ceil(comparison['total_commits']/100)
assert pages<=16,('unexpected comparison size',pages)
commits=list(comparison['commits'])
def get_page(page):return get(api+f'compare/b9980...b10809?per_page=100&page={page}')['commits']
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    for group in pool.map(get_page,range(2,pages+1)):commits.extend(group)
assert len(commits)==comparison['total_commits']
rows=[{'sha':c['sha'],'date':c['commit']['committer']['date'],'title':c['commit']['message'].splitlines()[0],'url':c['html_url']} for c in commits]
write('COMMITS.json',{'from':'b9980','to':'b10809','total':len(rows),'commits':rows})
pattern=re.compile(r'gemma|qwen|phi.?4|granite|gdn|recurrent|kv.cache|repack|ram peak|chat.*(?:fix|template)|parser|reasoning|sampling',re.I)
relevant=[r for r in rows if pattern.search(r['title'])]
write('RELEVANT_COMMITS.json',relevant)
selected=[]
for name in ['llama-b10809-bin-win-cuda-12.4-x64.zip','cudart-llama-bin-win-cuda-12.4-x64.zip']:
    a=next(a for a in release['assets'] if a['name']==name)
    assert (a.get('digest') or '').startswith('sha256:')
    selected.append({k:a[k] for k in ['name','size','digest','browser_download_url']})
write('SELECTED_ASSETS.json',selected)
assert shutil.disk_usage(target.parent).free>sum(a['size'] for a in selected)*4
downloads.mkdir();target.mkdir()
target_resolved=target.resolve()
for a in selected:
    archive=downloads/a['name']
    print(json.dumps({'stage':'download','name':a['name'],'bytes':a['size']}),flush=True)
    request=urllib.request.Request(a['browser_download_url'],headers={'User-Agent':'BAXY-C03-backend-audit'})
    with urllib.request.urlopen(request,timeout=60) as stream, archive.open('xb') as sink:
        shutil.copyfileobj(stream,sink,1024*1024)
    assert archive.stat().st_size==a['size']
    assert sha(archive)==a['digest'].removeprefix('sha256:')
    with zipfile.ZipFile(archive) as zip_file:
        for member in zip_file.infolist():
            destination=(target/member.filename).resolve()
            assert destination.is_relative_to(target_resolved),member.filename
            if member.is_dir():destination.mkdir(parents=True,exist_ok=True);continue
            destination.parent.mkdir(parents=True,exist_ok=True)
            data=zip_file.read(member)
            if destination.exists():assert sha(destination)==hashlib.sha256(data).hexdigest(),member.filename
            else:destination.write_bytes(data)
    print(json.dumps({'stage':'verified_extracted','name':a['name']}),flush=True)
servers=list(target.rglob('llama-server.exe'));assert len(servers)==1
server=servers[0]
version=subprocess.run([str(server),'--version'],capture_output=True,text=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
assert version.returncode==0
version_text=version.stdout+version.stderr
help_result=subprocess.run([str(server),'--help'],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
assert help_result.returncode==0
(out/'HELP.txt').write_text(help_result.stdout+help_result.stderr,encoding='utf-8',newline='\n')
assert sha(manifest)==initial
result={'baseline_release':{'tag':old['tag_name'],'published_at':old['published_at']},'candidate_release':{'tag':stable['tag_name'],'published_at':stable['published_at']},
 'server':str(server),'server_sha256':sha(server),'version':version_text.strip(),'commits_compared':len(rows),'relevant_titles':len(relevant),'manifest_unchanged':True,'promoted':False,
 'runtime_files':[{'path':str(p.relative_to(target)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in target.rglob('*.dll')]}
write('RESULT.json',result)
write('PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
print(json.dumps({k:v for k,v in result.items() if k!='runtime_files'},ensure_ascii=True),flush=True)
