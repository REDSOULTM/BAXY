"""Read-only reproduction of operation retrieval after the real UI260 failure."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / 'src'), str(root)]
from scripts.measure_mind_budget import current_core_catalog_snapshot
from baxy_mind.__main__ import configure_tools, configure_application_catalog
from baxy_mind.effect_intent import resolve_application_catalog_app_id
from baxy_mind.planner import PlannerCatalog
from baxy_mind.router import SemanticEncoder, MODEL_NAME, MODEL_REVISION

out = root / 'artifacts/comprobaciones/C03/astra-retrieval261'
out.mkdir(exist_ok=False)
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-retrieval261-private'
private.mkdir(exist_ok=False)
def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
core = root / 'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/baxy-core.exe'
inputs = ['Tengo en mente que abras steam', 'abre steam', 'Si, abre steam']
save(out/'PREREG.json', {'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Three literal owner text inputs observed in UI260; development, not reserve. '
    'Current authenticated Core hello only, no operations invoked. Exact production E5 CPU and '
    'PlannerCatalog, no LLM, no UI. Check app identity and shortlist before changing code. '
    'New Core discovery is a current snapshot, not the original UI260 hello.',
    'inputs': inputs, 'encoder': MODEL_NAME, 'encoderRevision': MODEL_REVISION,
    'source': {n: sha(root/n) for n in ['src/baxy_mind/planner.py', 'src/baxy_mind/router.py',
        'src/baxy_mind/effect_intent.py', 'src/baxy_mind/__main__.py',
        'src/Baxy.Kernel/Operations/ProductCatalog.cs', 'scratchpad/c03-retrieval261.py']},
    'coreSha256': sha(core)})
started = time.monotonic()
capabilities, apps, games = current_core_catalog_snapshot(core)
save(private/'HELLO_CATALOGS.json', {'capabilities': capabilities, 'apps': apps, 'games': games})
names = configure_application_catalog(apps)
print(json.dumps({'capabilities':len(capabilities), 'apps':len(names),
                  'steamNames':[n for n in names if 'steam' in n.casefold()]}, ensure_ascii=False), flush=True)
encoder = SemanticEncoder()
catalog = PlannerCatalog(configure_tools(capabilities), encoder=encoder.encode)
rows = []
for text in inputs:
    shortlist = [t.name for t in catalog.shortlist(text)]
    scores = catalog._semantic_tool_scores(text)
    raw_rank = sorted(scores, key=scores.get, reverse=True)
    row = {'input':text, 'resolvedAppId':resolve_application_catalog_app_id(text,names),
           'shortlist':shortlist, 'semanticRankAppOpen':raw_rank.index('app.open')+1,
           'scores':scores}
    rows.append(row)
    print(json.dumps({k:v for k,v in row.items() if k!='scores'},ensure_ascii=False),flush=True)
save(out/'RESULT.json', {'rows':rows, 'seconds':time.monotonic()-started,
    'steamNames':[n for n in names if 'steam' in n.casefold()],
    'catalogSha256':sha(private/'HELLO_CATALOGS.json')})
