from pathlib import Path
import json
import hashlib

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
rows = json.loads((base / 'astra-polarity52/paired.json').read_text(encoding='utf-8'))
assert len(rows) == 7 and all(r['terminal'] == 'published_final' for r in rows)
lines = ['# C03 — polaridad52: entradas y respuestas literales', '',
         'Mismos siete controles técnicos de51, no reserva humana ni UI/audio físico. '
         '**7/7 turnos completos útiles**, incluyendo los avisos de progreso. '
         'Cada respuesta se cotejó con completedStepsInOrder de su auditoría; '
         'astra-polarity52/paired.json conserva observaciones y salidas originales.', '']
for row in rows:
    lines += [f"## {row['turnId']} — Cumple", '', '**Entrada:** ' + row['request'], '', '**Progreso:**', '']
    labels = list(dict.fromkeys(e['label'] for e in row['publicEvents'] if e.get('type') == 'boot_stage' and e.get('label')))
    lines += ['> ' + label for label in labels] if labels else ['Sin etiqueta de progreso.']
    lines += ['', '**Respuesta final:**', '', '> ' + row['final'], '']
(base / 'PRUEBAS_POLARIDAD52.md').write_text('\n'.join(lines), encoding='utf-8')
pins = json.loads((base / 'TRAMO51_PINS.json').read_text(encoding='utf-8'))
paths = [p.replace('astra-progress51', 'astra-polarity52') for p in pins['files']]
paths.append('tests/Baxy.Integration.Tests/C03FactPreservationTests.cs')
pins['files'] = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}
pins['state'] = 'clock/progress/polarity repaired; C03 ongoing'
pins['validation'] = {'pythonInheritedUnchangedFrom51': {'passed': 3123, 'subtests': 115, 'skips': 0, 'seconds': 46.52},
                      'dotnet': {'passed': 173, 'skips': 0, 'seconds': 8},
                      'sourceQuality': 'Fast passed', 'releaseBuildSeconds': 16.10,
                      'warnings': 0, 'errors': 0, 'Full': 'not run during repair'}
(base / 'TRAMO52_PINS.json').write_text(json.dumps(pins, indent=2), encoding='utf-8')

checkpoint = base / 'CHECKPOINT.md'
archive = base / 'CHECKPOINT_HISTORICO_HASTA52.md'
assert not archive.exists()
archive.write_bytes(checkpoint.read_bytes())
checkpoint.write_text('''# C03 — CHECKPOINT — tramo52 adoptado — EN_CURSO

Actualizado2026-09-07. Goal completo activo en01a07974-2a33-7ed3-ba87-2436944e8115;
continuación de01a074f6-9e0e-7fb3-8282-a6b706198a7e. RamaGoal-c03, HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49.
Preservar todo el WIP/ajeno/evidencia; sin commit/push. Main excluida. Sin procesos propios.
Autoridad completa: C03_ASTRA_AUTORIDAD.md y C03_RESPUESTA_VERAZ.md, identidad y AGENTS.
El checkpoint anterior íntegro queda en CHECKPOINT_HISTORICO_HASTA52.md.

## Último resultado

astra-polarity52: **7/7 turnos completos útiles**, contando progreso. Antes48:2/7,
49:4/7,51:6/7. Mismos siete inputs técnicos de sólo lectura; no reserva humana.
Hora/audio ES/EN/mezcla completos; CPU de triple conservada; avisos sin inventos;
hora/CPU ya publica «No hay fallos reportados», compatible con failures=[].
63,09s,GPU3497,56MiB,RAM4677,24MiB,registro intacto, sesión98797 exit0.
PRUEBAS_POLARIDAD52.md, ASTRA-TRAMO-52.md, paired.json y TRAMO52_PINS.json fijan evidencia.

173 tests .NET pass,0 skips,8s: C03FactPreservationTests, Goal06VisibleVoiceTests y
NaturalSystemStatusRequestParserTests. Antes del arreglo:9fail/40pass/0skips.
Logs %TEMP%/c03-polarity52-{red,owners}.log; sesiones14636/86876 cerradas.
Fast verde, Release16,10s,0avisos/errores, sesión84205 exit0; log c03-polarity52-fast.log.
Python sin cambios desde51:3123pass,115subtests,0skips,46,52s. No Full durante reparación.

## Fuente adoptada y rechazos

- 52: UserMessagePolicy.LooksLikeFailure separa la negación local de fallos de
  los fallos afirmados. Conserva polaridad tipada y fallos de cláusulas independientes.
- 51: llm.py narra progreso mediante instrucción específica de tarea, sin dictar
  palabras visibles, en primero/reintento. Reusa gramática de medidas para bloquear
  inventos aunque haya «en curso». Producto51 tuvo cinco avisos fieles y6/7 turnos.
  El aviso mezcla necesitó tres intentos por el filtro de primera frase: los dos
  primeros eran fieles y el tercero se publicó. No afirmar ausencia de reintentos.
- 50: rechazados kind=progress y mover petición a pendingRequest: ambos seguían
  inventando medidas en nativo. No reabrir sin datos nuevos. role51 sí mejoró5/5.
- 49: separador existente conserva cláusulas hora/audio, su orden y catálogo completo.
- 48: retirado atajo C# Contains(hora/audio) que fabricaba siempre dos pasos y omitíaCPU.
- 47: cola de estilo terminal permite excluir contexto de otro tema sólo al generar
  conocimiento; payload/replay exactos reprodujeron el error de Luna.10/10 útiles.
- 46: ajuste absoluto incompleto pide nivel;45: OutputStream propietario reparó caída
  PortAudio;44: negación por alcance conserva consulta y prohibición independientes.
Detalles y huellas en cada ASTRA-TRAMO-N.md/TRAMON_PINS.json; no reconstruir campañas.

## Siguiente bloqueo: lectura de archivo y errores útiles

wire-context47 t12 pidió leer una ruta literal en AppData/C03-fixtures/ausente47.txt.
La extracción inventó resourceId truncado a35 caracteres y repidió la ruta ya dada.
No llegó al proveedor. Payload real en wire-context47/wire-36612.jsonl; ASTRA48 precisa alcance.
Inspección52: __main__.apply_turn_action_grounding_gate:1207 manda a plan si hay
required_predecessors. planner._required_predecessors:974 omite filesystem.read.text,
aunque _dependency_operations:1144 ya añade filesystem.list a su recuperación.
ProductCatalog:404 y Core.FilesystemHandlers:63 usan LocalFilesystemProvider.ReadText;
Program.cs:97 configura dataRoot/filesystem-sandbox. ResolveHandle:345 exige un ID
de su diccionario privado: NO asumir que IDs de filesystem.known.search sirven aquí.
known.search sólo busca nombres en desktop/documents/downloads; no lectura arbitraria.
filesystem.path.ensure.absent puede BORRAR: jamás usarlo para resolver una lectura.
Siguiente: corregir dependencia/resolución dentro del alcance real y respuesta útil
de límite cuando la ruta queda fuera, sin pedir datos ya dados ni inventar capacidad.
También falta acreditar error con prosa y causa, no sólo composition_failed recuperable.
No se modificó aún código de archivos en52. Reusar captura real antes de tratar el LLM.

## Reserva humana y cierre completo

No reserva100 congelada/ejecutada. Pool privado742 en
%LOCALAPPDATA%/BAXY/C03-real-user-pool-20260906/unique_requests.jsonl.
Auditoría45 deja239 no descartados; no equivalen a100 admitidos. review-with-probes.jsonl
en reserve-audit-tranche45. No repetir auditorías45; adjudicar literal/contexto/procedencia.
El dueño confirmó «Son turnos validos» para tres textos ingleses: ADMISIBILIDAD_DUENO_2026-09-06.md.
No preguntar otra vez ni extender la confirmación al pool. Rúbrica de mezcla flexible
y cuatro ejemplos preservados en ACLARACION_DUENO_2026-09-06.md; no cuotas/traducciones.

Falta cierre real de ocho rutas; cien turnos humanos frescos separados de desarrollo,
100/100 útiles/fieles; averías con causa/recuperación; UI de escritorio y voz/audio físico;
recursos/runtime final; contratosC04–C09 hasta instalación; Full totalmente verde y
publicación del trabajo validado fuera de main. No reducir objetivo ni cerrar con skips.
UI45 fue real con voz, sin caída, pero no certifica fuente52. Conductor51/52 no es UI.

Runtime sin cambios: Qwen3-4B-Instruct-2507 Q4_K_M; llama.cppb9980 CUDA12.4,
KVq8,ngl99,3x4096. Registro %LOCALAPPDATA%/BAXYRuntime/mind-runtime-v1.json,
SHA13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed.
Python registrado: %LOCALAPPDATA%/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe.
No bloqueo externo, pregunta pendiente ni proceso propio activo. Goal permanece activo.
''', encoding='utf-8')

handoff = base / 'HANDOFF.md'
assert (base / 'HANDOFF_HISTORICO_HASTA51.md').read_bytes() == handoff.read_bytes()
handoff.write_text('''# Handoff — C03 completo — 2026-09-07 — 2bf3d4c

Goal EN_CURSO. Task01a07974-2a33-7ed3-ba87-2436944e8115, ramaGoal-c03.
Preservar WIP/evidencia/ajeno, sin commit/push, main excluida. Sin procesos propios.
Autoridad: C03_ASTRA_AUTORIDAD.md; CHECKPOINT.md contiene el estado operativo completo.
El handoff anterior íntegro está en HANDOFF_HISTORICO_HASTA51.md.

Adoptado52: siete controles técnicos completos7/7 útiles, frente a2/7 en48,
4/7 en49 y6/7 en51. Hora/audio/CPU y progreso fieles; «No hay fallos» ya publica.
63,09s,GPU3497,56MiB,RAM4677,24MiB,registro intacto. Sesión98797 exit0.
173 tests .NET pass/0skips/8s. Fast verde, Release16,10s,0avisos/errores,
84205exit0. Python51 sin cambios:3123pass/115subtests/0skips/46,52s. No Full.
PRUEBAS_POLARIDAD52.md, ASTRA-TRAMO-52.md y TRAMO52_PINS.json fijan pruebas/huellas.

Decisiones:49 reutiliza separación de cláusulas para hora/audio;51 instruye narrar
progreso sin palabras fijas y veta medidas inventadas;52 interpreta negaciones de
fallos en UserMessagePolicy conservando fracasos independientes. No cambiar modelo.
Rechazados50:kind=progress y petición en pendingRequest. Ambos fallan en nativo.
El aviso mezcla aún puede necesitar tres intentos por el filtro de primera frase;
se publica útil, no afirmar que siempre pasa a la primera.

Siguiente: archivo47 repide ruta literal porque intenta usarla como resourceId35.
__main__.apply_turn_action_grounding_gate usa required_predecessors; planner:974
omite filesystem.read.text aunque _dependency_operations:1144 añade filesystem.list.
ReadText sólo admite IDs del LocalFilesystemProvider del filesystem-sandbox.
NO asumir que known.search proporciona IDs utilizables por read.text ni lookup
arbitrario de AppData. path.ensure.absent BORRA, no usarlo como resolución.
Resolver dentro del alcance real y dar límite útil fuera; luego error con prosa/causa.
Payload real: astra-wire-context47/wire-36612.jsonl; diagnóstico en CHECKPOINT.

Falta: ocho rutas completas, reserva100 humana fresca congelada antes de ejecutar,
averías/recuperación, UI/voz/audio físico y recursos finales, contratosC04–C09,
Full íntegro y publicación fuera de main. Conductor7 no es reserva ni UI.
Pool742 privado;239 candidatos no descartados, selección100 pendiente. Reusar
auditorías45. Confirmación de tres textos ingleses ya registrada: no preguntar de nuevo.
CHECKPOINT da rutas privadas, rúbrica del dueño y runtime. No bloqueo externo.
''', encoding='utf-8')
active = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
active.update(checkpoint='tramo52 adoptado; archivos y cierre integral pendientes',
              continuation='Completa y EN_CURSO; siete controles técnicos7/7 no sustituyen los cien humanos ni el resto del cierre.')
(base / 'RELEVO_ACTIVO.json').write_text(json.dumps(active, ensure_ascii=False, indent=2), encoding='utf-8')
print('Recorded tranche52 pairs/pins and condensed checkpoint/handoff with exact historical backups.')
