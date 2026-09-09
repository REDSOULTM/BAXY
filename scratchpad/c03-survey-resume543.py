"""Verify scope542 and finish the unrun standalone controls from541."""
from pathlib import Path
import json
import os
import psutil

root=Path(__file__).resolve().parents[1]
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-survey-resume543-private'
assert psutil.virtual_memory().available/2**20>3000,'Need room for one isolated product before launch.'
private.mkdir(exist_ok=False)
previous=private.parent/'C03-survey-readonly541-private'
panel=json.loads((previous/'panel.json').read_text(encoding='utf-8'))
cases=[{'case_id':'H0026','origin':'post542 scope regression of native request541',
        'text':'What GPU is installed, and how much dedicated video memory does it have?'},
       {'case_id':'H0026','origin':'new ES qualified-memory variant',
        'text':'¿Qué tarjeta gráfica tengo y cuánta memoria de video tiene?'},
       {'case_id':'H0026','origin':'new EN qualified-memory variant',
        'text':'How much video memory does this computer have?'},
       *panel[25:]]
assert len(cases)==22
(private/'panel.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
hook=root/'scratchpad/c03-owner543-hook'
hook.mkdir(exist_ok=False)
(hook/'sitecustomize.py').write_text((root/'scratchpad/c03-owner521-hook/sitecustomize.py').read_text(encoding='utf-8').replace('C03-private-product521-private','C03-survey-resume543-private'),encoding='utf-8')
source=(root/'scratchpad/c03-private-product521.py').read_text(encoding='utf-8')
source=source.replace('astra-private-product521','astra-survey-resume543')
source=source.replace('C03-private-product521-private','C03-survey-resume543-private')
source=source.replace('C03-private-profile521','C03-survey-profile543')
source=source.replace('c03-owner521-hook','c03-owner543-hook')
start=source.index('cases = ')
end=source.index('\n\ncommands =',start)
source=source[:start]+"cases = [row['text'] for row in json.loads((private/'panel.json').read_text(encoding='utf-8'))]"+source[end:]
start=source.index('prereg = {')
end=source.index("(out/'PREREG.json').write_text",start)
source=source[:start]+'''prereg={
 'utc':datetime.now(timezone.utc).isoformat(),
 'method':'Actual product with adopted source542, registered model/backend, isolated profile. Three GPU scope controls must return gpu_identity with adapter evidence; assess final prose separately (byte conversion still unresolved). Then19standalone messages not executed541, without repeating its25completed messages. History is explicitly new, not reconstructed original context. No sender, mutation, owner profile, physical UI/audio or model overrides.',
 'authorization':'AUTORIZACION_DUENO_536.md; historical and assistant-authored variants have explicit per-case provenance.',
 'criteria':'Correct scope before prose; no summary without adapters represented as GPU inventory. Each later knowledge/social/status final separately checked against observations, language and original survey expectation. No automatic coverage for plausible text or incomplete groups.',
 'manifest_sha256':sha(manifest),'panel_sha256':sha(private/'panel.json'),
 'source_sha256':{name:sha(root/name) for name in ['src/baxy_mind/effect_intent.py','src/baxy_mind/__main__.py','src/baxy_mind/llm.py']},
 'private':str(private),'case_count':len(cases),
 'resource_limits':{'gpu_stop_mib':3800,'minimum_free_ram_mib':768,'wall_time_seconds':240},
 'preflight':'One product only; require >3000MiB available before startup; threshold768MiB unchanged. Own build servers stopped afterFast542. Do not close other apps.'}
''' +source[end:]
exec(compile(source,__file__,'exec'))
