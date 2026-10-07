import json,sys
# Compact view of mission-journal operations in the last N records: op + observed (controls listed by name only).
import os
p=os.path.join(os.environ['LOCALAPPDATA'],'BAXY','cu-universal-perfil','journal','missions.jsonl')
ls=[l for l in open(p,encoding='utf-8-sig') if l.strip()]
n=int(sys.argv[1]); full=len(sys.argv)>2
for l in ls[-n:]:
    d=json.loads(l)['payload']
    if d['phase']=='started': continue
    r=d.get('response') or {}
    try: m=json.loads(r.get('message') or '{}')
    except Exception: m={'raw':r.get('message')}
    o=m.get('observed') or {}
    if d['operation']=='input.visible.controls' and not full:
        cs=o.get('controls') or []
        names=[(c.get('name') or '')[:30]+('*' if c.get('selected') else '') for c in cs]
        print(d['timestampUtc'][11:19],'VIEW',(o.get('window') or {}).get('title'),len(cs),'|',', '.join(names)[:900])
    else:
        print(d['timestampUtc'][11:19],d['operation'],m.get('succeeded'),json.dumps(o,ensure_ascii=False)[:700])
