from pathlib import Path
import datetime
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-files92-context'
paired = json.loads((out / 'paired.json').read_text(encoding='utf-8'))
lines = ['# C03 — recuperación de contexto92 — 4/4 útiles', '',
    'La búsqueda vacía se explica y el porqué en inglés conserva la misma causa. '
    'Lectura real y reloj recuperan en el mismo proceso.94668exit0;64,08s; '
    'GPU3177,5625MiB;RAM5970,09765625MiB;registro intacto. '
    '1152pytest pass/0skips/5,49s;182integración pass/0skips/15s; '
    'Fast16945exit0,Release15,01s,0 avisos/errores. ASTRA-TRAMO-92.md detalla '
    'herencia, cambios y fallos de implementación detectados/corregidos por pruebas.', '',
    'Fuente86+92; Qwen3.5 override sin promoción. El primer chat aún añade una falsa '
    'limitación del catálogo; se rechaza correctamente. La recuperación ahora recibe '
    'previousResponse, produce causa fiel y no ejecuta una nueva lectura. No se añade '
    'exención para códigos extra: sólo vocabulario literal del usuario previo. '
    'No aceptación UI/voz/audio/reserva humana ni Full.', '']
for turn in paired:
    labels = [e['label'] for e in turn['publicEvents'] if e.get('type') == 'boot_stage' and e.get('label')]
    lines += [f'## {turn["turnId"]} — útil', '', 'Entrada: ' + turn['request'], '',
        'Final literal: ' + turn['final'], '', 'Progreso publicado: ' + json.dumps(labels, ensure_ascii=False), '']
    seen = set()
    for row in turn['compose']:
        if row.get('draft') in seen:
            continue
        seen.add(row.get('draft'))
        lines += [f'Borrador ({row.get("reason") or "sin veto Python"}): {row.get("draft")}', '',
            '```json', json.dumps(row.get('payload'), ensure_ascii=False, indent=2), '```', '']
report = base / 'PRUEBAS_CONTEXTO92.md'
report.write_text('\n'.join(lines), encoding='utf-8')
files = [report, out / 'PREREG.json', out / 'RESULT.json', out / 'paired.json',
    out / 'compose-audit.jsonl', out / 'turn-audit.jsonl', base / 'ASTRA-TRAMO-92.md']
(base / 'TRAMO92_PINS.json').write_text(json.dumps({'scope': 'Source92 four-case integrated recovery, not final acceptance',
    'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}, indent=2), encoding='utf-8')

archive = base / 'CHECKPOINT_HISTORICO_HASTA91.md'
assert not archive.exists()
archive.write_text((base / 'CHECKPOINT.md').read_text(encoding='utf-8'), encoding='utf-8')
checkpoint = '''# C03 — CHECKPOINT — fuente92; recuperación4/4; progreso pendiente — EN_CURSO

Tarea01a07974-2a33-7ed3-ba87-2436944e8115, continuación de01a074f6-9e0e-7fb3-8282-a6b706198a7e.
Goal activo, ramaGoal-c03, HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49.
WIP/ajeno/evidencia preservados; sin commit/push; main excluida. Sin bloqueo externo.
Autoridad C03_ASTRA_AUTORIDAD.md/C03_RESPUESTA_VERAZ.md, identidad y AGENTS.
Historia íntegra CHECKPOINT_HISTORICO_HASTA67.md y CHECKPOINT_HISTORICO_HASTA91.md.

## Estado actual y siguiente acción

Fuente58+63+74+77+78+81+84+86+92 adoptada localmente; no progreso nuevo en fuente.
92 conserva context previo como dato previousResponse sólo en recuperación conversacional,
sin roles assistant anteriores. Nombres humanos de priorRequests quedan exentos del veto
de códigos por token exacto en Python/C#; el pedido actual sigue gobernando intención.
Se retira el contenedor previous_turn vacío de primera generación y ambos reintentos.
Acotadas nuevas2pass. Suite inicial8fail por referencias a la variable retirada: ambas
corregidas; --lf8pass. Cuatro suites completas1152pass/0skips/5,49s;182integración
pass/0skips/15s. Fast16945exit0,Release15,01s,0 avisos/errores. No Full.
Logs TEMP/c03-context92-{python-fixed,dotnet,fast}.log.

files92-context terminó94668exit0:4/4 útiles,64,08s,GPU3177,56MiB,RAM5970,10MiB.
Registro intacto; Qwen3.5 override sin promoción. Búsqueda vacía explicada y porqué en
inglés conserva causa; lectura real y reloj recuperan. El chat inicial todavía añade
una falsa limitación de catálogo y se rechaza; la recuperación útil la sustituye.
PRUEBAS_CONTEXTO92.md/TRAMO92_PINS.json fijan entradas/finales/fuente/hechos.

Único proceso propio activo: prototipo nativo93, handle59047, TEMP/c03-thinking93.log.
script scratchpad/c03-progress-thinking93.py; out astra-progress-thinking93.
Mismos seis paquetes87 y sampler greedy. Cambia sólo perfil a thinking: servidor
reasoning on,budget-1,deepseek; request enable_thinking true,max_tokens2048. No fuente,
prompts ni modelo cambiados; comprobar reasoning_content, finish_reason y costes.
Recoger RESULT/posts y adjudicar actividad verdadera antes de decidir. No builds/modelos
paralelos. Si no ayuda, no repetir cambios de prompt/formato ya refutados abajo.

## Decisiones y pruebas que no se repiten

81 panel técnico10/10 útil: archivo/UTF8/causa/checksum/capacidades/hora+audio+CPU/nivel.
Fuente74 corrige veto de operation y fallo negado;77 agrupa sólo prefijo system
(Qwen3.5 daba HTTP400);78 limita vetos por rol;81 adapta gramática existente de
enumeración nominal, manteniendo orden y catálogo.2774pytest pass/0skips;Fast81 verde.
PRUEBAS_ENUMERACION81.md y reportes74/75_76/77/78_80 conservan evidencia.

83 búsqueda vacía2/4: se convertía entries[]/count0 verificados en step_data_missing.
84 conserva file_search_no_matches antes de grounding imposible;162integración pass,
Fast verde tras corregir formato. Producto84 sigue2/4 por veto de negación y cifrado
inventado.86 reconoce no se encontró/no encontré/no se pudo en el guard existente,
preservando ausencia de fallos;1151pytest pass y181integración pass,Fast verde.
Producto86 3/4; la causa inventada nace cuando fallback descarta el contexto.
89/91 nativos: contexto como dato recupera causa/latencia y conserva cálculo/checksum.
Control límites sigue metatexto sin catálogo: no es5/5 ni aceptación de capacidades.
PRUEBAS_RECUPERACION86_89_91.md fija esa distinción y la herencia panel-opus-4/5.

82 progreso nativo4/6 con acting/in progress: porqué afirma lectura nueva; hora/CPU
produce metatexto. App ComposeMilestoneAsync siempre da acting; se pierde understanding.
85 sólo phase=understanding insuficiente.87 state=understanding the person's request
mejora parcial pero sigue leyendo.88 sustituye instrucción: aún lecturas y actor invertido.
90 rol dedicado o solicitud JSON no resuelve. NO adoptar ni apilar vetos/prompts;
se cambia estrategia a perfil/capacidad en93. PRUEBAS_PROGRESO82/85/87/88_90.md.
Todos estos son borradores nativos, no publicación real, UI ni audio.

No reabrir sin dato nuevo: borrar historial rompe referencias68; clasificador69/70
5/10 descartado; frases/roles/descripción65–67 insuficientes. Hechos en historial73
8/10 pero file2/file3 siguen mal; no implementados. is_elliptical_followup no cubre
hazlo/close that. Registrar anomalías, no borrar evidencia ni repetir hasta obtener pase.

## Runtime, reserva y cierre pendiente

Registro: Qwen3-4B-Instruct-2507 Q4_K_M,b9980CUDA12.4,KVq8,ngl99,3x4096.
Manifest SHA13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed.
Core AOT63 SHAfe2c1cfc351abf78bd4d5080fd651eaec2e5915f83b82a30613a57df40e48fed.
App Release92. Qwen3.5-4B-Q4_K_M local sólo override, mismo backend/perfil salvo93.
Modelo D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf.
Python de pruebas C:/Users/usuario/AppData/Local/Programs/Python/Python312/python.exe;
py apunta a313 sin pytest. Python runtime en %LOCALAPPDATA%/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe.

Tres textos ingleses admitidos por «Son turnos validos» ya registrado en
ADMISIBILIDAD_DUENO_2026-09-06.md; no preguntar de nuevo ni extender a742.
Reserva privada742,239candidatos no refutados;100 aún no seleccionados/congelados.
RESERVE_PROVENANCE_AUDIT45.json reutilizable. Spanglish español natural válido;
sin cuotas/traducciones. Cuatro ejemplos ACLARACION_DUENO_2026-09-06.md vigentes.

Falta cierre completo: ocho rutas útiles, cien turnos humanos frescos/literales
congelados antes de ejecutar y100/100 adjudicados, averías+recuperación aparte,
UI escritorio real con py main.py, voz/audio físico y techo conjunto4GB; conductor
no acredita UI/audio. Regresión y hashes antes de promover runtime; continuidad
C04–C09 hasta instalación; Full íntegro verde sólo al candidato final y publicación
validada fuera de main. No cerrar por panel técnico, silencio, skip ni traza solamente.
'''
(base / 'CHECKPOINT.md').write_text(checkpoint, encoding='utf-8')
(base / 'HANDOFF.md').write_text('''# Handoff C03 — fuente92 — 2026-09-07

CHECKPOINT.md manda. Goal activo, tarea01a07974-2a33-7ed3-ba87-2436944e8115,
ramaGoal-c03,HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. WIP/evidencia preservados,
main excluida, sin commit/push. No bloqueo externo ni Full durante reparación.

Fuente92 conserva respuesta previa como dato de recuperación y vocabulario humano
previo en guardas. Producto files92-context4/4 útil,94668exit0,64,08s,GPU3177,56MiB,
RAM5970,10MiB,registro intacto.1152pytest pass/0skips/5,49s;182integración pass/0skips/15s;
Fast16945exit0,Release15,01s,0 avisos/errores. PRUEBAS_CONTEXTO92.md/TRAMO92_PINS.json.

Único proceso activo93, handle59047, TEMP/c03-thinking93.log. Prototipo local
scratchpad/c03-progress-thinking93.py; out astra-progress-thinking93. Recoger
RESULT/posts, verificar reasoning real/final/costes. Sin builds/modelos paralelos.
No fuente de progreso adoptada.85/87 datos y88/90 instrucciones/formato insuficientes;
no seguir esa colección de variantes.93 cambia perfil thinking del mismo Qwen3.5,
sin sampler nuevo ni modificación del registro. Modelo actual sigue sólo override.

Anterior81 panel técnico10/10;84/86/92 recuperan causa vacía, negación y contexto.
Historia íntegra archivada en CHECKPOINT_HISTORICO_HASTA91.md y reportes por tramo.
No reabrir borrado de historial68 ni clasificador69/70; hechos73 insuficientes.

Tres turnos confirmados ya admitidos, sin extender a742 ni preguntar de nuevo.
Cierre integral pendiente:8rutas,100frescos congelados/100útiles,averías/recuperación,
UI/voz/audio+4GB,regresión/runtime,continuidadC04–C09,Full y publicación fuera de main.
''', encoding='utf-8')
path = base / 'RELEVO_ACTIVO.json'
relay = json.loads(path.read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    checkpoint='Fuente92: recuperación4/4,1152pytest/182integración pass,Fast verde; C03 EN_CURSO',
    continuation='Único proceso93 activo59047,TEMP/c03-thinking93.log. Recoger razonamiento/final/recursos. No builds/modelos paralelos ni Full. Qwen3.5 sólo override, cierre integral pendiente.')
path.write_text(json.dumps(relay, ensure_ascii=False, indent=2), encoding='utf-8')
