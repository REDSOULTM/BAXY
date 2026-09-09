from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
panel = base / 'astra-files72-qwen35'
refs = base / 'astra-selector-facts73'
paired = json.loads((panel / 'paired.json').read_text(encoding='utf-8'))
verdicts = [
    'Útil: identifica la limitación real de búsqueda absoluta.',
    'Útil: lee el contenido literal del fixture real.',
    'No útil: agotamiento por vetos falsos internal_code/missing_failure sobre tres borradores fieles.',
    'Útil: explica límite de ruta absoluta, sin sustituir por homónimo interior.',
    'Útil: hora verificada.',
    'No útil: atribuye la lectura anterior a un fallo de interpretación, perdiendo la causa UTF8.',
    'No útil: una pregunta de conocimiento termina en error de interpretación.',
    'Útil: enumera capacidades disponibles.',
    'No útil: agotamiento. El payload sólo contiene audio; los borradores añaden hora10:42 y CPU2 sin esos hechos. El veto extra_claim es correcto.',
    'No útil: debería aclarar el nivel de volumen; termina en agotamiento tras error de interpretación.',
]
lines = ['# C03 — producto Qwen3.5 y hechos en historial — tramos72–73', '',
    '72:5/10 turnos útiles con el modelo heredado en override. No se promueve. Registro intacto; '
    '137,17s, GPU3177,56MiB, RAM6653,66MiB, exit0. Fuente63, mismos primeros cinco controles de archivos, '
    'cinco transferencias adicionales. No UI, voz/audio físico ni reserva humana. El conductor no publicó '
    'ningún boot_stage.label no nulo; los borradores de progreso de la auditoría no prueban progreso visible.', '',
    'La mejora del selector nativo71 no se mantiene en todos los roles del producto. Las causas anteriores '
    'de t6/t7/t10 aún requieren localizar la primera transformación equivocada. No confundir con un fallo '
    'del proveedor ni corregir extra_claim de t9 para aceptar hechos ausentes.', '']
for turn, verdict in zip(paired, verdicts, strict=True):
    lines += [f'## 72 / {turn["turnId"]}', '', f'Entrada: {turn["request"]}', '',
              f'Final literal: {turn["final"]}', '', verdict, '']
    seen = set()
    for row in turn['compose']:
        if row.get('reason') and row.get('draft') not in seen:
            seen.add(row.get('draft'))
            lines += [f'Borrador rechazado ({row["reason"]}): {row.get("draft", "")}', '']
lines += ['## 73 / representación del resultado previo', '',
    'Registrado Qwen3-2507; mismos cuatro paquetes completos64 y seis referencias68. Sólo se sustituye '
    'contenido del asistente correspondiente al resultado de máquina por JSON de su fuente tipada. '
    'Las ofertas y conversación se conservan. Los resultados de búsqueda para referencias son fixtures '
    'sintéticos declarados, no hechos de archivos reales. No se ejecutan funciones ni se modifica fuente.', '',
    'Capturado6/10; resultado tipado8/10. Recupera file4 y reft4 (segundo archivo), pero file2 y file3 '
    'siguen seleccionando búsqueda en vez de lectura. No implementado: no resuelve la recuperación '
    'tras el primer fallo.14,23s, GPU3497,56MiB, RAM3357,53MiB; registro intacto.', '']
posts = [json.loads(s) for s in (refs / 'posts.jsonl').read_text(encoding='utf-8').splitlines()]
for row in posts:
    choice = row['response']['choices'][0]
    message = choice['message']
    selected = [c['function']['name'] for c in message.get('tool_calls', [])]
    lines += [f'### {row["id"]} / {row["variant"]}', '', f'Entrada: {row["text"]}', '',
              f'Selección: {json.dumps(selected)}; fin={choice["finish_reason"]}.', '',
              f'Texto bruto: {message.get("content", "")}', '']
report = base / 'PRUEBAS_PRODUCTO_Y_HECHOS72_73.md'
report.write_text('\n'.join(lines), encoding='utf-8')
files = [report, panel / 'PREREG.json', panel / 'RESULT.json', panel / 'paired.json',
         panel / 'wire-29372.jsonl', panel / 'compose-audit.jsonl',
         refs / 'PREREG.json', refs / 'RESULT.json', refs / 'posts.jsonl']
(base / 'TRAMO72_73_PINS.json').write_text(json.dumps({
    'scope': 'Unpromoted model72 and native history representation73; no acceptance claim',
    'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
}, indent=2), encoding='utf-8')
