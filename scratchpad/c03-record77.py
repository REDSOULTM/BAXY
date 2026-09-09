from pathlib import Path
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-files77-template'
paired = json.loads((out / 'paired.json').read_text(encoding='utf-8'))
wire = [json.loads(s) for s in (out / 'wire-31624.jsonl').read_text(encoding='utf-8').splitlines()]
assert not any(row.get('httpError') for row in wire)
assert all(sum(m['role'] == 'system' for m in row['payload']['messages']) <= 1 for row in wire)
lines = ['# C03 — template integrado77', '',
    '7/10 útiles frente a6/10 en74/75. Se elimina el rechazo HTTP y se recupera checksum. '
    '125,11s,GPU3177,56MiB,RAM6765,18MiB,exit0,registro intacto. Cada paquete HTTP real '
    'contiene como máximo un system. Qwen3.5 sigue en override; no promoción ni UI/voz/audio/reserva humana.', '',
    't6: el chat nativo explica UTF8 correctamente; C# lo veta como looks_like_failure y los '
    'tres intentos de recomposición Python como asserted_failure. t10: la aclaración nativa pregunta '
    'el nivel, pero C# la rechaza como unsolicited_catalog; el fallback pierde el dato pendiente y '
    'pregunta por dispositivo. t9: el reconocedor determinista explicit_effects selecciona sólo '
    'audio.status; no es una pérdida introducida por el modelo. Estas tres causas siguen abiertas.', '',
    'Four owner suites:1149 pass/0 skips/5,62s; Fast31677exit0,Release1,51s,0 avisos/errores. '
    'Logs preservados junto al panel. No Full durante reparación.', '']
for turn in paired:
    useful = turn['turnId'] in {'t1', 't2', 't3', 't4', 't5', 't7', 't8'}
    labels = [e['label'] for e in turn['publicEvents'] if e.get('type') == 'boot_stage' and e.get('label')]
    lines += [f'## {turn["turnId"]} — {"útil" if useful else "no útil"}', '',
              f'Entrada: {turn["request"]}', '', f'Final literal: {turn["final"]}', '',
              f'Labels de progreso: {json.dumps(labels, ensure_ascii=False)}', '']
    seen = set()
    for row in turn['compose']:
        if row.get('draft') not in seen:
            seen.add(row.get('draft'))
            lines += [f'Borrador ({row["intent"]}, {row.get("reason") or "sin veto Python"}): {row.get("draft")}', '']
report = base / 'PRUEBAS_TEMPLATE77.md'
report.write_text('\n'.join(lines), encoding='utf-8')
files = [report, out / 'PREREG.json', out / 'RESULT.json', out / 'paired.json', out / 'wire-31624.jsonl']
for name in ('c03-template77-pytest.log', 'c03-template77-fast.log'):
    path = out / name
    path.write_bytes((Path(os.environ['TEMP']) / name).read_bytes())
    files.append(path)
(base / 'TRAMO77_PINS.json').write_text(json.dumps({'scope': 'Template repair integrated; source hashes in PREREG; C03 open',
    'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}, indent=2), encoding='utf-8')
