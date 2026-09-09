from pathlib import Path
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-clock49'
rows = json.loads((out / 'paired.json').read_text(encoding='utf-8'))
reasons = [
    ('Falla', 'Respuesta final fiel; el progreso publicado inventa 14:30 y CPU45%, sin observaciones.'),
    ('Falla', 'Respuesta final fiel; el progreso declara que la hora no está disponible, aunque la lectura se completa.'),
    ('Cumple', 'Progreso de trabajo en curso y respuesta inglesa con hora/volumen verificados.'),
    ('Cumple', 'Antes de medir declara que aún no sabe la hora/audio y que sigue en progreso; luego responde con hechos verificados.'),
    ('Cumple', 'Hora verificada; conserva la prohibición independiente, sin silenciar.'),
    ('Falla', 'Hechos y borrador fieles; la app rechaza «No hay fallos reportados» con reversed_result y agota reintentos.'),
    ('Cumple', 'Lectura fiel de audio; recupera después del fallo de composición anterior.'),
]
lines = ['# C03 — pares literales de la regresión de reloj49', '',
         'Panel técnico consumido, siete entradas idénticas a compound-shell48. '
         'No reserva humana ni acreditación de UI/audio físico. '
         '**4/7 turnos completos útiles; 6/7 respuestas finales fieles publicadas.** '
         'Los hechos y auditorías completos están en astra-clock49/paired.json.', '']
for row, (verdict, reason) in zip(rows, reasons, strict=True):
    lines += [f"## {row['turnId']} — {verdict}", '', '**Entrada:** ' + row['request'], '', '**Progreso publicado:**', '']
    labels = list(dict.fromkeys(e['label'] for e in row['publicEvents'] if e.get('type') == 'boot_stage' and e.get('label')))
    lines += ['> ' + label for label in labels] if labels else ['Sin etiqueta de progreso.']
    lines += ['', '**Respuesta final:**', '', '> ' + row['final'], '', reason, '']
    if row['terminal'] == 'composition_failed':
        draft = next(c['draft'] for c in reversed(row['compose']) if c.get('draft'))
        lines += ['Borrador fiel rechazado por la app, no publicado:', '', '> ' + draft, '']
(base / 'PRUEBAS_RELOJ_COORDINADO49.md').write_text('\n'.join(lines), encoding='utf-8')
paths = ['src/baxy_mind/effect_intent.py', 'tests/test_effect_intent.py',
         'src/Baxy.App/MainWindowViewModel.cs', 'src/Baxy.App/UserMessagePolicy.cs',
         'src/baxy_mind/llm.py', 'src/baxy_mind/request_reading.py', 'src/baxy_mind/voice_output.py',
         'artifacts/comprobaciones/C03/astra-clock49/PREREG.json',
         'artifacts/comprobaciones/C03/astra-clock49/RESULT.json',
         'artifacts/comprobaciones/C03/astra-clock49/paired.json']
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
pins = {'state': 'clock reader adopted; C03 ongoing',
        'files': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths},
        'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest(),
        'validation': {'pytest': {'passed': 2957, 'subtests': 115, 'skips': 0, 'seconds': 45.09},
                       'sourceQuality': 'Fast passed', 'releaseBuildSeconds': 16.93,
                       'warnings': 0, 'errors': 0, 'Full': 'not run during repair'}}
(base / 'TRAMO49_PINS.json').write_text(json.dumps(pins, indent=2), encoding='utf-8')
print('Recorded seven literal pairs and source/runtime pins for tranche49.')
