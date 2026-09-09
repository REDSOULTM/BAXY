"""Preserve191 observation,192 source/tests and193 native feedback outputs."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import psutil

root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
def sha(path):
    with path.open('rb') as handle:return hashlib.file_digest(handle,'sha256').hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not any(p.info['name'] in {'Baxy.exe','llama-server.exe','piper.exe'} for p in psutil.process_iter(['name']))
out=base/'astra-source192-snapshot';out.mkdir(exist_ok=False)
sources=['src/baxy_mind/voice.py','src/baxy_mind/llm.py','src/Baxy.App/MainWindowViewModel.cs','src/Baxy.App/TurnVisibleFacts.cs','tests/test_mind_voice_runtime.py','tests/test_compose_contract.py','tests/Baxy.Integration.Tests/VoiceFeedbackTests.cs']
snapshot=[]
for name in sources:
    source=root/name;copy=out/name;copy.parent.mkdir(parents=True,exist_ok=True);copy.write_bytes(source.read_bytes())
    snapshot.append({'source':name,'snapshot':str(copy.relative_to(root)),'sha256':sha(copy)})
logs=['c03-feedback192-red.log','c03-feedback192-python.log','c03-feedback192-python-retry.log','c03-feedback192-dotnet.log','c03-feedback192-dotnet-retry.log','c03-feedback192-dotnet-owner.log','c03-feedback192-fast.log','c03-feedback193-policy.log']
for name in logs:(out/name).write_bytes((Path(os.environ['TEMP'])/name).read_bytes())
save(out/'INDEX.json',snapshot)
text='''# C03 — observación independiente y respuestas de voz compuestas —191–193

Fuente192 adopta localmente la retirada de dos respuestas TTS fijas. El motor
de voz conserva eventos de escucha/transcripción dudosa; la aplicación redacta
su respuesta mediante la cola y política compartidas. No hay cambio de AEC,
umbrales, modelo, voces o manifiesto registrado. Audio183 sigue pendiente.

## Observación191: no confundir transcripción con corte

Nemotron ya instalado, CPU6/greedy/auto, flush0,66s; mismo PCM original187 y
ventanas físicas189, crudo y normalizado.16lecturas sin pistas; sesión51364exit0.
Se conservan todas las variantes en astra-observe191, no sólo las favorables.

| Salida | Origen | Crudo | Normalizado |
|---|---|---|---|
'''
rows=json.loads((base/'astra-observe191/RESULTS.json').read_text(encoding='utf-8'))
assert len(rows)==16
for output in range(1,5):
    for condition in ['original','loopback']:
        pair=[r for r in rows if r['output']==output and r['condition']==condition]
        text+=f"| {output} | {condition} | {pair[0]['text'] or '(vacío)'} | {pair[1]['text'] or '(vacío)'} |\n"
text+='''
La hora inglesa se recupera completa en loopback crudo/normalizado, donde
Parakeet189 sólo reconoció «It is ten». Esto sustenta que esa lectura incompleta
no acredita otro corte. No borra el barge_in183 ni certifica toda la voz.
Nemotron también comete errores(«105» para10:55); tampoco es observador infalible.

## Cambio192 y ownership

VoiceEngine ya no pronuncia literalmente «Sí.» ni «¿Puedes repetirlo?».
Emite wake y ignored/transcript_doubtful como antes. TurnVisibleFacts transforma
sólo esos dos eventos en borradores conversation/clarification con causas
voice_wake_listening/voice_transcript_uncertain. Wake_detected, fondo ignorado,
turno no autorizado y barge_in no generan una respuesta añadida.

MainWindowViewModel usa PendingModelMessageQueue existente; no espera al modelo
en el callback UI. No inventa un pedido con la petición anterior: userText vacío,
sin contexto previo. El aviso caduca si cambia el turno; el acuse de wake también
si termina escucha. Pedir repetición sigue permitido después de cerrar captura.
La publicación compartida es la que conserva políticas y solicita TTS.
Llm proyecta las causas observadas como hechos; no fija la frase que se publica.

## Validación

Rojo antes de fuente:2fallos/85deseleccionados/1,15s, ambas frases fijas emitidas.
Primer Python falló por import pytest ausente; primer .NET por referencia vieja
del método renombrado. Se corrigieron ambos y se guardan sus logs.

Python registrado: `-m pytest tests/test_mind_voice_runtime.py
tests/test_compose_contract.py -q`:113pass,0skips,6,94s.
.NET Release filtro VoiceFeedbackTests|ModelMessage|FieldProductHonestTerminal:
14pass0skips808ms; tras añadir como controles las dos respuestas reales193,
16pass0skips946ms(sesión11832exit0). Incluye caducidad por nueva petición/fin de
escucha, ausencia de respuestas por ruido/intermedios y aceptación de prosa
compuesta. No es prueba acústica ni UI real.

`scripts/test_source_quality.ps1`: Fast32127exit0, todas las etapas verdes;
Release17,10s,0avisos/errores. Después sólo se añadieron dos TestCase literales,
compilados y ejecutados en el pase16. No nuevo Full durante reparación.

## Modelo real193

LlmRuntime.compose_user_message actual, Qwen3.5 override/perfil existente,
hechos nuevos y userText vacío; guardas/reintentos normales, sin prompts nuevos.
Sin App/UI/audio/operaciones. Se capturan payloads HTTP y respuestas completas.

| Evento | Respuesta literal | Tiempo | Adjudicación |
|---|---|---:|---|
'''
results=json.loads((base/'astra-feedback193/RESULTS.json').read_text(encoding='utf-8'))
for r in results:
    assert 'error' not in r
    verdict='Acuse de disponibilidad útil; no afirma ejecución.' if r['case']=='wake' else 'Pide repetir lo no entendido, sin inventar contenido.'
    text+=f"| {r['case']} | {r['text']} | {r['seconds']:.3f}s | {verdict} |\n"
text+='''
Comando193exit0;6,093s total,GPU3171,56MiB,RAM3203,63MiB,registro intacto.
Estas mismas dos frases fueron aceptadas por el compositor/política C# en el
pase16. No se presentan como prueba de publicación de la cola con UI real,
audio físico, reserva humana o ocho rutas finales.2/2 nativas útiles.

## Herencia y continuación

Se localizó sólo en lectura scripts/stt_real_voice_eval.py de Probando Gemma4.
Declara corpus data/stt_eval/real_mic/manifest.tsv y real_es, pero el manifest
real_mic no existe en esa ruta. No se deduce procedencia ni disponibilidad de
audios por el reporte histórico. No se tocó otro repositorio ni se descargó nada.

Siguiente: comprobar publicación por el recorrido App/cola sobre fuente192 y
continuar el bloqueo acústico183 con señales conservadas; DTLN128 aún experimental,
mezcla129 sigue discrepante. No regenerar187 para resolver la lectura inglesa:
191 ya aporta el observador independiente. No ejecutar scripts con hashes172.
Pendientes íntegros C03: ocho rutas finales,100humanos congelados y100/100, averías,
voz/entrada/wake/UI/4GB, promoción/instalación/continuidadC04–C09, Full y publicación.
'''
(base/'PRUEBAS_FEEDBACK191_193.md').write_text(text,encoding='utf-8')
for stage,label in [(191,'observe'),(193,'feedback')]:
    log=f'c03-{label}{stage}.log';(base/f'astra-{label}{stage}'/log).write_bytes((Path(os.environ['TEMP'])/log).read_bytes())
public=[base/'PRUEBAS_FEEDBACK191_193.md',out/'INDEX.json']+[out/name for name in logs]+[root/row['snapshot'] for row in snapshot]
for folder,names in {
 'astra-observe191':['PREREG.json','RESULTS.json','COMPLETE.json','c03-observe191.log'],
 'astra-feedback193':['PREREG.json','RESULTS.json','CLEANUP.json','posts.jsonl','c03-feedback193.log'],
}.items():public.extend(base/folder/name for name in names)
public.extend(root/'scratchpad'/name for name in ['c03-observe191.py','c03-feedback193.py'])
old=json.loads((base/'TRAMO182_190_PINS.json').read_text(encoding='utf-8'))
assert all(sha(root/r['path'])==r['sha256'] for r in old['public'])
assert all(sha(Path(r['privatePath']))==r['sha256'] for r in old['private'])
save(base/'TRAMO191_193_PINS.json',{'public':[{'path':str(path.relative_to(root)),'sha256':sha(path),'bytes':path.stat().st_size} for path in public],'private':[]})
note='''# Actualización193 — fuente192 validada localmente; C03 EN_CURSO

191 completo16lecturas: Nemotron recupera inglés187 completo en loopback; la
lectura Parakeet189 incompleta no acredita corte.183 y mezcla129 siguen abiertos.
Fuente192 retira dos TTS fijos, conserva eventos, App/cola existente compone
hechos y descarta avisos obsoletos. Sin AEC/umbrales/modelo/runtime nuevos.
Python113pass0skips6,94s; .NET final16pass0skips946ms; Fast32127exit0,
Release17,10s0avisos/errores. Dos nuevosTestCase193 compilados/pasados despuésFast.
193 nativo Qwen3.5: «Estoy listo para ayudarte con lo que necesites.»0,547s;
«¿Podrías repetir lo que dijiste?»0,344s. Política C# acepta ambas. GPU3171,56MiB.
No publicación UI/audio acreditada por193. PRUEBAS_FEEDBACK191_193.md e
TRAMO191_193_PINS.json + astra-source192-snapshot fijan fuente/tests/logs.
182_190pins íntegros. Todos procesos recogidos/terminados, ninguno propio activo.
Siguiente: comprobar App/cola con fuente192; continuar audio183 sin reinterpretar
191 como arreglo. No repetir187 para la lectura inglesa ni scripts de fuente172.
Este turno fue progreso: corrección192 + evidencia191/193. Goal íntegro activo.

'''
for name in ['CHECKPOINT.md','HANDOFF.md']:
    path=base/name;path.write_text(note+path.read_text(encoding='utf-8'),encoding='utf-8')
path=base/'RELEVO_ACTIVO.json';state=json.loads(path.read_text(encoding='utf-8'))
state.update(goalStatus='active',confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='Fuente192 adoptada localmente: voz sin dos TTS fijos,cola/composición hechos,avisos caducables.113Python/16.NET/Fast verdes.193dos respuestas nativas útiles;191 inglés recuperado.',continuation='Verificar publicación App/cola y continuar bloqueo acústico183. Sin procesos activos. No reejecutar fixtures que fijan fuente172; C03 íntegro.')
save(path,state)
print(json.dumps({'publicPins':len(public),'priorPinsVerified':True,'sourceSnapshot':len(snapshot),'goal':'active'}))
