import json,sys
for l in open(sys.argv[1],encoding='utf-8-sig'):
    l=l.strip()
    if not l: continue
    d=json.loads(l)
    t=d.get('type') or d.get('event') or d.get('kind')
    s=json.dumps(d,ensure_ascii=False)
    if len(sys.argv)>2 and sys.argv[2]=='all': print(s[:900]); continue
    if any(k in s for k in ('computer_use','computer.use','final','reply','text','confirm','mission','terminal','error')):
        print(s[:700])
