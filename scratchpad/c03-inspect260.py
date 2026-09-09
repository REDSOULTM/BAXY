"""Record read-only process evidence while the already-owned desktop runs."""
from pathlib import Path
import json
import os
import psutil

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-ui260'
owner = json.loads((out / 'PROCESS.json').read_text(encoding='utf-8'))
app = psutil.Process(owner['app'])
assert app.create_time() == owner['appCreateTime']
rows = []
for process in [app, *app.children(recursive=True)]:
    try:
        rows.append({'pid': process.pid, 'created': process.create_time(),
                     'exe': process.exe(), 'command': process.cmdline(),
                     'rss': process.memory_info().rss})
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        continue
path = out / 'PROCESSES_OBSERVED.json'
assert not path.exists()
path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-ui260-private'
events = [json.loads(line) for line in (private/'voice-events.jsonl').read_text(encoding='utf-8').splitlines()]
print(json.dumps({'processes': len(rows), 'observedRssMiB': sum(r['rss'] for r in rows)/1048576,
                  'nonAecEvents': [e for e in events if e['event'] != 'aec_observation']}, ensure_ascii=False))
