"""Actual product measurement-query controls following source545."""
from pathlib import Path
import json
import os
import psutil

root=Path(__file__).resolve().parents[1]
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-coordinate-product546-private'
assert psutil.virtual_memory().available/2**20>3000
private.mkdir(exist_ok=False)
cases=[
 {'case_id':'H0079','origin':'owner historical survey','text':'decime la hora y cuánta batería tengo'},
 {'case_id':'H0079','origin':'assistant English variant','text':'How much battery is left, and what time is it?'},
 {'case_id':'H0079','origin':'assistant reordered variant','text':'¿Cuánta batería tengo y qué hora es?'},
 {'case_id':'H0079','origin':'assistant changed scope','text':'¿Qué fecha es y cuánta RAM libre tengo?'},
 {'case_id':'H0079','origin':'assistant English changed scope','text':'How much disk space is free, and how much battery is left?'},
 {'case_id':'H0079','origin':'assistant combined-scope regression','text':'¿Qué sistema operativo tengo y cuánta RAM hay?'},
]
(private/'panel.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
hook=root/'scratchpad/c03-owner546-hook'
hook.mkdir(exist_ok=False)
(hook/'sitecustomize.py').write_text((root/'scratchpad/c03-owner521-hook/sitecustomize.py').read_text(encoding='utf-8').replace('C03-private-product521-private','C03-coordinate-product546-private'),encoding='utf-8',newline='\n')
source=(root/'scratchpad/c03-private-product521.py').read_text(encoding='utf-8')
for old,new in [('astra-private-product521','astra-coordinate-product546'),('C03-private-product521-private','C03-coordinate-product546-private'),('C03-private-profile521','C03-coordinate-profile546'),('c03-owner521-hook','c03-owner546-hook')]:
    source=source.replace(old,new)
start=source.index('cases = ')
end=source.index('\n\ncommands =',start)
source=source[:start]+"cases = [row['text'] for row in json.loads((private/'panel.json').read_text(encoding='utf-8'))]"+source[end:]
start=source.index('prereg = {')
end=source.index("(out/'PREREG.json').write_text",start)
source=source[:start]+'''prereg={
 'utc':datetime.now(timezone.utc).isoformat(),
 'method':'Shared product after source545, isolated profile, six read-only coordinated queries. Registered Qwen2507/b9980 unchanged. No physical UI or voice. All requested observations must be present and correctly attributed in final prose; do not credit publication alone.',
 'authorization':'AUTORIZACION_DUENO_536.md; development with per-case provenance.',
 'manifest_sha256':sha(manifest),'panel_sha256':sha(private/'panel.json'),
 'source_sha256':{name:sha(root/name) for name in ['src/baxy_mind/effect_intent.py','src/baxy_mind/__main__.py','src/baxy_mind/llm.py']},
 'private':str(private),'case_count':len(cases),
 'resource_limits':{'gpu_stop_mib':3800,'minimum_free_ram_mib':768,'wall_time_seconds':240}}
'''+source[end:]
exec(compile(source,__file__,'exec'))
