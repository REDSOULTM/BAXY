from pathlib import Path
import json
import os

private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-survey-readonly541-private'
panel=json.loads((private/'panel.json').read_text(encoding='utf-8'))
targets={r['text'] for r in panel if r['case_id'] in {'H0007','H0025','H0026'}}
requests={}
with (private/'http-posts.jsonl').open(encoding='utf-8-sig') as handle:
    for line in handle:
        row=json.loads(line)
        if row['stage']=='request':
            messages=row['payload'].get('messages',[])
            content=messages[-1].get('content','') if messages else ''
            if isinstance(content,str) and any(content.startswith(t) or content.endswith(t) for t in targets):
                requests[row['id']]=row
        elif row['stage']=='response' and row['id'] in requests:
            req=requests[row['id']]['payload']['messages']
            msg=req[-1]['content']
            choice=row['response'].get('choices',[{}])[0].get('message',{})
            print(json.dumps({'id':row['id'],'system':req[0]['content'][:110],
                              'last_input':msg if len(msg)<1400 else msg[-1400:],
                              'response':choice},ensure_ascii=False))
