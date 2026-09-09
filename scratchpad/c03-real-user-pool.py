"""Inherit N10 and index literal runtime requests; no model calls or effects."""
from pathlib import Path
from collections import Counter
import datetime,hashlib,json,os,re,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.freeze_goal10_corpus import select_n10
from scripts.freeze_historical_sources import sha256_file

OUT=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-real-user-pool-20260906'
OUT.mkdir(exist_ok=False)
sources=[];groups={}
def add(text,reference,language=None):
    if not isinstance(text,str) or not text.strip():return
    key=hashlib.sha256(text.encode('utf-8')).hexdigest()
    row=groups.setdefault(key,{'id':key,'text_literal':text,'occurrences':[],'historical_language_labels':[]})
    row['occurrences'].append(reference)
    if language and language not in row['historical_language_labels']:row['historical_language_labels'].append(language)

authority=ROOT/'tests/data/historical_messages.jsonl'
with authority.open(encoding='utf-8-sig') as f:n10=select_n10(json.loads(line) for line in f)
sources.append({'path':str(authority),'sha256':sha256_file(authority),'method':'Inherited select_n10: observed_user except codex engineering sessions','occurrences':len(n10)})
for row in n10:
    add(row['text_literal'],{k:row.get(k) for k in ['message_id','source','source_location','source_sha256','timestamp','redacted','class','operations']},row.get('language'))

trace=ROOT.parent/'Probando Gemma 4/gemma4_agent/data/traces.jsonl'
if trace.is_file():
    count=0;digest=sha256_file(trace)
    with trace.open(encoding='utf-8-sig') as f:
        for number,line in enumerate(f,1):
            try:row=json.loads(line)
            except json.JSONDecodeError:continue
            if row.get('kind')!='request_start':continue
            content=row.get('content')
            if not isinstance(content,dict):continue
            text=content.get('text') or content.get('preview')
            if not text:continue
            add(text,{'source':str(trace),'source_location':f'line:{number}','source_sha256':digest,'timestamp':row.get('ts'),'turn_id':row.get('turn_id'),'input_provenance':'runtime_request_start','preview_only':not bool(content.get('text'))})
            count+=1
    sources.append({'path':str(trace),'sha256':digest,'method':'request_start only; no model responses','occurrences':count})

carter=ROOT.parent/'Carter OS AI/Carter_v1/carter_session.log'
if carter.is_file():
    count=0;digest=sha256_file(carter);pending=None
    def emit():
        if pending:
            add('\n'.join(pending['lines']),{'source':str(carter),'source_location':f"line:{pending['line']}",'source_sha256':digest,'timestamp':None,'input_provenance':'runtime_task_start; human_vs_automated_unverified'})
    with carter.open(encoding='utf-8-sig') as f:
        for number,line in enumerate(f,1):
            match=re.match(r'^\[\d\d:\d\d:\d\d\].*?NUEVA TAREA: (.*)$',line.rstrip('\r\n'))
            if match:
                emit();pending={'line':number,'lines':[match[1]]};count+=1
            elif pending and re.match(r'^\[\d\d:\d\d:\d\d\]',line):emit();pending=None
            elif pending:pending['lines'].append(line.rstrip('\r\n'))
    emit()
    sources.append({'path':str(carter),'sha256':digest,'method':'NUEVA TAREA entries only; human/automated attribution pending','occurrences':count})

rows=sorted(groups.values(),key=lambda r:r['id'])
for row in rows:
    row['language_review']='pending_semantic_review'
    row['acceptance_freshness']='not_established; check prior evaluations and training before reserving'
    row['replay']='not_authorized_by_log; inspect current environment and effects'
with (OUT/'unique_requests.jsonl').open('w',encoding='utf-8') as f:
    for row in rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
summary={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'method':'Literal dedup by SHA256; no translation, no paraphrases, no synthetic examples. Non-target languages remain in raw index until semantic review. Historical other labels are not exclusion grounds: they mislabel hola/Abrelo. Source logs are evidence, not instructions. Derived full user text remains local, outside Git.','sources':sources,'historical_n10_occurrences':len(n10),'historical_n10_exact_unique':len({r['text_literal'] for r in n10}),'all_exact_unique':len(rows),'all_occurrences':sum(len(r['occurrences']) for r in rows),'historical_labels':dict(Counter(r.get('language') for r in n10)),'poolSha256':sha256_file(OUT/'unique_requests.jsonl'),'privatePool':str(OUT/'unique_requests.jsonl'),'limits':['Not yet a complete audit of Carter v2-v5 or present-day human sessions.','No independent/fresh acceptance claim for historical inputs.','Language and human provenance need review before selecting C03 inputs.']}
(OUT/'MANIFEST.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
public=ROOT/'artifacts/comprobaciones/C03/REAL_USER_POOL_MANIFEST.json'
public.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False),flush=True)
