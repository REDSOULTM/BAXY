"""Compare the actual failed native selector with registered2507, no protocol changes."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.request
import psutil

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03/astra-selector-model292'
out.mkdir(exist_ok=False)
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-ui288-private'
snapshot=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-ui288-snapshot292'
snapshot.mkdir(exist_ok=False)
app=psutil.Process(57420)
assert abs(app.create_time()-1788827018.593568)<.01
assert Path(app.exe()).resolve()==(root/'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.exe').resolve()
with urllib.request.urlopen('http://127.0.0.1:58635/slots',timeout=5) as response:
    assert not any(item['is_processing'] for item in json.load(response))
audit=[json.loads(line) for line in (private/'turn-audit.jsonl').read_text(encoding='utf-8').splitlines()]
assert set(row['request_id'] for row in audit)=={'6','11'}, 'New interaction; preserve/review before managing app.'
for name in ['LAUNCH.json','launch.log','http-posts.jsonl','turn-audit.jsonl','compose-audit.jsonl','raw-replies.jsonl','shell-trace.jsonl']:
    if (private/name).exists():
        shutil.copy2(private/name,snapshot/name)
model=Path(r'D:\BAXYRuntime\experiments\models\qwen3-4b-instruct-2507-a06e946b\Qwen3-4B-Instruct-2507-Q4_K_M.gguf')
binary=Path(r'D:\BAXYRuntime\assets\llama-b9980-cuda12.4\llama-server.exe')
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()
assert sha(model)=='3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'
assert sha(manifest)=='13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
cases=[]
for folder in ['astra-abstain289','astra-abstain290']:
    cases += [row for row in json.loads((root/f'artifacts/comprobaciones/C03/{folder}/RESULT.json').read_text(encoding='utf-8')) if row['variant']=='before']
args=[str(binary),'-m',str(model),'--host','127.0.0.1','--port','57485','-ngl','99','-c','12288','-b','2048','-ub','256','-fa','on','-ctk','q8_0','-ctv','q8_0','-np','3','--jinja','--reasoning','off','--reasoning-budget','0','--cont-batching']
prereg={'utc':datetime.now(timezone.utc).isoformat(),'previousTurn':'progress: adopted284 verifiedUI/Fast; root native length reproduced288; rejected289-291 scope regressions change next action.',
    'method':'Same18 actual/frozen native AUTO payloads as289/290; only model changes from overrideQwen3.5 to registered2507. Same backend build/KV/ctx/batch/slots, no new prompt/descriptor/limits.287 compared prose only and cannot answer this root failure. Local, no effects; close controlledUI288 after exact log snapshot, then restore desktop separately.',
    'criteria':'Paris complete zero-effect selection with no truncation; retain expected authorized actions and no-effect scope cases. Do not promote on single case; identify existing failures and regressions individually.',
    'inheritance':'INVESTIGACION_FORMATO_Y_CLASIFICACION_C03: native-scope2507 was11/11 before downstream guard. Use same scoped controls and seven newer cases; evidence is not current integrated acceptance.',
    'hashes':{'model':sha(model),'binary':sha(binary),'manifest':sha(manifest)},'args':args,'cases':[row['case_id'] for row in cases],
    'snapshot':str(snapshot),'app':app.pid,'appCreated':app.create_time()}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
children=app.children(recursive=True)
assert 101140 not in {p.pid for p in children}
for proc in [app,*children]:
    try:
        proc.terminate()
    except psutil.NoSuchProcess:
        pass
gone,alive=psutil.wait_procs([app,*children],timeout=5)
assert not alive
log=(out/'server2507.log').open('wb')
process=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
(out/'PROCESS.json').write_text(json.dumps({'pid':process.pid,'owned':True})+'\n',encoding='utf-8')
results=[]
try:
    deadline=time.monotonic()+75
    while True:
        assert process.poll() is None
        try:
            with urllib.request.urlopen('http://127.0.0.1:57485/health',timeout=1) as response:
                if response.status==200:
                    break
        except Exception:
            if time.monotonic()>deadline:
                raise TimeoutError('Server readiness')
            time.sleep(.25)
    for row in cases:
        request=urllib.request.Request('http://127.0.0.1:57485/v1/chat/completions',data=json.dumps(row['payload'],ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
        started=time.monotonic()
        with urllib.request.urlopen(request,timeout=90) as response:
            response=json.load(response)
        choice=response['choices'][0]
        names=[call['function']['name'] for call in choice['message'].get('tool_calls') or []]
        result={'case_id':row['case_id'],'expected':row['expected'],'names':names,'operations':[name.removeprefix('baxy_').replace('__','.') for name in names],'finish':choice['finish_reason'],'seconds':round(time.monotonic()-started,3),'payload':row['payload'],'response':response}
        results.append(result)
        (out/'RESULT.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k not in ('payload','response')},ensure_ascii=True),flush=True)
finally:
    process.terminate()
    process.wait(timeout=10)
    log.close()
    (out/'STOP.json').write_text(json.dumps({'pid':process.pid,'exit':process.returncode,'utc':datetime.now(timezone.utc).isoformat(),'registrationUnchanged':sha(manifest)==prereg['hashes']['manifest'],'questionnaireAlive':psutil.pid_exists(101140)})+'\n',encoding='utf-8')
