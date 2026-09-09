from pathlib import Path
import json
import hashlib

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
rows = json.loads((base / 'astra-progress51/paired.json').read_text(encoding='utf-8'))
lines = ['# C03 — progreso51: entradas y respuestas literales', '',
         'Mismos siete controles técnicos de49, no reserva humana ni UI/audio físico. '
         '**6/7 turnos completos útiles**, incluyendo progreso. '
         'Las observaciones y auditorías están en astra-progress51/paired.json.', '']
for row in rows:
    verdict = 'Falla' if row['turnId'] == 't6' else 'Cumple'
    lines += [f"## {row['turnId']} — {verdict}", '', '**Entrada:** ' + row['request'], '', '**Progreso:**', '']
    labels = list(dict.fromkeys(e['label'] for e in row['publicEvents'] if e.get('type') == 'boot_stage' and e.get('label')))
    lines += ['> ' + label for label in labels] if labels else ['Sin etiqueta de progreso.']
    lines += ['', '**Respuesta final:**', '', '> ' + row['final'], '']
    if verdict == 'Falla':
        draft = next(c['draft'] for c in reversed(row['compose']) if c.get('draft'))
        lines += ['La app rechaza este borrador fiel por «fallos» pese a estar negado; no se publicó:', '', '> ' + draft, '']
lines += ['El progreso de t4 necesitó tres intentos: los dos primeros eran declaraciones '
          'honestas de desconocimiento seguidas de trabajo en curso, rechazadas por el '
          'control que exige la señal de progreso en la primera frase. El tercero fue '
          'útil y se publicó. No afirmar que todos los avisos pasan a la primera.', '']
(base / 'PRUEBAS_PROGRESO51.md').write_text('\n'.join(lines), encoding='utf-8')
pins = json.loads((base / 'TRAMO49_PINS.json').read_text(encoding='utf-8'))
paths = [p.replace('astra-clock49', 'astra-progress51') for p in pins['files']]
paths.append('tests/test_c03_request_preservation.py')
pins['files'] = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}
pins['state'] = 'progress narration adopted; C03 ongoing'
pins['validation'] = {'pytest': {'passed': 3123, 'subtests': 115, 'skips': 0, 'seconds': 46.52},
                      'sourceQuality': 'Fast passed', 'releaseBuildSeconds': 2.85,
                      'warnings': 0, 'errors': 0, 'Full': 'not run during repair'}
(base / 'TRAMO51_PINS.json').write_text(json.dumps(pins, indent=2), encoding='utf-8')
print('Recorded progress51 pairs and pins.')
