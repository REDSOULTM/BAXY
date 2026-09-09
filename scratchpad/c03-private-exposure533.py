"""Audit actual private development logs against reserve, without showing/replaying texts."""
from pathlib import Path
from datetime import datetime,timezone
import collections,hashlib,json,os,unicodedata
root=Path(__file__).resolve().parents[1]
local=Path(os.environ['LOCALAPPDATA'])/'BAXY'
out=local/'C03-private-exposure533-private'
public=root/'artifacts/comprobaciones/C03/astra-private-exposure533'
out.mkdir(exist_ok=False);public.mkdir(exist_ok=False)
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def key(t):return ' '.join(unicodedata.normalize('NFC',t).casefold().split())
prior=local/'C03-exposure532-private/review.jsonl'
rows=list(map(json.loads,prior.open(encoding='utf-8-sig')))
reserve=list(map(json.loads,(local/'C03-reserve-language475-private/review.jsonl').open(encoding='utf-8-sig')))
reserve_ids={r['id'] for r in reserve}
index=collections.defaultdict(set)
for r in rows:index[key(r['text_literal'])].add(r['id'])
paths=[];excluded=[]
# Bounded inventory of the known local C03 diagnostic root; no artifacts traversal.
filenames={'posts.jsonl','http-posts.jsonl','compose-audit.jsonl','turn-audit.jsonl','turns.jsonl','messages.jsonl','compose-overrides.jsonl','forwarded-native.jsonl','deferred-override.jsonl'}
for folder in sorted(local.glob('C03-*-private')):
 if not folder.is_dir():continue
 if any(s in folder.name for s in ('reserve-','exposure','owner-review','questionnaire')):
  excluded.append({'path':str(folder),'reason':'reserve/owner adjudication, not BAXY development input'});continue
 for filename in sorted(filenames):
  path=folder/filename
  if path.is_file():paths.append(path)
write(public/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'method':'Read actual private C03 HTTP/composition/turn inputs by bounded folder and exact log-name inventory. Recursive JSON and exact full text/individual complete lines, NFC/casefold/whitespace only. No model calls, effects or product edits. Results exclude matched reserve candidates from acceptance; not code/repair examples. Hash files before and after; unstable/malformed files stay unresolved. Separate prior532 exposures, no certification from nonmatch.','files':len(paths),'filenames':sorted(filenames),'prior_sha256':sha(prior),'reserve_review_sha256':sha(local/'C03-reserve-language475-private/review.jsonl')})
matches=collections.defaultdict(set);sources=[];errors=[]
def visit(v,ref,depth=0):
 if depth>30:return
 if isinstance(v,str):
  for text in [v,*v.splitlines()]:
   for identifier in index.get(key(text),[]):matches[identifier].add(ref)
  if v.lstrip().startswith(('{','[')):
   try:decoded=json.loads(v)
   except (ValueError,RecursionError):return
   if isinstance(decoded,(list,dict)):visit(decoded,ref,depth+1)
 elif isinstance(v,dict):
  for k,value in v.items():
   # Pure replies can repeat input; this is conservative development exposure,
   # never evidence that a matched text was typed by a human in this probe.
   visit(value,ref,depth+1)
 elif isinstance(v,list):
  for value in v:visit(value,ref,depth+1)
for path in paths:
 before=sha(path);count=0
 with path.open(encoding='utf-8-sig') as f:
  for n,line in enumerate(f,1):
   if not line.strip():continue
   try:r=json.loads(line)
   except (ValueError,RecursionError) as error:
    errors.append({'path':str(path),'line':n,'error':str(error)});continue
   visit(r,f'{path}:{n}');count+=1
 after=sha(path)
 sources.append({'path':str(path),'sha256_before':before,'sha256_after':after,'stable':before==after,'rows':count,'bytes':path.stat().st_size})
new=[];remaining=[]
with (out/'review.jsonl').open('x',encoding='utf-8') as f:
 for row in rows:
  refs=sorted(matches.get(row['id'],[]));row['private_development_exposure533']=refs
  if refs:
   if row['freshness_review']!='known_exposure':new.append(row['id'])
   row['freshness_review']='known_exposure'
  if row['id'] in reserve_ids and row['freshness_review']!='known_exposure':remaining.append(row['id'])
  f.write(json.dumps(row,ensure_ascii=False)+'\n')
write(out/'sources.json',sources);write(out/'parse-errors.json',errors);write(out/'excluded-folders.json',excluded);write(out/'remaining-ids.json',remaining)
summary={'utc':datetime.now(timezone.utc).isoformat(),'audited_files':len(sources),'audited_rows':sum(s['rows'] for s in sources),'stable_files':sum(s['stable'] for s in sources),'malformed_lines':len(errors),'matched_pool_ids':len(matches),'newly_exposed_since532':len(new),'reserve475_count':len(reserve_ids),'reserve475_matched':len(reserve_ids & set(matches)),'remaining_reserve_count':len(remaining),'remaining_semantic_languages':dict(collections.Counter(r['language_semantic'] for r in reserve if r['id'] in remaining)),'private':str(out),'review_sha256':sha(out/'review.jsonl'),'sources_sha256':sha(out/'sources.json'),'certified_fresh':0,'frozen':False,'replayed':0,'limitations':['Bounded known private C03 logs, not every possible historical project/cache.','Exact full-string/line match; aliases, paraphrases and formatted inline fragments remain separate review.','All matched development evidence is conservatively excluded; no authorship conclusion.','Historical training/splits and context remain necessary.','Any malformed or unstable files are recorded as unresolved, not silently accepted.']}
write(public/'RESULT.json',summary);write(public/'PINS.json',{p.name:sha(p) for p in public.iterdir() if p.is_file() and p.name!='PINS.json'})
print(json.dumps(summary,ensure_ascii=True),flush=True)
