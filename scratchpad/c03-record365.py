"""Pin365 after owner suites/Fast and update the exact next product action."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-declared-memory365'
assert 'source_quality_gate_passed: mode=Fast' in (out / 'fast.log').read_text(encoding='utf-8-sig')
pins = {}
for name in ['src/Baxy.App/NaturalMemoryRequestParser.cs',
             'tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs',
             'tests/Baxy.Integration.Tests/MemoryTurnSessionTests.cs']:
    with (root / name).open('rb') as stream:
        pins[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
(out / 'PINS.json').write_text(json.dumps(pins, indent=2) + '\n', encoding='utf-8')
path = base / 'CHECKPOINT.md'
text = path.read_text(encoding='utf-8')
text = text.replace('365 última fuente WIP:', '365 última fuente validada, integración pendiente:')
text = text.replace('MindShellEndToEndTests. No repetir. Fast365 ahora en curso; después',
    'MindShellEndToEndTests. Fast365 verde18,06s0warnings/errors, handle91387cerrado. RESULT/PINS365 escritos. Siguiente:')
text = text.replace('NO ejecutar producto antes de dueñas/Fast verdes.',
    'Dueñas/Fast ya verdes; ejecutar ahora366 y registrarhandle.')
path.write_text(text, encoding='utf-8')
path = base / 'HANDOFF.md'
text = path.read_text(encoding='utf-8').replace('365WIP en NaturalMemoryRequestParser.cs:', '365 validada en fuente; integración pendiente. NaturalMemoryRequestParser.cs:')
text = text.replace('SIGUIENTE: recoger Fast365 recién lanzado. Si verde, ejecutar preparado scratchpad/c03-product366.py:',
    'Fast365verde18,06s0warnings/errors; handle91387cerrado. RESULT/PINS365 escritos.\nSIGUIENTE: ejecutar preparado scratchpad/c03-product366.py:')
path.write_text(text, encoding='utf-8')
path = base / 'RELEVO_ACTIVO.json'
state = json.loads(path.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='365 private name binding validated:1926pass0skip4m33s, Fast18.06s green. All test handles closed. Product366 ready; source362Python unchanged.',
    continuation='Run product366 now, same10controls364 with source365 only; inspect every turn/journal. Full C03 remains active.')
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('365 validated/pinned;366 next.')
