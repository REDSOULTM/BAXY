"""Read compact diagnostics from the active263 capture without changing it."""
from pathlib import Path
import json
import os

path=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-ui263-private/http-posts.jsonl'
rows=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
requests={row['id']:row for row in rows if row['stage']=='request'}
for row in rows:
    if row['stage'] not in {'response','failure'}:
        continue
    request=requests[row['id']]['payload']
    choices=row.get('response',{}).get('choices',[])
    selection=request.get('tool_choice')=='auto'
    if not selection and row['stage']!='failure':
        continue
    print(json.dumps({'id':row['id'],'selection':selection,'stage':row['stage'],
        'tools':[t['function']['name'] for t in request.get('tools',[])],
        'lastMessage':request.get('messages',[])[-1:] if selection else [],
        'choice':choices,'errorType':row.get('errorType')},ensure_ascii=False))
