"""Index all742 requirements for shared-repair planning; never award coverage."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib
import json
import os
import re
import sys

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from baxy_mind.effect_intent import resolve_explicit_effects
from baxy_mind.request_reading import read_request
base=root/'artifacts/comprobaciones/C03'
home=Path(os.environ['LOCALAPPDATA'])/'BAXY'
path=home/'C03-survey-requirements336-private/requirements.jsonl'
before=path.read_bytes()
requirements=[json.loads(line) for line in before.splitlines()]
catalog=root/'src/Baxy.Kernel/Operations/ProductCatalog.cs'
operations=frozenset(re.findall(r'Descriptor\(\s*"([a-z][a-z0-9_.]+)"',catalog.read_text(encoding='utf-8-sig')))
assert len(requirements)==742 and {'app.open','system.status','system.time','wifi.status'}<=operations
batch=json.loads((home/'C03-status-batch689-private/adjudication.json').read_text(encoding='utf-8'))
measured={r['case_id']:r for r in batch if r['case_id'].startswith('H')}
board=[]
for row in requirements:
    reading=read_request(row['literal'])
    resolved=resolve_explicit_effects(row['literal'],operations)
    proposed=list(resolved.operations) if resolved is not None else []
    groups=sorted({op.split('.')[0] for op in proposed})
    group='+'.join(groups) if groups else ('conversation:'+','.join(sorted(reading.intents)) if reading.intents else 'needs_context_or_model')
    last=measured.get(row['case_id'])
    board.append({'case_id':row['case_id'],'coverage':row['verification_status'],
        'expectation_kind':row.get('expectation_kind'),'planning_group':group,
        'standalone_explicit_operations':proposed,'language':reading.language,
        'batch689':None if last is None else {'verdict':last['verdict'],'cause_group':last['cause_group']}})
counts=dict(Counter(r['coverage'] for r in board))
assert counts=={'open':716,'covered':26}
result={'updated_at':datetime.now(timezone.utc).isoformat(),'records':742,'verification_counts':counts,
    'method':'Read-only planning index over every survey row using existing request reading and bounded explicit-effect resolver against statically declared catalog names. No model inference, provider calls or effects. Standalone resolution lacks original dialogue/application catalog; unresolved does not mean unsupported, resolved does not mean correct or covered. Planning only; preserve individual evidence and owner notes in private source.',
    'owner_direction':'Prioritize maximum coverage across the entire742 registry. Batch by shared causes and complete affected categories; do not treat small experimental panels as delivery units.',
    'requirements_sha256':hashlib.sha256(before).hexdigest(),'catalog_sha256':hashlib.sha256(catalog.read_bytes()).hexdigest(),
    'catalog_names':len(operations),'group_counts':dict(Counter(r['planning_group'] for r in board).most_common()),
    'open_group_counts':dict(Counter(r['planning_group'] for r in board if r['coverage']=='open').most_common()),
    'measured_batch689_cause_counts':dict(Counter(r['cause_group'] for r in batch if r.get('cause_group'))),
    'rows':board}
(base/'COVERAGE_WORKBOARD692.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
assert path.read_bytes()==before
print(json.dumps({'records':742,'coverage':counts,'catalog_names':len(operations),'largest_open_groups':list(result['open_group_counts'].items())[:15]},ensure_ascii=False))
