"""Correlate every product694 turn by request id, preserving all native drafts."""
from pathlib import Path
import argparse
import json
import os
import re

parser=argparse.ArgumentParser()
parser.add_argument('--start',type=int,default=0)
parser.add_argument('--count',type=int,default=25)
parser.add_argument('--ids', default='', help='Comma-separated case IDs for an exact follow-up read.')
parser.add_argument('--summary', action='store_true', help='Read every final before opening its complete typed facts.')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-status-batch694-private'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):
    with p.open(encoding='utf-8-sig') as stream:return list(map(json.loads,stream))
assert read(root/'artifacts/comprobaciones/C03/astra-status-batch694/EXIT.json')=={'exitCode':0,'manifest_unchanged':True}
assert (private/'panel.json').read_bytes()==(private.parent/'C03-status-batch689-private/panel.json').read_bytes()
panel=read(private/'panel.json')
events=rows(private/'capture/events.jsonl')
finals=[r for r in events if r.get('type')=='terminal']
assert len(panel)==len(finals)==73
shell=rows(private/'shell-trace.jsonl')
compose=rows(private/'compose-audit.jsonl')
audit=rows(private/'turn-audit.jsonl')
decisions={r['request_id']:r for r in audit if r.get('phase')=='final'}
review=[]
for i,(case,final) in enumerate(zip(panel,finals),1):
    trace=[r for r in shell if r['scope']=='turn' and r['id']==f't{i}']
    ids=[m[1] for r in trace if (m:=re.search(r'turn\.decide\.id\.(\d+)\.',r.get('detail') or ''))]
    drafts=[r for r in compose if r.get('trace')==f't{i}']
    review.append({**case,'turn_id':f't{i}','terminal':final,
        'core_calls':[r['detail'] for r in trace if r['stage']=='core.call.start'],
        'decisions':[decisions[k] for k in ids if k in decisions],'compose':drafts})
(private/'review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
selected = [r for r in review if r['case_id'] in args.ids.split(',')] if args.ids else review[args.start:args.start+args.count]
for r in selected:
    first=next((d for d in r['compose'] if d.get('stage')=='first'),{})
    print(json.dumps({'id':r['case_id'],'group':r['group'],'text':r['text'],'final':r['terminal']['final'],
        'kind':r['terminal']['kind'],'core_calls':r['core_calls'],'facts':None if args.summary else first.get('payload'),
        'rejected':None if args.summary else [{k:d.get(k) for k in ['stage','draft','reason']} for d in r['compose'] if d.get('reason')]},ensure_ascii=False))
