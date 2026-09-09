from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-memory-refine440'
(out/'RESULT.md').write_text('''# 440 — el refinamiento intercambia el fallo; no se adopta

Ocho casos, once llamadas. Jordan y Marta se atribuyen correctamente tras ver
el borrador; Ana María se pierde y la respuesta niega un dato presente. 5/8→7/8,
pero el criterio exigía conservar los ocho y los hechos. Todos stop. 7,453 s,
GPU3173,5625MiB, RAM1203,80078125MiB, sin violaciones, manifiesto intacto.
Cliente cerrado. No fuente ni guarda de nombres adoptadas. 439/440 cierran la
estrategia de feedback: no añadir más variantes de instrucciones/reintentos.

El compositor de estados excluye deliberadamente la conversación (C#CreateFacts
y Python prompt_facts). Agregar historia puede dar información de atribución,
pero una lectura de datos persistidos también debe funcionar en sesión nueva:
no se fabrica diálogo humano ni se hace depender el dato de una charla anterior.

441 reutiliza el único9B ya disponible y su perfil medido390. Son otros payloads:
composición de memoria actual sin tools, frente al selector AUTO de390. El rechazo
390 se conserva: no certifica ni impide medir esta función. Comparación acotada
antes de cualquier decisión de runtime, sin colección de modelos/descargas.
''',encoding='utf-8',newline='\n')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
(out/'PINS.json').write_text(json.dumps({p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'},indent=2)+'\n',encoding='utf-8',newline='\n')
source=(root/'scratchpad/c03-memory-roles438.py').read_text(encoding='utf-8')
source=source.replace('astra-memory-roles438','astra-memory-9b441').replace('C03-memory-roles438-private','C03-memory-9b441-private')
source=source.replace('qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf','qwen35-9b-03b74727/Qwen3.5-9B-Q4_K_M.gguf')
source=source.replace("BAXY_MIND_NGL=str(config['ngl'])", "BAXY_MIND_NGL='14'")
source=source.replace('00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4','03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8')
start=source.index(" 'method':");end=source.index(" 'cases':",start)
source=source[:start]+''' 'method':'Eight identical first-native payloads from438: compare its current4B baseline with the existing9B asset at partial ngl14, inherited390. No prompt, data, sampling, token count, roles, validators, source or manifest edits. Current425 cache0/no-mmap retained. No tools offered or effects. Capability/resource diagnostic; not guarded product/UI/voice/fresh acceptance.',
 'new_evidence':'438 and439/440 reject roles and feedback for the current memory composition defect.390 tested a different responsibility: native AUTO selector with historical identity answers; this does not resolve whether9B can compose memory records accurately. Reuse388 model-specific research and390 measured loading profile; no additional models downloaded. See440 RESULT for strategy change.',
 'criteria':'All8 semantically useful, literal values/third-party relation preserved, no assistant-name attribution or extra effects. Review all responses and finish reasons. Report extra RAM and time honestly; a pass here only permits integrated comparison, never promotion. Keep3800MiB GPU watchdog and768MiB system free RAM.120s diagnostic timeout does not certify product latency.',
 'ngl':14,
''' +source[end:]
start=source.index("        for variant in ['baseline','tool-return']:")
end=source.index("            before=time.monotonic()",start)
source=source[:start]+'''        for variant in ['9b-ngl14']:
            payload=copy.deepcopy(case['payload'])
            assert payload==case['payload']
''' +source[end:]
source=source.replace('client.begin_request(40)','client.begin_request(120)').replace("'request_seconds':40","'request_seconds':120")
target=root/'scratchpad/c03-memory-9b441.py';assert not target.exists()
target.write_text(source,encoding='utf-8',newline='\n')
for filename in ['CHECKPOINT.md','HANDOFF.md']:
 path=base/filename;content=path.read_text(encoding='utf-8')
 content=content.replace('438 rechazado; diagnóstico439 preparado','440 rechazado; diagnóstico441 preparado')
 content=content.replace('438 recogido y cerrado; no procesos de modelo/producto/build activos. No editar fuente durante439.','438–440 recogidos y cerrados; no modelo/producto/build activo. No editar fuente durante441.')
 start=content.index('## Siguiente acción');end=content.index('## Pendientes completos',start)
 content=content[:start]+'''## Siguiente acción
438 roles5/8→5/8 rechazado;439 feedbacksistema5/8→6/8;440 feedbackconborrador
5/8→7/8 pero pierde AnaMaría y niega memoria. RESULT/PINS; ninguna guarda de
nombres ni prompt/retry nuevo adoptados. Abandonar roles/procedencia/feedback.
441 preparado: mismos8payloads438 en9B ya disponible, perfil390ngl14/no-mmap;
425cache0 conserva el ajuste RAM. Otra responsabilidad que390AUTO; comparar sólo
esta composición, no adoptar runtime sin producto/regresión/recursos. 120s por
request diagnóstico no acredita latencia de producto. Ejecutar c03-memory-9b441.py.
Fuente436 vigente. La memoria debe servir también en sesión nueva, sin fabricar
declaraciones humanas ni depender del historial para interpretar datos guardados.

''' +content[end:]
 path.write_text(content,encoding='utf-8',newline='\n')
path=base/'RELEVO_ACTIVO.json';record=json.loads(path.read_text(encoding='utf-8-sig'))
record.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),continuation='440 rejected:7of8 but loses stored name. No guard/source adopted.441 prepared: reuse existing9B profile390 for the8 unchanged memory payloads438. Source436, full C03 active.')
path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('440 recorded, feedback abandoned,441 prepared; source unchanged')
