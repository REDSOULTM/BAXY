import json,sys
# Compact view of mission-journal operations in the last N records: op + observed (controls listed by name only).
# The journal rotates (missions.<k>.jsonl are the sealed segments, missions.jsonl the live one), so the last N
# records may start in an archived segment. Only the segments the journal's manifest (missions.jsonl.segments,
# newest first) still links belong to this journal: segments left by an earlier reset are not read.
import os
p=os.path.join(os.environ['LOCALAPPDATA'],'BAXY','cu-universal-perfil','journal','missions.jsonl')
def linked_segments(path):
    try: manifest=json.load(open(path+'.segments',encoding='utf-8'))['payload']
    except (OSError,ValueError,KeyError): return []
    stem,ext=os.path.splitext(path)
    return ['%s.%d%s'%(stem,link['segment'],ext) for link in reversed(manifest.get('segments') or [])]
def journal_lines(path,count):
    files=linked_segments(path)+[path]
    out=[]
    for f in reversed(files):
        if not os.path.exists(f): continue
        out=[l for l in open(f,encoding='utf-8-sig') if l.strip()]+out
        if len(out)>=count: break
    return out[-count:]
n=int(sys.argv[1]); full=len(sys.argv)>2
ls=journal_lines(p,n)
for l in ls:
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
