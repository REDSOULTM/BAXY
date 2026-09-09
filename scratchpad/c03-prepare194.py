"""Actual desktop with diagnostic input events; source192 remains unchanged."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
out=base/'astra-ui194';out.mkdir(exist_ok=False)
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-ui194-private';private.mkdir(exist_ok=False)
prior=json.loads((base/'astra-audio166/PREREG.json').read_text(encoding='utf-8'))
paths=['src/Baxy.App/MainWindowViewModel.cs','src/Baxy.App/TurnVisibleFacts.cs','src/Baxy.App/PendingModelMessageQueue.cs','src/Baxy.App/MindSidecarClient.cs','src/Baxy.App/ModelMessageComposer.cs','src/baxy_mind/voice.py','src/baxy_mind/llm.py','src/baxy_mind/__main__.py','scratchpad/c03-ui194-hook/sitecustomize.py']
prereg={'utc':datetime.now(timezone.utc).isoformat(),'model':prior['model'],
 'method':'Actual py main.py and current192 App UI, existing registered runtime with Qwen3.5 override. External sitecustomize injects explicit wake/uncertain events only on command. Third case injects a technical voice.transcript while feedback composer is active and delays that diagnostic invocation0.5s. No authored response injection. Actual shared queue/policy/publication; observe UI via Computer Use.',
 'limitations':'Synthetic events and technical transcript are not human voice or fresh reserve. Existing unapproved wake seam not accepted. Endpoint volume remains as found; no acoustic/output claim. Speex remains product AEC, no DTLN binding.',
 'cases':['wake','uncertain','supersede with ¿Qué hora es?'],
 'sourceFiles':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths},
 'registrationSha256':hashlib.sha256((Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json').read_bytes()).hexdigest()}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2),encoding='utf-8')
content=(root/'scratchpad/c03-launch-audio166.py').read_text(encoding='utf-8').replace('astra-audio166','astra-ui194')
needle="with (out / 'launch.log').open('w', encoding='utf-8') as log:"
content=content.replace(needle,"env.update(BAXY_MIND_PYTHONPATH=str(root/'scratchpad/c03-ui194-hook')+os.pathsep+str(root/'src'), BAXY_DATA_DIR=str(Path(env['LOCALAPPDATA'])/'BAXY/C03-ui194-profile'))\n"+needle)
with (root/'scratchpad/c03-launch194.py').open('x',encoding='utf-8') as handle:handle.write(content)
print('194 prepared: actual UI, source192, diagnostic events; no endpoint change or acoustic acceptance.')
