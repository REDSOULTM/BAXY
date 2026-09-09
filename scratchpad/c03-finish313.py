from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import psutil

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-ui313-private'
launch = json.loads((private / 'LAUNCH.json').read_text(encoding='utf-8-sig'))
app = psutil.Process(launch['app'])
assert abs(app.create_time() - launch['appCreateTime']) < .01
assert Path(app.exe()).resolve() == (root / 'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.exe').resolve()
backends = []
for child in app.children(recursive=True):
    if child.name() == 'llama-server.exe':
        backends.append({'pid': child.pid, 'createTime': child.create_time(), 'command': child.cmdline()})
paths = [
    'src/Baxy.App/UserMessagePolicy.cs',
    'src/baxy_mind/llm.py',
    'tests/Baxy.Integration.Tests/PlannerAppBoundaryTests.cs',
    'tests/Baxy.Integration.Tests/Goal06VisibleVoiceTests.cs',
    'tests/test_compose_contract.py',
    'artifacts/comprobaciones/C03/astra-person-reference311/dotnet-owners-corrected.log',
    'artifacts/comprobaciones/C03/astra-person-reference311/python-owners.log',
    'artifacts/comprobaciones/C03/astra-person-reference311/fast311.log',
]
pins = {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in paths}
ui_path = private.parent / 'C03-ui312-private/ui.jsonl'
capture = [json.loads(line) for line in ui_path.read_text(encoding='utf-8-sig').splitlines()]
turn = next(row for row in capture if row['type'] == 'ui.turn')
assert turn['published'] and turn['rendered'][0]['msg'] == 'Tú eres el usuario que está hablando conmigo.'
pins_record = {'utc': datetime.now(timezone.utc).isoformat(), 'sha256': pins,
    'privateUi312': str(ui_path), 'ui312Sha256': hashlib.sha256(ui_path.read_bytes()).hexdigest(),
    'publicationRepaired': True, 'usefulIdentityResolved': False,
    'nativeHttpCaptured312': False, 'python': {'pass': 1040, 'skip': 0},
    'dotnet': {'pass': 155, 'skip': 0}, 'fast311': 'passed', 'full': 'not run during repair'}
(base / 'TRAMO309_313_PINS.json').write_text(json.dumps(pins_record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
relay = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'))
relay.update(confirmedAtUtc=pins_record['utc'],
    checkpoint='313: source311 publication repair proven in real UI312;1195 owners pass;Fast311green;normal BAXY313 open.',
    continuation='Capture exact selector payload with BAXY_MIND_PYTHONPATH observer when appropriate; preserve new owner313 turns; identity remains generic. Full C03 active.')
relay['userOwnedInstance'] = {'pid': app.pid, 'createTime': app.create_time(),
    'launcher': launch['launcher'], 'status': 'running', 'processRevalidated': True,
    'automaticClose': False, 'privateLogs': str(private), 'backends': backends,
    'instruction': 'Leave open for the owner; preserve new owner turns before any restart. No probe or timer.'}
(base / 'RELEVO_ACTIVO.json').write_text(json.dumps(relay, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'app': app.pid, 'backends': backends, 'publicationRepaired': True, 'goalComplete': False}))
