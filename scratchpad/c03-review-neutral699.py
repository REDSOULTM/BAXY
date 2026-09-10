"""Expose final answers and measured costs; do not manufacture quality grades."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import statistics

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03/K2_HORIZON_NATIVE699'
parser=argparse.ArgumentParser()
parser.add_argument('tag')
parser.add_argument('--start',type=int,default=0)
parser.add_argument('--count',type=int,default=0)
parser.add_argument('--seal-measurements',action='store_true')
args=parser.parse_args()
private=Path(os.environ['LOCALAPPDATA'])/f'BAXY/C03-k2-native699-{args.tag}-private'
out=base/f'run-{args.tag}'
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))
panel=read(base/'PANEL.json')
records=[json.loads(line) for line in (private/'results.jsonl').read_text(encoding='utf-8').splitlines()]
prereg=read(out/'PREREG.json')
assert prereg['panel_sha256']==sha(base/'PANEL.json')
assert prereg['driver_sha256']==sha(private/'driver.py')
assert [r['case'] for r in records]==prereg['cases'][:len(records)]
metrics=dict(tag=args.tag,responses=len(records),expected=50,
    seconds=dict(median=statistics.median(r['seconds'] for r in records),max=max(r['seconds'] for r in records)),
    errors=[r['case'] for r in records if r.get('error')],
    empty_finals=[r['case'] for r in records if not r['content'].strip()],
    finish_reasons={str(x):sum(r.get('finish_reason')==x for r in records) for x in {r.get('finish_reason') for r in records}},
    prompt_tokens_max=max(r.get('usage',{}).get('prompt_tokens',0) for r in records),
    completion_tokens_max=max(r.get('usage',{}).get('completion_tokens',0) for r in records),
    results_sha256=sha(private/'results.jsonl'))
if (out/'RESOURCES.json').exists():
    metrics['resources']=read(out/'RESOURCES.json')
if args.seal_measurements:
    assert len(records)==50 and 'resources' in metrics
    assert metrics['resources']['manifest_unchanged'] and not metrics['resources']['violations']
    assert metrics['resources']['gpu_peak_mib']<4096
    parity=[json.loads(line) for line in (out/'TEMPLATE_PARITY.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(parity)==50 and all(r['suffix_matches'] for r in parity)
    if prereg['arguments']['family']=='k2':
        token=read(out/'TOKENIZER_PARITY.json')
        assert token['equal']==token['cases']==285 and token['mismatches']==0
    requests=[json.loads(line) for line in (private/'requests.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(requests)==50
    for request,row in zip(requests,panel,strict=True):
        assert request['payload']['messages']==row['payload']['messages']
        assert all(key not in request['payload'] for key in ['tools','response_format'])
    metrics['requests_sha256']=sha(private/'requests.jsonl')
    metrics['template_parity_sha256']=sha(out/'TEMPLATE_PARITY.jsonl')
    (out/'MEASUREMENTS.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(metrics,ensure_ascii=False))
for row,record in list(zip(panel,records,strict=False))[args.start:args.start+args.count]:
    print(json.dumps(dict(id=row['id'],rubric=row['rubric'],answer=record['content'],error=record.get('error')),ensure_ascii=False))
