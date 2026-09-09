from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import psutil

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03/astra-runtime287'
out.mkdir(exist_ok=False)
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-owner264-heap280'
assert hashlib.sha256((private/'TRANSCRIPT282.json').read_bytes()).hexdigest()=='9658a77505564ec1384e58aba91ed75d03b078f865182f94b6ecc3b0ee839ef6'
app=psutil.Process(84328)
assert abs(app.create_time()-1788820609.3516054)<0.01
assert Path(app.exe()).resolve()==(root/'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.exe').resolve()
children=app.children(recursive=True)
assert 101140 not in {p.pid for p in children}
server=next(p for p in children if p.pid==89232)
assert abs(server.create_time()-1788820621.7334836)<0.01
record={'utc':datetime.now(timezone.utc).isoformat(),'reason':'Owner finished264 and authorized continued goal/PC management. Complete UI transcript282 preserved and hash verified. Free old build/backend for integrated Fast and controlled registered-model comparison; questionnaire excluded.',
    'processes':[{'pid':p.pid,'created':p.create_time(),'name':p.name(),'ppid':p.ppid()} for p in [app,*children]]}
(out/'STOP_PREREG.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
# psutil Process identity protects against PID reuse. Stop only this owned tree.
for proc in [app,*children]:
    try:
        proc.terminate()
    except psutil.NoSuchProcess:
        pass
gone,alive=psutil.wait_procs([app,*children],timeout=5)
record.update(remaining=[p.pid for p in alive],questionnaireAlive=psutil.pid_exists(101140),ramAvailableMiB=psutil.virtual_memory().available/2**20)
(out/'STOP_RESULT.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in record.items() if k!='processes'}))
assert not alive
assert record['questionnaireAlive']
