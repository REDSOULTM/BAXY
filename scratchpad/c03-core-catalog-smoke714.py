"""Check that the repaired real Core publishes a verified, nonempty catalog."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time

import psutil

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-core-catalog-smoke714'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-core-catalog-smoke714-private'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
write=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not out.exists() and not private.exists()
prior=json.loads((base/'astra-fixture-startup-probe713/RESULT.json').read_text())
assert prior['ready']==50 and prior['failed_startups']==0 and prior['fixture_restored'] and prior['temporary_helper_removed']
assert not any(p.info['name'] and p.info['name'].lower() in {'testhost.exe','baxy-core.exe','llama-server.exe'} for p in psutil.process_iter(['name']))
core=root/'tests/Baxy.Integration.Tests/bin/Release/net10.0-windows10.0.19041.0/baxy-core.exe'
out.mkdir();private.mkdir()
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'method':'One actual Core, fresh private data root, no requests/LLM. Require hello within10s after Process.Start, exact PID and application catalog verified,complete and nonempty. This detects a fast startup caused by fail-closed empty inventory; it does not claim every one of713 starts had an identical inventory.',
    'core_files':{name:sha(core.parent/name) for name in ['baxy-core.exe','baxy-core.dll','Baxy.Providers.Windows.dll']},'coverage_added':0})
first=[];ready=threading.Event()
with (private/'stderr.log').open('wb') as errors:
    proc=subprocess.Popen([str(core)],cwd=core.parent,env=dict(os.environ,BAXY_DATA_DIR=str(private/'data')),
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=errors,creationflags=subprocess.CREATE_NO_WINDOW)
    started=time.monotonic()
    def read():
        first.append(proc.stdout.readline(1_048_576));ready.set()
    reader=threading.Thread(target=read,daemon=True);reader.start()
    timely=ready.wait(10)
    elapsed=time.monotonic()-started
    hello={}
    try:
        if first:
            (private/'hello.json').write_bytes(first[0]);hello=json.loads(first[0])
    finally:
        proc.stdin.close()
        try:proc.wait(timeout=10)
        except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
        reader.join(timeout=1);proc.stdout.close()
catalog=hello.get('applicationCatalog',{})
result={'utc':datetime.now(timezone.utc).isoformat(),'hello_within10s':timely,'seconds':elapsed,
    'hello_type':hello.get('type'),'pid_matches':hello.get('pid')==proc.pid,
    'application_catalog':{'verified':catalog.get('verified'),'complete':catalog.get('complete'),'names_count':len(catalog.get('names',[]))},
    'clean_exit_code':proc.returncode,'private_hello_sha256':sha(private/'hello.json') if (private/'hello.json').exists() else None,
    'model_inference':False,'coverage_added':0,'goal_complete':False}
write(out/'RESULT.json',result)
print(json.dumps(result),flush=True)
assert timely and elapsed<=10 and hello.get('type')=='hello' and hello.get('pid')==proc.pid
assert catalog.get('verified') is True and catalog.get('complete') is True and len(catalog.get('names',[]))>0
assert proc.returncode==0
