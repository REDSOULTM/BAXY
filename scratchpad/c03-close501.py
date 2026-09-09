"""Pin source validation; integrated audio/plan verification remains separate."""
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-context-level501'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-context-level501-private'
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert '3377 passed, 121 subtests passed in 48.89s' in (out / 'owners.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out / 'fast.log').read_text(encoding='utf-8-sig')
patches = []
pins = {}
for relative in ['src/baxy_mind/effect_intent.py', 'src/baxy_mind/__main__.py']:
    path = root / relative
    before = private / (path.stem + '-before.py')
    patches.extend(difflib.unified_diff(before.read_text(encoding='utf-8-sig').splitlines(True),
                                      path.read_text(encoding='utf-8-sig').splitlines(True),
                                      fromfile='before/' + relative, tofile='after/' + relative))
    pins[relative] = sha(path)
(out / 'SOURCE.patch').write_text(''.join(patches), encoding='utf-8')
write(out / 'RESULT.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'source_sha256': pins,
    'baseline': {'failed': 6, 'passed': 20, 'seconds': 1.61},
    'resolver_focal': {'passed': 26, 'seconds': .75},
    'turn_binding_focal': {'passed': 11, 'seconds': 1.66},
    'preserved_failures': ['turn-first-intervention.log: level argument absent across context boundary',
                           'turn-second-intervention.log: unmute clitic argument absent'],
    'owners': {'passed': 3377, 'subtests_passed': 121, 'skips': 0, 'seconds': 48.89, 'session': 98547, 'exit': 0},
    'fast': {'passed': True, 'release_seconds': 3.31, 'warnings': 0, 'errors': 0, 'session': 51448, 'exit': 0},
    'limits': 'Source validation only. Actual turn/plan/arguments protocol502 follows; no audio execution, UI or C03 acceptance.'
})
(out / 'RESULT.md').write_text('''# Nivel numérico con antecedente único

Una respuesta numérica hereda el objeto sólo cuando el pedido anterior del usuario coincide con el contrato de aclaración audio.volume/level del catálogo. Las dos superficies literales vuelven a atravesar el lector ordinario. No se heredan acciones ya completas, objetivos múltiples, pedidos de otros dispositivos ni texto del asistente. Las negaciones, correcciones y nuevas órdenes se conservan.

El turno y el plan reciben el mismo referente. Al materializar el nivel se vuelve a probar el contrato incompleto y la respuesta numérica única; no basta encontrar un número cercano. El binding de unmute reutiliza la misma familia de clíticos que el reconocimiento de operaciones. No se cambian prompts, samplers, runtime ni el shell.

Baseline: 6 fallos, 20 aprobados. Resolver: 26 aprobados. Turno y argumentos: 11 aprobados; los fallos intermedios de nivel y estado siguen guardados. Siete suites dueñas: 3377 aprobados y 121 subtests aprobados, cero skips, 48,89 s. Fast verde; Release 3,31 s, cero advertencias y errores.

Pendiente: protocolo real 502 con los incidentes y sus planes/argumentos. Esta validación aún no demuestra el audio físico, la interfaz ni el cierre de C03.
''', encoding='utf-8')
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    path = base / name
    text = path.read_text(encoding='utf-8')
    text = text.replace('tramo 501 (preparación)', 'tramo 501 validado; 502 preparado')
    text += '\n501 cerrado: 3377 pass y 121 subtests pass, cero skips, 48,89 s; Fast verde, Release 3,31 s sin advertencias ni errores. Nueva lectura acotada del nivel pendiente y binding de nivel/unmute; fuente effect_intent y __main__501, llm466. Siguiente: scratchpad/c03-audio-mind502.py, 14 turnos con plan/argumentos reales según el protocolo del shell, sin efectos. Recoger runtime antes de editar.\n'
    path.write_text(text, encoding='utf-8')
record = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'))
record.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
              checkpoint='Fuente501:3377 pass,121 subtests,0 skips y Fast verde. Llaves y negaciones conservadas.',
              continuation='Ejecutar502:14 turnos más bindings reales, sin efectos. Recoger antes de editar fuente. C03 íntegro activo.')
write(base / 'RELEVO_ACTIVO.json', record)
print('501 source validation closed; integrated502 still required.')
