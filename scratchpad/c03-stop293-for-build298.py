"""Preserve owned development logs and stop only the verified UI293 tree."""
from pathlib import Path
import json
import os
import shutil
import urllib.request
import psutil

root = Path(__file__).resolve().parents[1]
private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-ui293-private'
snapshot = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-ui293-snapshot298'
app = psutil.Process(97436)
assert abs(app.create_time()-1788828033.4354932) < .01
assert Path(app.exe()).resolve() == (root/'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.exe').resolve()
with urllib.request.urlopen('http://127.0.0.1:63490/slots', timeout=5) as response:
    assert not any(item['is_processing'] for item in json.load(response)), 'Owner activity; do not stop'
rows = [json.loads(line) for line in (private/'turn-audit.jsonl').read_text(encoding='utf-8').splitlines()]
ids = {str(row.get('request_id', row.get('requestId', row.get('id', '')))) for row in rows}
print(json.dumps({'audit_keys':list(rows[0]),'ids':sorted(ids)}))
# Inspect the actual trace IDs before authorizing a restart of this development session.
assert ids <= {'6', '10'}, f'Unknown turn identifiers {ids}; preserve session first'
snapshot.mkdir(exist_ok=False)
for name in ['LAUNCH.json','launch.log','compose-audit.jsonl','turn-audit.jsonl','raw-replies.jsonl','shell-trace.jsonl']:
    if (private/name).is_file():
        shutil.copy2(private/name,snapshot/name)
children = app.children(recursive=True)
owned = [{'pid':p.pid,'createTime':p.create_time(),'exe':p.exe()} for p in [app,*children]]
assert 101140 not in [p.pid for p in children]
app.terminate()
psutil.wait_procs([app],timeout=8)
for process in reversed(children):
    try:
        process.terminate()
    except psutil.NoSuchProcess:
        pass
psutil.wait_procs(children,timeout=8)
(root/'artifacts/comprobaciones/C03/astra-question-scope298/STOP293.json').write_text(json.dumps({'snapshot':str(snapshot),'owned':owned},indent=2)+'\n',encoding='utf-8')
