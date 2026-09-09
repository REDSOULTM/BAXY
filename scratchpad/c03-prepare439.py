from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-memory-roles438'
(out / 'RESULT.md').write_text('''# 438 — rol tool no corrige el sujeto del recuerdo

Ocho pares, 16 primeras respuestas nativas. Baseline 5/8 útiles y variante
5/8 útiles: Jordan, Marta y Ana María siguen atribuidos al asistente. EN,
hermana, dos registros, enable y save conservan utilidad. Todos terminan stop.
Cambiar «Mi nombre es Jordan» por «Mi nombre guardado es Jordan» no corrige
el sujeto. No se adopta fuente ni se promueve runtime. 347 ya falló con 2507;
438 aporta el mismo rechazo con 3.5 y contrato literal 402. No repetir roles
ni la frase de procedencia de 349. El contrato literal no causó este fallo:
401 lo reproduce antes y después y sí mejora la conservación de valores EN.

10,594 s; GPU 3175,5625 MiB; RAM 1210,203125 MiB; sin violaciones, manifiesto
intacto, cliente cerrado. No acredita producto, UI, voz ni aceptación fresca.
Revisar cada respuesta en replies.jsonl; originales privados en PREREG.json.
''', encoding='utf-8', newline='\n')

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

(out / 'PINS.json').write_text(json.dumps({p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'}, indent=2) + '\n', encoding='utf-8', newline='\n')

source = (root / 'scratchpad/c03-memory-roles438.py').read_text(encoding='utf-8')
source = source.replace('import os\n', 'import os\nimport re\n')
source = source.replace('astra-memory-roles438', 'astra-memory-feedback439').replace('C03-memory-roles438-private', 'C03-memory-feedback439-private')
start = source.index(" 'method':")
end = source.index(" 'cases':", start)
source = source[:start] + ''' 'method':'Eight unchanged native first completions from438. Only a direct first-person name assertion equal to a non-BAXY observed record value receives one additional native call. Add the one preregistered factual correction to the existing system message; otherwise identical payload/settings. No source edits, no offered tools/effects, no generated user declarations. Native feedback diagnostic, not the production retry/publication path.',
 'new_evidence':'438 rejects tool roles on current3.5. Inherit compose_visible_defect/_payload_fact_defect and the existing bounded compose retry: detect contradiction against observed data, not a banned phrase or owner-name list. Self-Refine (https://arxiv.org/abs/2303.17651, v2, read2026-09-08) supports testing feedback/refinement, not success on this model: that paper uses LLM-generated feedback and other models; here feedback is deterministic and derived from a concrete contradiction.',
 'criteria':'All8 useful with no changed healthy payload, preserved values and third-party relation, no claim of new effects. One repair maximum per detected case; no seeds/sampling roulette. Evaluate every answer; no adoption if wrong subject remains or failures exchange. Source adoption additionally requires valid/invalid fact-check controls, actual bounded retry and product.',
 'correction':FEEDBACK,
''' + source[end:]
insertion = source.index("prereg={'utc'")
source = source[:insertion] + '''FEEDBACK = "You are BAXY. Do not identify yourself with a value read from private memory. Report the stored data in answer to the person's request."

def identity_conflict(answer, payload):
    try:
        situation=json.loads(fact_line(payload).removeprefix('situation: '))
    except (StopIteration,json.JSONDecodeError):
        return False
    if situation.get('operation') not in {'memory.recall','memory.list'} or situation.get('outcome')!='completed':return False
    records=situation.get('seen',{}).get('records',[])
    for record in records:
        value=record.get('value')
        if not isinstance(value,str) or not value.strip() or len(value)>256 or value.casefold() in {'baxy','[redacted]'}:continue
        pattern=r"^\\s*(?:mi nombre(?: guardado)? es|me llamo|my(?: saved)? name is)\\s+[\\\"'«“]?"+re.escape(value.strip())+r"(?=$|[\\s.!?,;:'\\\"»”])"
        if re.search(pattern,answer or '',re.IGNORECASE):return True
    return False

''' + source[insertion:]
start = source.index("        for variant in ['baseline','tool-return']:")
end = source.index("            before=time.monotonic()", start)
source = source[:start] + '''        variants=['baseline']
        for variant in variants:
            payload=copy.deepcopy(case['payload'])
            if variant=='feedback':
                payload['messages'][0]['content']+='\\n'+FEEDBACK
            else:assert payload==case['payload']
''' + source[end:]
needle = "            print(json.dumps(row,ensure_ascii=True),flush=True)"
source = source.replace(needle, needle + '''
            if variant=='baseline' and identity_conflict(row.get('answer'),payload):variants.append('feedback')''')
target = root / 'scratchpad/c03-memory-feedback439.py'
assert not target.exists()
target.write_text(source, encoding='utf-8', newline='\n')

for filename in ['CHECKPOINT.md', 'HANDOFF.md']:
    path = base / filename
    content = path.read_text(encoding='utf-8')
    content = content.replace('diagnóstico438', '438 rechazado; diagnóstico439 preparado')
    content = content.replace('No source edits mientras corra438 (exec session1112). No otros modelos/builds.', '438 recogido y cerrado; no procesos de modelo/producto/build activos. No editar fuente durante439.')
    start = content.index('## Siguiente acción')
    end = content.index('## Pendientes completos', start)
    content = content[:start] + '''## Siguiente acción
438 rechazado: 5/8→5/8, tres nombres ES aún atribuidos a BAXY. RESULT/PINS.
439 preparado: mismos8 baseline y sólo un feedback si el texto declara como
nombre propio un valor observado distinto de BAXY. No cambia respuestas válidas,
no reemplaza texto ni infiere que cada registro sea del usuario. Hereda guardas
factuales/reintento existente; no roles/procedencia ni retirada402. Antes de fuente,
medir diagnóstico, controles válidos/inválidos y posterior retry/producto real.
Ejecutar scratchpad/c03-memory-feedback439.py. Fuente436 sigue vigente.

''' + content[end:]
    path.write_text(content, encoding='utf-8', newline='\n')
path = base / 'RELEVO_ACTIVO.json'
record = json.loads(path.read_text(encoding='utf-8-sig'))
record.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), continuation='438 closed/rejected5of8 unchanged.439 prepared: one feedback on observed memory identity contradiction only; no source adoption. Source436, full C03 active.')
path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
path = base / 'ESTADO_PARA_DUENO_2026-09-08.md'
content = path.read_text(encoding='utf-8').replace('Estoy contrastando el resultado de la herramienta como dato separado de la\npetición. La prueba438 es diagnóstica; no implica que el problema ya esté resuelto.\nEl valor guardado no se está cambiando para corregir la frase.', 'La prueba438 de separar el resultado de la herramienta no mejoró la atribución\ny se descartó. La siguiente comprobación usa la corrección factual existente:\nel modelo debe informar el dato guardado sin adoptar ese nombre como identidad.\nEl valor guardado no se cambia para corregir la frase.')
path.write_text(content, encoding='utf-8', newline='\n')
print('438 recorded;439 prepared; checkpoint current; source unchanged')
