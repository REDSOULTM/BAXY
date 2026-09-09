from pathlib import Path
import datetime
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-files78-roles'
paired = json.loads((out / 'paired.json').read_text(encoding='utf-8'))
lines = ['# C03 — alcance de los vetos78 y enumeración79–80', '',
    '78:9/10 útiles,112,17s,GPU3177,56MiB,RAM6293,96MiB,exit0,registro intacto. '
    'Se recuperan la explicación de la causa UTF8 y la pregunta por el nivel del volumen. '
    'Qwen3.5 sigue override; no UI/voz/audio físico/reserva humana ni promoción.', '',
    'Fuente78: la aclaración clasificada usa el guard de invitación con su rol conocido, pero '
    'sigue rechazando familias ausentes del pedido. No se añade el verbo pon a una lista de frases. '
    'Conversación de conocimiento puede explicar un fallo anterior; las respuestas de operaciones '
    'siguen sujetas a su polaridad verificada. Sin cambios de prompts, selector ni historial.', '',
    'Rojo C#:2 fail/60 pass/0 skips/4s; Python1 fail/21 deselected/0,50s. '
    'Después:1150 pytest pass/0 skips/5,78s;169 integración pass/0 skips/30s. '
    'Fast49738exit0,Release16,01s,0 avisos/errores. No Full durante reparación.', '']
for turn in paired:
    labels = [e['label'] for e in turn['publicEvents'] if e.get('type') == 'boot_stage' and e.get('label')]
    lines += [f'## {turn["turnId"]} — {"no útil" if turn["turnId"] == "t9" else "útil"}', '',
              f'Entrada: {turn["request"]}', '', f'Final literal: {turn["final"]}', '',
              f'Labels de progreso: {json.dumps(labels, ensure_ascii=False)}', '']
lines += ['## Diagnóstico de enumeración79–80', '',
    '79 no reproduce el producto: usó el shortlist de herramientas de un turno de archivos, '
    'que no contenía las tres operaciones de observación. Su resultado null no sirve como '
    'baseline; se conserva el error metodológico y no se sobrescribe la evidencia.', '',
    '80 aísla system.time/audio.status/system.status, todas existentes en el catálogo. '
    'Dime la hora, el audio y el uso de CPU queda en una sola cláusula y sale por el return '
    'de strict_request de effect_intent.py:12722 con sólo audio.status. El control52 que '
    'repite los verbos y el control de dos observaciones resuelven completos y en orden. '
    'unresolved_compound_contract no detecta la pérdida del nominal. No se llamó al modelo.', '',
    '81 adapta la gramática existente _PURE_COORDINATED_STATUS_CLAUSE, no añade una capa. '
    'Incluye dominio sin palabra estado, uso de CPU/CPU usage y separadores de coma; sólo '
    'divide cuando TODA la cláusula es una enumeración de estados. Conserva el verbo rector. '
    'Rojo3 fail/6 pass/1615 deselected/1,17s; acotada corregida10 pass/1614 deselected/0,69s. '
    'Validación amplia y producto81 pendientes al escribir este informe.', '']
report = base / 'PRUEBAS_ROLES78_Y_ENUMERACION79_80.md'
report.write_text('\n'.join(lines), encoding='utf-8')
files = [report, out / 'PREREG.json', out / 'RESULT.json', out / 'paired.json']
for name in ('c03-roles78-pytest.log', 'c03-roles78-dotnet.log', 'c03-roles78-fast.log', 'c03-roles78-red.log'):
    path = out / name
    path.write_bytes((Path(os.environ['TEMP']) / name).read_bytes())
    files.append(path)
for stage in ('79', '80'):
    files += [base / ('astra-observation-scope' + stage) / name for name in ('PREREG.json', 'RESULT.json')]
(base / 'TRAMO78_80_PINS.json').write_text(json.dumps({'scope': 'Role repair78 and read-only scope diagnostic79/80;81 pending',
    'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}, indent=2), encoding='utf-8')

checkpoint = '''# C03 — CHECKPOINT — roles78 y enumeración81 — EN_CURSO

Tarea01a07974-2a33-7ed3-ba87-2436944e8115, continuación de01a074f6-9e0e-7fb3-8282-a6b706198a7e.
Goal activo, ramaGoal-c03, HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49.
WIP/ajeno/evidencia preservados; sin commit/push; main excluida. Sin bloqueo externo.
Autoridad C03_ASTRA_AUTORIDAD.md/C03_RESPUESTA_VERAZ.md, identidad y AGENTS.
Historia íntegra CHECKPOINT_HISTORICO_HASTA67.md y todos los informes fechados.

## Estado de fuente y producto

Fuente58 + guard proveedor63 + Python74 + serialización77 + alcance78 + candidato81.
74 quita veto por operation y hereda failed/fallo negado de C#52:producto6/10.
75 localiza HTTP400 por prefijo con varios system en Qwen3.5.76 nativo elimina9/9
errores agrupando instrucciones; principales controles2507 preservados.77 agrupa
el prefijo en _post, conserva texto/orden/diálogo/payload original:producto7/10.
78 usa el rol de aclaración al valorar una invitación (conserva familias), y deja
que conversación de conocimiento explique fallos sin afirmar un outcome nuevo.
Producto files78-roles9/10 útiles: causa UTF8 y pregunta por nivel recuperadas.
11070exit0,112,17s,GPU3177,56MiB,RAM6293,96MiB,registro intacto. Qwen3.5 sólo
override; NO promovido. T9 todavía deriva a audio.status y omite hora/CPU.
1150pytest pass/0 skips/5,78s;169 integración pass/0 skips/30s.
Fast78 verde49738exit0,Release16,01s,0 avisos/errores. No Full.

81 pendiente: adapta la gramática existente de enumeración de estados a dominio
sin sufijo, uso de CPU y separadores de coma, sólo si coincide la cláusula entera.
79 fue diagnóstico inválido con shortlist de archivos; no usar como baseline.
80 con tres hojas de catálogo reproduce el early return12722 de strict_request
audio.status; controles52 con verbos repetidos y dos nominales sí resuelven.
Rojo81 3fail/6pass; acotada10pass. Cinco suites pytest en ejecución20042,
log TEMP/c03-nominal81-pytest.log. files81-nominal PREPARADO, no ejecutado;
esperar suites, Fast y después driver scratchpad/c03-files81-nominal.py.
No otros modelos/conductores activos. No fuente81 adoptada sin producto/regresión.

## Evidencia y decisiones

PRUEBAS_VETO74.md/TRAMO74_PINS.json;
PRUEBAS_TEMPLATE75_76.md/TRAMO75_76_PINS.json;
PRUEBAS_TEMPLATE77.md/TRAMO77_PINS.json;
PRUEBAS_ROLES78_Y_ENUMERACION79_80.md/TRAMO78_80_PINS.json.
Los reportes tienen entradas/finales/borradores y los PREREG fijan fuente exacta.
Hook77 captura post_chat_completion después de serializar;75 sólo _post previo.
Ningún panel acredita UI/voz/audio físico o reserva humana. No confundir labels
de progreso publicados con borradores en compose-audit.

No reabrir sin dato nuevo: borrar historial rompe referencias68; clasificador69/70
5/10 descartado; frases/roles/descripción65–67 insuficientes. Hechos en historial73
8/10 pero file2/file3 siguen mal; no implementados. is_elliptical_followup no sirve
para hazlo/close that. El modelo71 nativo9/10 proponía leer ante porqué; el producto
78 resuelve esa pregunta como explicit_conversation sin efectos.

## Runtime, reserva y cierre pendiente

Registro: Qwen3-4B-Instruct-2507 Q4_K_M,b9980CUDA12.4,KVq8,ngl99,3x4096.
Manifest SHA13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed.
Core AOT63 SHAfe2c1cfc351abf78bd4d5080fd651eaec2e5915f83b82a30613a57df40e48fed.
No source de provider/kernel cambiada desde63; App Release actual78.
«Son turnos validos» sólo admite tres textos: ADMISIBILIDAD_DUENO_2026-09-06.md.
No repetir pregunta ni extender a742. Pool privado742/239 no descartados;
selección100 pendiente, auditorías45 reutilizables. Sin traducciones/cuotas.
Faltan8rutas,100humanos frescos congelados y100/100 útiles,averías/recuperación,
UI/voz/audio físico+4GB conjuntos,continuidadC04–C09,Full verde y publicación
fuera de main. No Full durante reparación ni cierre parcial de C03.
Nombre sin coincidencias y progreso que infiere UTF8 del nombre siguen pendientes.
No basename exterior->interior; path.ensure.absent puede borrar, no es búsqueda.
'''
(base / 'CHECKPOINT.md').write_text(checkpoint, encoding='utf-8')
(base / 'HANDOFF.md').write_text('''# Handoff — C03 — 78/81 — 2026-09-07

Goal activo, tarea01a07974-2a33-7ed3-ba87-2436944e8115, ramaGoal-c03,
HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. CHECKPOINT manda. Sin commit/push,
main excluida, preservar WIP/ajeno/evidencia. Sin bloqueo externo.

Fuente58+63+74+77+78; candidato81 en validación. Producto78 9/10 útil,
112,17s,GPU3177,56MiB,RAM6293,96MiB,11070exit0. Qwen3.5 override, registro2507
intacto.74 arregla falso veto operation/failed;77 agrupa prefijo system (Qwen3.5
daba HTTP400);78 conserva causa de fallo en conversación y nivel en aclaración.
1150pytest pass/0skips;169integración pass/0skips;Fast78 verde,Release16,01s.
PRUEBAS_VETO74.md, PRUEBAS_TEMPLATE75_76.md, PRUEBAS_TEMPLATE77.md y
PRUEBAS_ROLES78_Y_ENUMERACION79_80.md, con pins, fijan la evidencia.

T9 sólo audio:79 usó shortlist inaplicable, NO baseline.80 con tres hojas reales
localiza return estricto12722.81 extiende gramática existente de nominales y
separa comas sólo tras match completo. Acotada10pass. Cinco suites pytest
ejecución20042, TEMP/c03-nominal81-pytest.log. files81-nominal preparado,
no ejecutado: terminar pruebas/Fast, correr driver y adjudicar entero. No otros
modelos ni conductores activos. No Full durante reparación.

No reabrir clasificador69/70 ni borrado de historial68. Hechos73 parcial8/10,
no fuente. Registro sin promoción; falta regresión de8rutas/UI/voz/audio+4GB.
Tres textos ingleses admitidos; no repetir pregunta ni extender a742. Reserva100
fresca congelada/100útiles,averías/recuperación,continuidadC04–C09,Full verde y
publicación fuera de main pendientes. No aceptar panel técnico como reserva.
''', encoding='utf-8')
relay = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    checkpoint='Producto78 9/10; candidato81 en pruebas; C03 completo EN_CURSO',
    continuation='Recoger pytest20042, Fast y producto files81-nominal preparado. Fuente74/77/78 repara vetos/template; modelo sólo override. Cierre integral pendiente.')
(base / 'RELEVO_ACTIVO.json').write_text(json.dumps(relay, ensure_ascii=False, indent=2), encoding='utf-8')
