from pathlib import Path
import datetime
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
panel = base / 'astra-files74-veto'
paired = json.loads((panel / 'paired.json').read_text(encoding='utf-8'))
lines = ['# C03 — validación integrada del veto74', '',
    '6/10 útiles frente a5/10 en72. Se recupera t3 con exactamente el primer borrador que72 vetó. '
    'Fuente63 + Python74; Qwen3.5 sigue como override sin promoción. Selector/historial/prompts intactos. '
    '123,12s, GPU3177,56MiB, RAM6983,55MiB, exit0; registro intacto. No UI/voz/audio físico ni reserva humana.', '',
    'Aceptado el arreglo local de falsos vetos: t3 publica la causa UTF8 real. C03 completo sigue abierto. '
    't6/t7 fallan en conversation_reply con HTTPError y t10 en turn_preparation con HTTPError. '
    'El hook47 no capturaba excepciones;75 instrumenta ese punto antes de inferir una causa. '
    't9 sigue vetado por hechos adicionales: no se ha relajado extra_claim.', '']
for turn in paired:
    useful = turn['turnId'] in {'t1', 't2', 't3', 't4', 't5', 't8'}
    labels = [e['label'] for e in turn['publicEvents'] if e.get('type') == 'boot_stage' and e.get('label')]
    lines += [f'## {turn["turnId"]} — {"útil" if useful else "no útil"}', '',
              f'Entrada: {turn["request"]}', '', f'Final literal: {turn["final"]}', '',
              f'Labels de progreso publicados: {json.dumps(labels, ensure_ascii=False)}', '']
lines += ['## Validación de fuente', '',
    'Python312 -m pytest tests/test_compose_contract.py tests/test_c03_request_preservation.py '
    'tests/test_turn_policy.py -q:1105 pass/0 skips/5,67s. Fast70202exit0, Release2,86s, '
    '0 avisos/errores. Full no ejecutado durante reparación. Los logs están junto a este panel.', '']
report = base / 'PRUEBAS_VETO74.md'
report.write_text('\n'.join(lines), encoding='utf-8')
for name in ('c03-veto74-pytest.log', 'c03-veto74-fast.log'):
    (panel / name).write_bytes((Path(os.environ['TEMP']) / name).read_bytes())
files = [report, panel / 'PREREG.json', panel / 'RESULT.json', panel / 'paired.json',
         root / 'src/baxy_mind/llm.py', root / 'tests/test_compose_contract.py',
         panel / 'c03-veto74-pytest.log', panel / 'c03-veto74-fast.log']
(base / 'TRAMO74_PINS.json').write_text(json.dumps({'scope': 'Integrated Python veto repair; C03 remains open',
    'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}, indent=2), encoding='utf-8')
for current, historical in [('CHECKPOINT.md', 'CHECKPOINT_HISTORICO_HASTA67.md'),
                             ('HANDOFF.md', 'HANDOFF_HISTORICO_HASTA67.md')]:
    archive = base / historical
    assert not archive.exists(), historical
    archive.write_bytes((base / current).read_bytes())
(base / 'CHECKPOINT.md').write_text('''# C03 — CHECKPOINT — veto74 y diagnóstico HTTP75 — EN_CURSO

Tarea01a07974-2a33-7ed3-ba87-2436944e8115, continuación de01a074f6-9e0e-7fb3-8282-a6b706198a7e.
RamaGoal-c03, HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. Goal activo.
WIP/ajeno/evidencia preservados; sin commit/push; main excluida. Sin bloqueo externo.
Autoridad C03_ASTRA_AUTORIDAD.md/C03_RESPUESTA_VERAZ.md, identidad y AGENTS.
Historia íntegra en CHECKPOINT_HISTORICO_HASTA67.md y sus referencias.

## Actual

Fuente58 + guard proveedor63 + Python74.74 retira el sustantivo ordinario operation
del veto de metatexto y hereda la distinción C#52 entre failed/fallo afirmado y negado.
No cambios a selector, catálogo, historial, prompts ni runtime registrado.
Rojo2 fail/1 pass; después21 pass. Tres suites dueñas1105 pass/0 skips/5,67s.
Fast70202exit0, Release2,86s,0 avisos/errores. No Full.
Producto files74-veto terminó48789exit0:6/10 útiles frente a5/10 de72.
T3 publica literalmente el primer borrador fiel vetado en72; UTF8 recuperado.
123,12s, GPU3177,56MiB,RAM6983,55MiB,registro intacto. Qwen3.5 sólo override,
NO promovido. PRUEBAS_VETO74.md/TRAMO74_PINS.json conservan resultado/fuente/logs.

75 en ejecución91075: files75-http, misma fuente74/override10casos; hook75 lee
HTTPError.code y body BytesIO con getvalue sin consumir/alterar el error.
72/74 t6/t7 dan HTTPError en conversation_reply; t10 en turn_preparation.
Hook47 registraba sólo éxitos, no hay paquetes fallidos en su wire. Recoger
errores75 antes de atribuir causas o tocar modelo/prompts. No builds paralelos.
T9 sigue rechazado correctamente: payload sólo audio, borrador añade hora/CPU.

## Decisiones cerradas

68 refuta borrar respuestas previas: referencias5/6 completo,1/6 sólo usuarios,
1/6 sin contexto.69/70 clasificador needs_dialogue5/10 con/sin schema, descartado.
71 Qwen3.5 nativo9/10 vs6/10 registrado; pide lectura ante porqué, fallo real.
72 producto5/10, no promoción;73 fuente tipada en contenido de historial8/10
vs6/10, pero file2/file3 siguen search. No implementar como solución completa.
PRUEBAS_REFERENCIAS_Y_MODELO68_71.md/TRAMO68_71_PINS.json y
PRUEBAS_PRODUCTO_Y_HECHOS72_73.md/TRAMO72_73_PINS.json fijan evidencia.
65–67 frases/roles/descripción no bastan, no repetir. No detector de referencias
por is_elliptical_followup: sólo reconoce preguntas, no hazlo/close that.

## Runtime, reserva y cierre pendiente

Registro intacto: Qwen3-4B-Instruct-2507 Q4_K_M,b9980CUDA12.4,KVq8,ngl99,3x4096.
Manifest SHA13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed.
Core AOT63 SHAfe2c1cfc351abf78bd4d5080fd651eaec2e5915f83b82a30613a57df40e48fed.
Conductor no acredita UI ni voz/audio físico; techo conjunto final4GB pendiente.
«Son turnos validos» sólo para tres textos de ADMISIBILIDAD_DUENO_2026-09-06.md,
ya registrado; no preguntar ni extender a742. Pool privado742/239 candidatos
no descartados, selección100 pendiente; reusar auditorías45. Sin cuotas artificiales.
Faltan8rutas,100humanos frescos congelados y100/100 útiles, averías/recuperación,
UI/voz/audio físico+recursos, continuidadC04–C09, Full verde final y publicación
fuera de main. No Full durante reparación, no cierre parcial de C03.
No basename exterior->interior; path.ensure.absent puede borrar, no es búsqueda.
Nombre sin coincidencias y progreso que infiere UTF8 del nombre siguen pendientes.
''', encoding='utf-8')
(base / 'HANDOFF.md').write_text('''# Handoff — C03 — tramo74/75 — 2026-09-07

Goal activo, tarea01a07974-2a33-7ed3-ba87-2436944e8115, ramaGoal-c03,
HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. CHECKPOINT manda.
Preservar WIP/ajeno/evidencia, sin commit/push, main excluida. No bloqueo externo.

Fuente58+guard63+Python74. La causa UTF8 ahora se publica en files74-veto/t3;
antes72 se vetaba «the operation»/«failed». Se hereda negación C#52, sin prompts.
1105pytest pass/0 skips/5,67s; Fast70202exit0,Release2,86s,0 avisos/errores.
Producto74:6/10 útiles,48789exit0,123,12s,GPU3177,56MiB,RAM6983,55MiB.
Qwen3.5 sigue override, registro2507 intacto. No Full, UI/audio ni reserva100.
PRUEBAS_VETO74.md/TRAMO74_PINS.json incluyen fuente y resultados verificables.

75 ejecución91075, files75-http: mismo panel/fuente74 con hook75 capturando
errores HTTP sin consumirlos.72/74 fallan t6/t7 conversation_reply y t10
turn_preparation; hook47 no registraba paquetes fallidos. Recoger RESULT,
paired y httpError en wire antes de decidir. No procesos/builds paralelos.

No reabrir: eliminar respuestas rompe referencias68; clasificador previo69/70
5/10 descartado; modelo71 nativo9/10 pero producto72 5/10; hechos en historial73
8/10 pero file2/file3 siguen fallando. No fuente de selector/historial cambiada.
PRUEBAS_REFERENCIAS_Y_MODELO68_71.md y PRUEBAS_PRODUCTO_Y_HECHOS72_73.md.

Tres textos ingleses admitidos, no repetir pregunta ni extender a742.
Pendiente cierre entero:8rutas,reserva100 fresca/100útiles,averías/recuperación,
UI/voz/audio físico y4GB conjuntos,continuidadC04–C09,Full verde y publicación.
No Full durante reparación. Historia previa HANDOFF_HISTORICO_HASTA67.md.
''', encoding='utf-8')
relay = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    checkpoint='Veto74 validado; HTTP75 en ejecución; C03 completo EN_CURSO',
    continuation='Fuente58+63+74, modelo Qwen3.5 sólo override. Capturar causa HTTP t6/t7/t10. No Full durante reparación; cierre integral pendiente.')
(base / 'RELEVO_ACTIVO.json').write_text(json.dumps(relay, ensure_ascii=False, indent=2), encoding='utf-8')
