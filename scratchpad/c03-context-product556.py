"""Real-product closing and continuity after source555, isolated profile."""
from pathlib import Path
import json,os,psutil
root=Path(__file__).resolve().parents[1]
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-context-product556-private'
assert psutil.virtual_memory().available/2**20>3000
private.mkdir(exist_ok=False)
previous=private.parent/'C03-survey-resume543-private'
panel=json.loads((previous/'panel.json').read_text(encoding='utf-8'))
cases=[c for c in panel if c['case_id'] in {'H0065','H0073','H0078'}]
cases.extend([
 {'case_id':'H0078','origin':'new Spanish closing variant','text':'Gracias, ya no necesito nada más.'},
 {'case_id':'H0078','origin':'new English closing variant','text':"That's all for now, thank you."},
 {'case_id':'continuity-control','origin':'new explicit temporary dialogue fact, no private save requested','text':'La palabra que inventé es Solmira729.'},
 {'case_id':'continuity-control','origin':'new literal recall regression','text':'¿Qué palabra inventada mencioné antes?'},
])
assert len(cases)==10
(private/'panel.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
hook=root/'scratchpad/c03-owner556-hook'
hook.mkdir(exist_ok=False)
(hook/'sitecustomize.py').write_text((root/'scratchpad/c03-owner521-hook/sitecustomize.py').read_text(encoding='utf-8').replace('C03-private-product521-private','C03-context-product556-private'),encoding='utf-8',newline='\n')
source=(root/'scratchpad/c03-private-product521.py').read_text(encoding='utf-8')
for old,new in [('astra-private-product521','astra-context-product556'),('C03-private-product521-private','C03-context-product556-private'),('C03-private-profile521','C03-context-profile556'),('c03-owner521-hook','c03-owner556-hook')]:source=source.replace(old,new)
start=source.index('cases = ');end=source.index('\n\ncommands =',start)
source=source[:start]+"cases = [row['text'] for row in json.loads((private/'panel.json').read_text(encoding='utf-8'))]"+source[end:]
start=source.index('prereg = {');end=source.index("(out/'PREREG.json').write_text",start)
source=source[:start]+'''prereg={
 'utc':datetime.now(timezone.utc).isoformat(),
 'method':'Shared product with source555 and registered Qwen2507/b9980. Replay actual543 CPU/volume context then closing That is it/Eso era todo, plus ES/EN closing variants and temporary literal recall. Source must never publish resolved_meaning when direct_answer is invalid; bounded direct retry should provide natural final or honest failure. Check native first transformation and every final, no mere admission credit.',
 'authorization':'AUTORIZACION_DUENO_536.md; explicit isolated read-only diagnostic, conversational fact does not authorize private memory mutation.',
 'criteria':'Closing addressed to the person without internal third-person analysis or echoes. Keep ES/EN, recall Solmira729 exactly without inventing private storage. CPU subject remains independently unresolved; do not mark all cases correct because closure improves. No physical desktop/voice credit.',
 'manifest_sha256':sha(manifest),'panel_sha256':sha(private/'panel.json'),
 'source_sha256':{name:sha(root/name) for name in ['src/baxy_mind/llm.py','src/baxy_mind/__main__.py','src/baxy_mind/effect_intent.py']},
 'private':str(private),'case_count':len(cases),
 'resource_limits':{'gpu_stop_mib':3800,'minimum_free_ram_mib':768,'wall_time_seconds':240}}
''' +source[end:]
exec(compile(source,__file__,'exec'))
