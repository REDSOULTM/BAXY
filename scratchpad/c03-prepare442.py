from pathlib import Path
import hashlib
import json

root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
out=base/'astra-memory-9b441'
(out/'RESULT.md').write_text('''# 441 — 9B no mejora la atribución y cuesta más

Mismos ocho payloads438, sin cambios de prompt o muestreo. 5/8 útiles: las tres
lecturas españolas siguen atribuyendo Jordan/Marta/Ana María a BAXY. Los otros
cinco controles mantienen utilidad; todos stop. 48,36s, GPU3010,3125MiB,
RAM4007,27734375MiB; sin violaciones, registro intacto, cliente cerrado.
No promover ni repetir modelo9B para este fallo. La comparación con4B438 es
de composición nativa, no consumo/latencia del producto entero.

442 vuelve a4B y cambia una sola entrada de composición: omite la pregunta
original sólo ante lectura privada completada, conservando situation, contrato,
idioma y muestreo. Es el alcance de _compose_user_content(include_request=False)
ya heredado por acting, sin respuesta fija ni feedback/guardia. Hipótesis:
releer la pregunta personal en una fase que ya tiene un resultado puede hacer
que el modelo resuelva identidad en lugar de narrar los registros. Se contrasta,
no se presupone; la hermana y los múltiples registros son controles necesarios.
''',encoding='utf-8',newline='\n')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
(out/'PINS.json').write_text(json.dumps({p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'},indent=2)+'\n',encoding='utf-8',newline='\n')
source=(root/'scratchpad/c03-memory-roles438.py').read_text(encoding='utf-8')
source=source.replace('astra-memory-roles438','astra-memory-result-scope442').replace('C03-memory-roles438-private','C03-memory-result-scope442-private')
start=source.index(" 'method':");end=source.index(" 'cases':",start)
source=source[:start]+''' 'method':'Eight paired native first completions from438. Only for completed memory.recall/list, omit the original first-line user request from composition; preserve all observed data, system, language, literal contract and sampling. Enable/save controls are identical payloads. Existing include_request=False mechanism used by acting is the inheritance; no code changes, tools/effects, validator/retry or runtime promotion.',
 'new_evidence':'441 existing9B repeats the three ES name attribution errors with more RAM.439/440 feedback rejected. Current438 payload combines the natural personal question and an already completed read. Isolate whether reinterpreting that question causes the subject error; this is data/request scope, not another feedback, provenance phrase or tool-role variation.',
 'criteria':'All8 useful and values/relations/counts preserved; no changed enable/save payload. No new effect claim, assistant-name attribution, leaked protocol or value denial. Every response judged, all finish reasons/resources recorded. Adoption requires guarded composition and real product with further read scope/empty/redacted/query controls.',
''' + source[end:]
start=source.index("        for variant in ['baseline','tool-return']:");end=source.index("            before=time.monotonic()",start)
source=source[:start]+'''        for variant in ['baseline','result-scope']:
            payload=copy.deepcopy(case['payload'])
            if variant=='result-scope':
                situation=json.loads(fact_line(payload).removeprefix('situation: '))
                if situation.get('operation') in {'memory.recall','memory.list'} and situation.get('outcome')=='completed':
                    payload['messages'][-1]['content']=payload['messages'][-1]['content'].split('\\n',1)[1]
                else:assert payload==case['payload']
            else:assert payload==case['payload']
''' +source[end:]
target=root/'scratchpad/c03-memory-result-scope442.py';assert not target.exists()
target.write_text(source,encoding='utf-8',newline='\n')
print('441 rejected/recorded;442 prepared; source unchanged')
