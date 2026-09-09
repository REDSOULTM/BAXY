from pathlib import Path
import datetime
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
rows = json.loads((base / 'astra-routes-volume46/paired.json').read_text(encoding='utf-8'))
report = base / 'PRUEBAS_RUTAS_C03_TRAMO46.md'
prior = report.read_text(encoding='utf-8').split('\n## Producto corregido —')[0]
lines = [prior, '## Producto corregido — astra-routes-volume46', '',
         'Mismos33 normales. 32/33 útiles: se reparan t23/t24; t10 contiene un error '
         'factual nuevo. No se aprueba el panel completo. 112,33s, GPU3499,56MiB, '
         'RAM5872,35MiB, registro intacto, exit0. Fuente de PREREG más movimiento '
         'posterior de un comentario sin efecto ejecutable; hashes finales en TRAMO46_PINS.json.', '']
for row in rows:
    verdict = ('FALLO: atribuye a la Luna mantener a la Tierra en su órbita; '
               'la explicación causal no es fiel.' if row['turnId'] == 't10' else
               'ÚTIL/FIEL: petición y hechos concordantes; niveles80/60/40 y restauración100 verificados.')
    lines += [f'### {row["turnId"]}', '', f'Entrada: {row["request"]}', '',
              f'Respuesta: {row["final"]}', '', verdict, '']
report.write_text('\n'.join(lines), encoding='utf-8')
files = ['src/baxy_mind/effect_intent.py', 'src/baxy_mind/llm.py', 'src/baxy_mind/__main__.py',
         'src/baxy_mind/request_reading.py', 'src/baxy_mind/voice_output.py',
         'tests/test_effect_intent.py', 'tests/test_turn_policy.py']
pins = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'status': 'EN_CURSO',
        'adopted': 'Incomplete absolute audio level clarification; existing pending context now completes80/60/40.',
        'validation': {'ownerPass': 2525, 'relatedPass': 402, 'subtests': 115, 'skips': 0,
                       'fast': 'green; build4.73s; zero warnings/errors; no Full'},
        'product': {'normal': 33, 'useful': 32, 'failed': ['t10 gravity factual example'],
                    'path': 'astra-routes-volume46'},
        'files': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in files}}
(base / 'TRAMO46_PINS.json').write_text(json.dumps(pins, ensure_ascii=False, indent=2), encoding='utf-8')
print('Recorded33 corrected-source replies and final source pins.')
