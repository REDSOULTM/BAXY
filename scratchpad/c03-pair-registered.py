"""Pair existing conductor evidence; never infer a quality verdict from publication."""
from pathlib import Path
import json
import sys

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
folder=base/sys.argv[1]
commands=[json.loads(s) for s in folder.with_suffix('.turns.jsonl').read_text(encoding='utf-8-sig').splitlines()]
requests=[];mode='none'
for c in commands:
    if c['cmd']=='inject':mode=c['mode']
    elif c['cmd']=='restore':mode='none'
    elif c['cmd']=='turn':requests.append({'request':c['text'],'injection':mode})
events=[json.loads(s) for s in (folder/'events.jsonl').read_text(encoding='utf-8-sig').splitlines()]
compose=[json.loads(s) for s in (folder/'compose-audit.jsonl').read_text(encoding='utf-8-sig').splitlines()]
paired=[];public=[]
for e in events:
    if e.get('type')=='event':public.append(e['event'])
    elif e.get('type')=='terminal':
        index=len(paired);tid=f't{index+1}'
        paired.append({**requests[index],'turnId':tid,'terminal':e['kind'],'final':e.get('final'),'publicEvents':public,'compose':[c for c in compose if c.get('trace')==tid]})
        public=[]
    elif e.get('type')=='posterior' and paired:paired[-1]['posterior']=e
assert len(paired)==len(requests),(len(paired),len(requests))
(folder/'paired.json').write_text(json.dumps(paired,ensure_ascii=False,indent=2),encoding='utf-8')
for r in paired:
    utterances=[e['entry']['msg'] for e in r['publicEvents'] if e.get('type')=='activity' and e['entry']['src']=='BAXY']
    print(json.dumps({'id':r['turnId'],'request':r['request'],'injection':r['injection'],'terminal':r['terminal'],'answer':r['final'],'visible':utterances},ensure_ascii=False))
