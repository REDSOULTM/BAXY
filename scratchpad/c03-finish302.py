from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import psutil

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-memory-product301-private'
rows=[json.loads(line) for line in (private/'capture/events.jsonl').read_text(encoding='utf-8-sig').splitlines()]
terminals=[row for row in rows if row.get('type')=='terminal']
assert len(terminals)==3
cases=json.loads((base/'astra-memory-product301/PREREG.json').read_text(encoding='utf-8'))['cases']
result={'adjudication':[{'request':text,**terminal,'useful':index<2} for index,(text,terminal) in enumerate(zip(cases,terminals))],
    'limitation':'Complete shared product with native inference, not a graphical UI observation or physical audio test. Third final is unhelpful; its raw candidate invents visits to Lima, so it must not be counted as a good response merely rejected by a guard.',
    'journal_operations':[]}
journal=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-memory-profile301/journal/missions.jsonl'
for line in journal.read_text(encoding='utf-8-sig').splitlines():
    envelope=json.loads(line)
    payload=envelope.get('payload',{})
    result['journal_operations'].append({key:payload[key] for key in ('phase','operation','operationName') if key in payload})
(base/'astra-memory-product301/RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
launch=json.loads((Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-ui302-private/LAUNCH.json').read_text(encoding='utf-8'))
app=psutil.Process(launch['app'])
assert abs(app.create_time()-launch['appCreateTime'])<.01
backends=[p for p in app.children(recursive=True) if p.name()=='llama-server.exe']
backend=[{'pid':p.pid,'createTime':p.create_time(),'command':p.cmdline()} for p in backends]
report='''# C03 — prueba de producto300–301 y reapertura302

300 no llegó a ejecutar turnos: el perfil de diagnóstico anidado fue rechazado
por WindowsPrivateStorage.PreparePrivateDataRoot, que exige un hijo directo de
LOCALAPPDATA/BAXY. Se preservó el fallo runtime_not_ready; no se presenta como
fallo del saludo.301 corrigió sólo la ubicación del perfil, sin relajar seguridad.

301 ejecutó tres casos de desarrollo mediante py main.py --conductor, source298/299,
runtime registrado2507, sesiones nuevas entre casos y sin inyección de decisiones.
Modelo/manifest sin cambios. Dos de tres respuestas útiles:

- me llamo emmanuel, dime hola emmanuel → Hola Emmanuel, ¿cómo estás? 😎
- me llamo Albeda → ¡Hola Albeda! ¿En qué puedo ayudarte hoy? 😎
- my favorite city is Lima → Lima (NO útil).

Todos terminaron publicados sin timeout ni fallo de composición, lo que no hace
correcto al tercero. Su primera respuesta bruta inventa «I’ve been there a few
times» y pregunta por un lugar favorito. El retry devuelve sólo «Lima». No aceptar
la primera por ser más larga ni relajar veracidad; tampoco contar la publicación
como respuesta correcta. Revisar payload/contexto y primera transformación exacta
antes de otra regla de palabras. Contraste298 sin historial daba otro borrador;
no son payloads idénticos ni una comparación causal del modelo.

Capturas y perfil completos privados, referencias y adjudicación mínima en
astra-memory-product301. Conductor NO acredita píxeles de UI ni audio físico.
No se pidieron escrituras de memoria. RESULT.json resume operaciones del journal.

302 reabre py main.py sin probe, override ni temporizador para que el dueño use
BAXY. Se verificó proceso y ventana BAXY, y bienvenida compuesta publicada t0.
No se enviaron mensajes del agente a esa nueva instancia. Cuestionario742 sigue
disponible en http://127.0.0.1:63179/ y sus marcas permanecen intocadas.

Validación vigente:1022pass0skip5,65s Python298;1879pass0skip2m25s .NET299;
Fast299 VERDE con build19,33s0warn/error. No nuevo Full ni publicación/promotion.
Los fallos de París, atribución del nombre, conocimiento/memoria contextual, demás
rutas y criterios de aceptación integral mantienen C03 EN_CURSO.
'''
(base/'PRODUCTO_Y_REAPERTURA300_302.md').write_text(report,encoding='utf-8')
checkpoint='''# C03 — checkpoint302 — EN_CURSO

Últimos informes: SALUDO_Y_PREGUNTAS297_298.md, MEMORIA_CONVERSACIONAL299.md,
PRODUCTO_Y_REAPERTURA300_302.md. Fuente298 corrige restatement comparando cada
pregunta y no la respuesta entera.299 deja AskToSave pasar la petición completa
a la política semántica; persistencia explícita y barreras memory.* permanecen.

Validación: Python tres suites1022pass0skip5,65s; .NET shell/parser/plan1879pass,
0skip2m25s; Fast299integrado VERDE,build19,33s0warn/error. Fast298anterior falló
porque UI293 bloqueaba Core; logs conservados, árbol verificado detenido y snapshot
privado298. No Full durante reparación. No fuente posterior299.

301 producto real compartido: saludo emmanuel y Albeda útiles; Lima sólo «Lima»
NO útil. Primer rawLima inventa visitas personales, retry de baja información.
300 falló antes de turnos por perfil anidado;301 usa hijo directo legítimo.
No claim UI/audio desde conductor ni aceptación/promotion. Próximo diagnóstico:
raw301/contexto real frente a298 para Lima y atribución de roles. No otra barrida
de modelos/prompts/regex sin frontera causal; evitar aceptar experiencia inventada.

UI293 fue detenida preservando logs. UI302 reabierta por py main.py, disponible
sin timer ni override; ventana BAXY y bienvenida t0 verificadas. No controles
agente en302. Ver RELEVO_ACTIVO para PIDs/creación/backend. Logs privados:
%LOCALAPPDATA%/BAXY/C03-ui302-private. No usar backend con /slots activo.

Sesión humana264 íntegra:121mensajes(63dueño58BAXY), TRANSCRIPT282.json/.md en
%LOCALAPPDATA%/BAXY/C03-owner264-heap280. No subir heap ni texto completo.
Cuestionario742 http://127.0.0.1:63179/ PID101140 SIN cierre automático,200verificado.
answers.json del dueño en C03-owner-questionnaire-20260907: no borrar, sobrescribir,
rellenar ni congelar. Autoría/capacidad separadas; tres ingleses admitidos vigentes.

Antecedentes292–296: selector2507 17/18 (win07wrongwindow.active); schemas29414/18
rechazados; proyección295no útil. UI293 Parísclarificacióninnecesaria y «quien soy»
→«Soy usuario,en el dominio REDNOTE» atribuciónincorrecta.284 conservaba nombre pero
no rol. Diagnósticos289–291abstenciónrequired rechazados, no repetir descriptor.

Goal-c03/HEAD2bf3d4c, preservar WIP/main. Recursos260:3516,66MiBGPU/4822,60MiBRAM
con captura/AEC/Piper sin ASRhumano; no medición conjunta nueva302. Wake sin certificar.
Pendiente objetivo completo: ocho rutas útiles,100/100humanos frescos sin congelar,
averías/recuperación, UI/voz/ASR/recursos finales, runtime/instalación,
continuidadC04–C09, Full y publicación fuera main. Sin bloqueo externo.
'''
for name in ('CHECKPOINT.md','HANDOFF.md'):
    (base/name).write_text(checkpoint,encoding='utf-8')
p=base/'RELEVO_ACTIVO.json'
record=json.loads(p.read_text(encoding='utf-8'))
record.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='302: source298/299 adopted; 1022 Python and1879 .NET pass,Fast299green; native product301 greeting fixed, Lima unhelpful; UI302 reopened.',continuation='Keep UI302 and questionnaire available; diagnose actual301 Lima false experience/low-information retry and293 identity role. Whole C03 still active.')
record['userOwnedInstance']={'pid':app.pid,'createTime':app.create_time(),'launcher':launch['launcher'],
    'automaticClose':False,'privateLogs':str(Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-ui302-private'),
    'status':'running','processRevalidated':True,'backends':backend,
    'instruction':'Keep open for owner use; no agent controls sent to302; inspect slots before sharing model.'}
p.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
files=['src/baxy_mind/llm.py','src/Baxy.App/MainWindowViewModel.cs','tests/test_turn_policy.py',
    'tests/Baxy.Integration.Tests/MindShellEndToEndTests.cs','tests/fixtures/mind_turn_contract/baxy_mind/__main__.py',
    'artifacts/comprobaciones/C03/astra-question-scope298/NATIVE_RESULT.json',
    'artifacts/comprobaciones/C03/astra-memory-route299/owners-corrected.log',
    'artifacts/comprobaciones/C03/astra-memory-route299/fast.log',
    'artifacts/comprobaciones/C03/astra-memory-product301/RESULT.json']
pins={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files}
(base/'TRAMO297_302_PINS.json').write_text(json.dumps(pins,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'app':app.pid,'backend':backend,'journal':result['journal_operations']},ensure_ascii=True))
