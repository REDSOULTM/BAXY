from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
out=base/'astra-memory-redaction443'
(out/'RESULT.md').write_text('''# 443 — estado de ocultación tipado no mejora la respuesta

Tres casos protegidos/mixtos: 1/3 útil tanto baseline como variante. Inglés
describe correctamente el registro oculto; ES sigue negando acceso y la mezcla
se atribuye el color favorito a BAXY. Los siete controles conservan payload y
respuesta idénticos; dos nombres ES siguen incorrectos, no cuentan como verdes.
No adoptar fuente/proyección ni relajar la ocultación. Todos stop;13,328s,
GPU3175,5625MiB/RAM1208,7578125MiB, sin violaciones, registro intacto, cerrado.

444 cambia de familia reutilizando el GGUF Gemma publicado ya presente. Referencia
histórica astra-gemma-published midió otros nueve mensajes con prompt/historial de
entonces:4/9 bajo aquella adjudicación, nunca aceptación. No se borra ese rechazo.
El nuevo dato son once payloads de memoria actuales que fallan antes de guardas
con ambos tamaños de Qwen. No se descarga otra colección ni se cambian prompts.
La ficha oficial google/gemma-4-E2B-it, leída2026-09-08, documenta system nativo y
2,3B efectivos/5,1B con embeddings. No demuestra calidad ni consumo del GGUF
publicado por BAXY. Se reutilizan hash/revisión/perfil de astra-gemma-published;
no se incorpora adapter separado ni se presume equivalencia con el LoRA local.
https://huggingface.co/google/gemma-4-E2B-it
''',encoding='utf-8',newline='\n')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
(out/'PINS.json').write_text(json.dumps({p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'},indent=2)+'\n',encoding='utf-8',newline='\n')
source=(root/'scratchpad/c03-memory-roles438.py').read_text(encoding='utf-8')
idx=source.index("out=base/")
source=source[:idx]+'''added=set()
with (local/'C03-memory-redaction443-private/posts.jsonl').open(encoding='utf-8-sig') as f:
    for line in f:
        row=json.loads(line)
        if row['variant']=='baseline' and row['id'] in {'redacted-es','redacted-en','mixed-es'} and row['id'] not in added:
            added.add(row['id']);cases.append({'id':row['id'],'payload':row['payload'],'origin':'exact443 baseline native protected/mixed record'})
assert len(cases)==11
''' +source[idx:]
source=source.replace('astra-memory-roles438','astra-memory-gemma444').replace('C03-memory-roles438-private','C03-memory-gemma444-private')
source=source.replace('qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf','baxy-gemma4-e2b-published-f9b84ecd/gemma-4-E2B-it-Q4_K_M.gguf')
source=source.replace('00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4','9d4a5a653f2733a5faeb5f58a0e30bc064dfd569b0059cabb2547dbc4ba0f4b7')
start=source.index(" 'method':");end=source.index(" 'cases':",start)
source=source[:start]+''' 'method':'Eleven identical first-native payloads:8baseline438 plus3protected/mixed baseline443. Only GGUF changes to the existing published BAXY Gemma E2B asset. Native model template, unchanged inputs/sampler/output allowance and ngl99/KVq8_0/cache0/no-mmap. No separate adapter, source edits, offered tools/effects or manifest change. Composition diagnostic, not integrated/fresh acceptance.',
 'new_evidence':'Qwen4B/9B both fail attribution with current memory data; feedback and representation probes rejected438–443. Existing Gemma comparison covered other responsibilities and older prompts, so preserve its rejection while measuring this new target. Reuse its exact verified published GGUF/hash; official family card/system support rechecked2026-09-08 at https://huggingface.co/google/gemma-4-E2B-it. Card does not certify this published checkpoint.',
 'criteria':'All11 useful with correct subject/values/redaction, no extra effects or false access denial; every finish reason reviewed. All8 original controls remain explicit and three protected cases cannot be omitted. GPU3800MiB/freeRAM768MiB watchdog retained; resource absence blocks success. No promotion on native alone: guarded composition and product/regression/installed profile required.',
''' +source[end:]
start=source.index("        for variant in ['baseline','tool-return']:");end=source.index("            before=time.monotonic()",start)
source=source[:start]+'''        for variant in ['published-gemma']:
            payload=copy.deepcopy(case['payload'])
            assert payload==case['payload']
''' +source[end:]
target=root/'scratchpad/c03-memory-gemma444.py';assert not target.exists()
target.write_text(source,encoding='utf-8',newline='\n')
for name in ['CHECKPOINT.md','HANDOFF.md']:
 path=base/name;content=path.read_text(encoding='utf-8')
 start=content.index('## Siguiente acción');end=content.index('## Pendientes completos',start)
 content=content[:start]+'''## Siguiente acción
443redacción tipada1/3→1/3; sin fuente. 438–443rechazados y registrados.
444 preparado: GemmaE2Bpublicado existente, mismos11payloads (8baseline438,
3protegidos/mixtos443). Una familia distinta; conserva rechazo histórico4/9
de otras preguntas/prompts. No adapter nuevo/descargas/prompts/sampler. Hash
9d4a5a65/perfilngl99q8_0,cache0/no-mmap. Ejecutar c03-memory-gemma444.py;
no editar fuente durante modelo. Si mejora, guardas/producto yregresión antes
depromover; si falla no colección. Fuente436 vigente. Nombres/redactado abiertos.

''' +content[end:]
 content=content.replace('442 rechazado; diagnóstico443 preparado','443 rechazado; diagnóstico444 preparado').replace('No editar fuente durante443.','No editar fuente durante444.')
 path.write_text(content,encoding='utf-8',newline='\n')
path=base/'RELEVO_ACTIVO.json';record=json.loads(path.read_text(encoding='utf-8-sig'))
record.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),continuation='443 rejected1of3 unchanged;source436 unchanged.444 prepared: existing published Gemma,11 unchanged memory payloads438/443. Name/redaction still open; full C03 active.')
path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('443 recorded;444 prepared; source436 unchanged')
