from pathlib import Path
import json
import os
import shutil
import urllib.request
import psutil

root=Path(__file__).resolve().parents[1]
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-ui310-private'
launch=json.loads((private/'LAUNCH.json').read_text(encoding='utf-8'))
app=psutil.Process(launch['app'])
assert abs(app.create_time()-launch['appCreateTime'])<.01
assert Path(app.exe()).resolve()==(root/'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.exe').resolve()
with urllib.request.urlopen('http://127.0.0.1:49955/slots',timeout=5) as response:
    assert not any(row['is_processing'] for row in json.load(response)), 'Owner/backend busy'
if (private/'turn-audit.jsonl').exists():
    assert not (private/'turn-audit.jsonl').read_text(encoding='utf-8').strip(), 'New owner turns: preserve conversation before stopping'
compose=[json.loads(line) for line in (private/'compose-audit.jsonl').read_text(encoding='utf-8').splitlines()]
assert all(row.get('trace')=='t0' for row in compose), 'New activity: do not stop'
snapshot=private.parent/'C03-ui310-snapshot311'
snapshot.mkdir(exist_ok=False)
for name in ['LAUNCH.json','launch.log','compose-audit.jsonl','turn-audit.jsonl','raw-replies.jsonl','shell-trace.jsonl']:
    if (private/name).exists():
        shutil.copy2(private/name,snapshot/name)
children=app.children(recursive=True)
assert 101140 not in [p.pid for p in children]
owned=[{'pid':p.pid,'createTime':p.create_time(),'exe':p.exe()} for p in [app,*children]]
app.terminate()
psutil.wait_procs([app],timeout=8)
for child in reversed(children):
    try:
        child.terminate()
    except psutil.NoSuchProcess:
        pass
psutil.wait_procs(children,timeout=8)
out=root/'artifacts/comprobaciones/C03/astra-person-reference311'
(out/'STOP310.json').write_text(json.dumps({'snapshot':str(snapshot),'owned':owned},indent=2)+'\n',encoding='utf-8')
print('UI310 had no owner turns; logs preserved; verified owned tree stopped for integrated311.')

