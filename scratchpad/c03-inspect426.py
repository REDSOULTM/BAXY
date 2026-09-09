import json
import os
from pathlib import Path
root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-private-product426-private'
read=lambda p:[json.loads(l) for l in p.open(encoding='utf-8-sig')]
events=read(private/'capture/events.jsonl')
finals=[e for e in events if e['type']=='terminal']
prior=[e for e in read(private.parent/'C03-private-product423-private/capture/events.jsonl') if e['type']=='terminal']
print(json.dumps({'same_finals_as423':[e['final'] for e in finals]==[e['final'] for e in prior], 'finals':finals},ensure_ascii=False))
wire=read(private/'http-posts.jsonl');requests={};pairs=[]
for r in wire:
    key=(r['pid'],r['id'])
    if r['stage']=='request': requests[key]=r
    elif r['stage']=='response' and key in requests:
        req=requests[key];p=req['payload'];messages=p.get('messages',[])
        last=next((m['content'] for m in reversed(messages) if m['role']=='user'),'')
        if 'Me llamo Álvaro.' not in last: continue
        schema=(p.get('response_format') or {}).get('json_schema',{}).get('name')
        response=r['response'];message=(response.get('choices') or [{}])[0].get('message',{})
        pairs.append({'pid':key[0],'id':key[1],'schema':schema,'last_user':last,'message':message,'payload':p})
(private/'introduction-pairs.json').write_text(json.dumps(pairs,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
for p in pairs:
    if p['last_user']=='Me llamo Álvaro.' or p['last_user'].endswith('Me llamo Álvaro.'):
        print(json.dumps({k:v for k,v in p.items() if k!='payload'},ensure_ascii=False))
