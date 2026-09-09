from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-files86-negation'
paired = json.loads((out / 'paired.json').read_text(encoding='utf-8'))
lines = ['# C03 — recuperación de negación86 y contexto89/91', '',
    '86 producto:3/4 útiles. T1 publica la ausencia verificada; t2 sigue inventando cifrado. '
    'T3 y t4 recuperan lectura y reloj.73121exit0;64,11s;GPU3177,5625MiB;RAM5867,484375MiB; '
    'registro intacto.1151pytest pass/0skips/6,42s;181integración pass/0skips/15s. '
    'Fast1604exit0,Release15,73s,0 avisos/errores.', '',
    'wire-19416.jsonl localiza la primera desviación: el chat ve todo el intercambio y '
    'explica ausencia, pero añade que leer ese archivo no está en el catálogo. El guard '
    'rechaza esa respuesta. El compositor de recuperación recibe sólo kind=conversation, '
    'sin la respuesta anterior; inventa cifrado. La omisión es explícita en llm.py por '
    'panel-opus-4/5 con Granite: añadir el turno anterior como assistant causaba repetición '
    'del tema previo ante cálculo o límites. test_a_follow_up_does_not_replay_the_previous_turn '
    'conserva esa evidencia. No restaurar roles anteriores a ciegas.', '',
    '89 compara intercambio previo como dato de situation, manteniendo sólo roles system/user. '
    'Recupera causa y latencia; cálculo y checksum no heredan tema.91 conserva sólo previousResponse, '
    'el dato que App ya provee, porque priorRequests no garantiza asociación exacta si hubo turnos '
    'sin respuesta. Mismos resultados útiles en esos cuatro controles. El control de límites '
    'no repite subnet mask, pero sigue siendo metatexto: carece del catálogo real, no acredita '
    'capacidades ni una aceptación5/5. No borrar ese límite.', '',
    'Contraste reutilizado: [ingeniería de contexto de Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) '
    'distingue instrucciones y contexto relevante. Es orientación de representación, no prueba '
    'para estos modelos. La decisión candidata se basa en packets86/89/91 y contrastes locales. '
    'Fuente de recuperación todavía sin cambiar; Qwen3.5 override sin promoción. No UI/audio/reserva.', '']
for turn in paired:
    lines += [f'## 86/{turn["turnId"]} — {"no útil" if turn["turnId"] == "t2" else "útil"}', '',
        'Entrada: ' + turn['request'], '', 'Final: ' + turn['final'], '']
report = base / 'PRUEBAS_RECUPERACION86_89_91.md'
native = [(89, 'astra-context89'), (91, 'astra-context91')]
for number, name in native:
    folder = base / name
    lines += [f'## Recursos{number}', '', (folder / 'RESULT.json').read_text(encoding='utf-8'), '']
    for row in [json.loads(s) for s in (folder / 'posts.jsonl').read_text(encoding='utf-8').splitlines()]:
        lines += [f'### {number}/{row["case"]}/{row["variant"]}', '',
            row['response']['choices'][0]['message']['content'], '']
report.write_text('\n'.join(lines), encoding='utf-8')
for number, name in [(86, 'astra-files86-negation'), *native]:
    folder = base / name
    files = [report, folder / 'PREREG.json', folder / 'RESULT.json',
        folder / ('paired.json' if number == 86 else 'posts.jsonl')]
    (base / f'TRAMO{number}_PINS.json').write_text(json.dumps({'scope': 'Development context and negation evidence; not acceptance',
        'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}, indent=2), encoding='utf-8')

lines = ['# C03 — progreso88/90: no adoptar', '',
    '88 sustituye la instrucción existente por narrar actividad actual. Mejora t5/t6, '
    'pero t1/t2/t3 siguen leyendo, y t4 atribuye a la persona informar hora/CPU. '
    '90 contrasta dos diferencias independientes contra88: rol dedicado sin prompt '
    'general, o solicitud como requested_goal JSON sin cambiar instrucciones. Ninguna '
    'resuelve el panel. Rol dedicado empeora t2 a analizar contenido/errores; JSON '
    'mejora t1, pero t2/t3 siguen leyendo y t4 invierte actor. Se detiene esta estrategia '
    'de instrucciones/formato: NO adoptar ni sumar más vetos por frases. Siguiente '
    'investigación: capacidad y perfil de inferencia del rol, contra mismos casos.', '',
    'Todos nativos, sin efectos ni publicación/UI/audio. Qwen3.5 override; registro intacto.', '']
report = base / 'PRUEBAS_PROGRESO88_90.md'
for number, name in [(88, 'astra-progress-instruction88'), (90, 'astra-progress-role90')]:
    folder = base / name
    lines += [f'## Recursos{number}', '', (folder / 'RESULT.json').read_text(encoding='utf-8'), '']
    for row in [json.loads(s) for s in (folder / 'posts.jsonl').read_text(encoding='utf-8').splitlines()]:
        lines += [f'### {number}/{row["turn"]}/{row["variant"]}', '', 'Entrada: ' + row['text'], '',
            row['response']['choices'][0]['message']['content'], '']
report.write_text('\n'.join(lines), encoding='utf-8')
for number, name in [(88, 'astra-progress-instruction88'), (90, 'astra-progress-role90')]:
    folder = base / name
    files = [report, folder / 'PREREG.json', folder / 'RESULT.json', folder / 'posts.jsonl']
    (base / f'TRAMO{number}_PINS.json').write_text(json.dumps({'scope': 'Unsuccessful progress prototypes; not adopted',
        'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}, indent=2), encoding='utf-8')

for name in ('CHECKPOINT.md', 'HANDOFF.md'):
    path = base / name
    path.write_text(path.read_text(encoding='utf-8') + '\n\n## Actualización86–91\n\n'
        '86 terminó73121exit0:3/4 útiles; búsqueda/lectura/reloj bien, porqué inventa cifrado.\n'
        'El primer chat tenía historial pero filtró catálogo; fallback descarta contexto.\n'
        '89/91 nativos recuperan causa/latencia y conservan cálculo/checksum con contexto\n'
        'como dato, sin roles previos. Límites aún metatexto, no aceptación5/5.\n'
        'PRUEBAS_RECUPERACION86_89_91.md y pins. Siguiente92: previousResponse ya enviado\n'
        'por App debe llegar al compositor; identidad de archivo previa pertenece a\n'
        'vocabulario del usuario, no a códigos internos. Contrastes antes de producto.\n'
        '88/90 progreso insuficientes; NO adoptar. Parar variantes de prompt/formato y\n'
        'contrastar capacidad/perfil de inferencia. PRUEBAS_PROGRESO88_90.md.\n'
        'Sin procesos/modelos activos, fuente86, no Full, modelo sólo override.\n', encoding='utf-8')
path = base / 'RELEVO_ACTIVO.json'
relay = json.loads(path.read_text(encoding='utf-8'))
relay.update(checkpoint='Fuente86: producto3/4; contexto89/91 útil en controles; progreso88/90 sin adoptar; C03 EN_CURSO',
    continuation='Sin procesos activos.92: conservar previousResponse como dato, vocabulario humano previo en guard. Progreso: cambiar estrategia a perfil de inferencia. No Full ni promoción.')
path.write_text(json.dumps(relay, ensure_ascii=False, indent=2), encoding='utf-8')
