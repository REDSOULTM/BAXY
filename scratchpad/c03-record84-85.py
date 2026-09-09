from pathlib import Path
import datetime
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-files84-emptycause'
paired = json.loads((out / 'paired.json').read_text(encoding='utf-8'))
lines = ['# C03 — causa de búsqueda vacía84', '',
    '2/4 útiles. La causa llega como file_search_no_matches, con búsqueda verificada vacía. '
    'El compositor produce primero una explicación fiel, pero Python veta las tres formas '
    'negativas como missing_failure. T1 termina composition_failed; t2 inventa cifrado. '
    'T3 y t4 recuperan lectura real y reloj. No aceptar este panel ni la causa inventada.', '',
    '27467exit0;76,11s;GPU3177,5625MiB;RAM6325,94140625MiB;registro intacto. '
    'Fuente81+App84, Qwen3.5 override sin promoción.162 integración pass/0 skips/8s. '
    'Fast inicial93075 falla dos detalles de formato; corregidos,18548 verde,Release16,67s,0 avisos/errores. '
    'No UI/audio/reserva humana.', '']
for turn in paired:
    lines += [f'## {turn["turnId"]} — {"útil" if turn["turnId"] in {"t3", "t4"} else "no útil"}', '',
        f'Entrada: {turn["request"]}', '', f'Final literal: {turn["final"]}', '']
    seen = set()
    for row in turn['compose']:
        if row.get('draft') in seen:
            continue
        seen.add(row.get('draft'))
        lines += [f'Borrador ({row.get("reason") or "sin veto Python"}): {row.get("draft")}', '',
            '```json', json.dumps(row.get('payload'), ensure_ascii=False, indent=2), '```', '']
report84 = base / 'PRUEBAS_BUSQUEDA_VACIA84.md'
report84.write_text('\n'.join(lines), encoding='utf-8')

out85 = base / 'astra-progress-phase85'
rows85 = [json.loads(s) for s in (out85 / 'posts.jsonl').read_text(encoding='utf-8').splitlines()]
lines = ['# C03 — prototipo de fase85', '',
    'Sólo datos: mismos seis paquetes82, comparados con phase=understanding. '
    'No fuente nueva, prompt adicional ni promoción. La etiqueta no basta: el modelo sigue '
    'leyendo archivos en t1/t2/t3 y trata t6 como comprensión del archivo, no de la pregunta. '
    'T5 cambia a interpretación de la petición; t4 identifica hora/CPU pero implica revisión. '
    'No trasladar este prototipo al producto. Es un resultado nativo, sin publicación/UI/audio.', '',
    'exit0;8,81s;GPU3171,5625MiB;RAM3259,47265625MiB;registro intacto.', '']
for row in rows85:
    lines += [f'## {row["turn"]} / {row["variant"]}', '', f'Entrada: {row["text"]}', '',
        row['response']['choices'][0]['message']['content'], '']
report85 = base / 'PRUEBAS_PROGRESO85.md'
report85.write_text('\n'.join(lines), encoding='utf-8')
for number, folder, report in [(84, out, report84), (85, out85, report85)]:
    files = [report, folder / 'PREREG.json', folder / 'RESULT.json',
        folder / ('paired.json' if number == 84 else 'posts.jsonl')]
    (base / f'TRAMO{number}_PINS.json').write_text(json.dumps({
        'scope': 'Development evidence, not human acceptance or model promotion',
        'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    }, indent=2), encoding='utf-8')

state = ('84 terminó27467exit0:2/4 útil. Causa vacía preservada; Python veta No se encontró/\n'
    'No se encontraron/No encontré como missing_failure. T1 composition_failed, t2 inventa\n'
    'cifrado; t3/t4 recuperan. PRUEBAS_BUSQUEDA_VACIA84.md/TRAMO84_PINS.json.\n'
    '76,11s,GPU3177,56MiB,RAM6325,94MiB,registro intacto.85 nativo terminóexit0:\n'
    'añadir sólo phase=understanding no corrige inferencias de lectura; NO adoptar.\n'
    'PRUEBAS_PROGRESO85.md/TRAMO85_PINS.json. Sin procesos/modelos propios activos.\n'
    'Siguiente86: reparar alcance de negación impersonal en el guard existente, con\n'
    'contrastes de ausencia de fallos; repetir cuatro turnos84. Progreso requiere otra\n'
    'representación de la actividad verdadera, no una etiqueta ambigua. No Full.')
for name in ('CHECKPOINT.md', 'HANDOFF.md'):
    path = base / name
    content = path.read_text(encoding='utf-8')
    path.write_text(content + '\n\n## Actualización84–85\n\n' + state + '\n', encoding='utf-8')
path = base / 'RELEVO_ACTIVO.json'
relay = json.loads(path.read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    checkpoint='84: causa vacía preservada, veto de negación impersonal;85 etiqueta de fase insuficiente; C03 EN_CURSO',
    continuation='Sin procesos activos.86: guard de negación con contrastes; repetir cuatro turnos84. Modelo sólo override. No Full.')
path.write_text(json.dumps(relay, ensure_ascii=False, indent=2), encoding='utf-8')
