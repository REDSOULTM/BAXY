"""Observe the rebuilt Core hello after correcting duplicate Start entries."""
from pathlib import Path
import hashlib
import json
import os
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root/'src'),str(root)]
from scripts.measure_mind_budget import current_core_catalog_snapshot
from baxy_mind.__main__ import configure_application_catalog
from baxy_mind.effect_intent import resolve_application_catalog_app_id

out = root/'artifacts/comprobaciones/C03/astra-app-catalog262'
private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-app-catalog262-private'
private.mkdir(exist_ok=False)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
core = root/'src/Baxy.Core/bin/Release/net10.0-windows10.0.19041.0/baxy-core.exe'
old = json.loads((private.parent/'C03-retrieval261-private/HELLO_CATALOGS.json').read_text(encoding='utf-8'))
started = time.monotonic()
capabilities,apps,games = current_core_catalog_snapshot(core)
names = configure_application_catalog(apps)
save(private/'HELLO_CATALOGS.json',{'capabilities':capabilities,'apps':apps,'games':games})
result = {'seconds':time.monotonic()-started, 'coreSha256':sha(core),
    'providerSha256':sha(core.parent/'Baxy.Providers.Windows.dll'),
    'capabilitiesUnchanged':capabilities==old['capabilities'],
    'appsBefore':len(old['apps']['names']), 'appsAfter':len(names),
    'addedNames':sorted(set(names)-set(old['apps']['names'])),
    'removedNames':sorted(set(old['apps']['names'])-set(names)),
    'resolution':{text:resolve_application_catalog_app_id(text,names)
                  for text in ['Tengo en mente que abras steam','abre steam','Si, abre steam']}}
save(out/'CORE_RESULT.json',result)
print(json.dumps(result,ensure_ascii=False))
