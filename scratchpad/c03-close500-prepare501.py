"""Pin the validated clitic repair and preregister bounded reference resolution."""
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
out = base / 'astra-volume-clitic500'
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert '3188 passed in 47.04s' in (out / 'owners.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out / 'fast.log').read_text(encoding='utf-8-sig')
source = root / 'src/baxy_mind/effect_intent.py'
before = local / 'C03-volume-clitic500-private/effect_intent-before.py'
(out / 'SOURCE.patch').write_text(''.join(difflib.unified_diff(
    before.read_text(encoding='utf-8-sig').splitlines(True), source.read_text(encoding='utf-8-sig').splitlines(True),
    fromfile='source498/effect_intent.py', tofile='source500/effect_intent.py')), encoding='utf-8')
write(out / 'RESULT.json', {
    'utc': datetime.now(timezone.utc).isoformat(),
    'baseline': {'failed': 9, 'passed': 5, 'seconds': 1.73},
    'first_intervention': {'failed': 2, 'passed': 34, 'seconds': 1.00,
                           'reason': 'Clause heads still omitted ponle; dative TV scope was not excluded. Both failed controls preserved and fixed through existing shared grammars.'},
    'focal': {'passed': 36, 'seconds': .75},
    'owners': {'passed': 3188, 'skips': 0, 'seconds': 47.04, 'session': 53141, 'exit': 0},
    'fast': {'passed': True, 'release_seconds': 3.37, 'warnings': 0, 'errors': 0, 'session': 4862, 'exit': 0},
    'source_sha256': sha(source), 'tests_sha256': sha(root / 'tests/test_effect_intent.py'),
    'change': 'Shared setting verb includes ponle and is reused by clause boundaries. Missing level with explicit local PC/computer asks for level. Existing audio-scope guard also recognizes dative a/al/to for non-global audio targets.',
    'limits': 'Only source and owned validation; original current-fragment context and C# resumption remain to prove.'
})
(out / 'RESULT.md').write_text('''# Volumen con ponle y objeto local

Se conserva la misma operación para pon y ponle. La gramática compartida de ajustes también delimita las cláusulas; se retiran las alternativas duplicadas que sustituye. El pedido sin nivel y con objeto local PC/computer conserva audio.volume y pregunta level. Los objetivos de audio en otra aplicación, TV o micrófono siguen fuera del volumen global, incluido el complemento dativo.

Baseline: 9 fallos y 5 aprobados. La primera intervención dejó dos fallos de alcance, guardados en first-intervention.log; se corrigieron antes de integrar. Focal: 36 aprobados. Cinco suites dueñas: 3188 aprobados, cero skips, 47,04 s. Fast verde, Release 3,37 s, cero advertencias y errores. No Full durante reparación.

La cadena completa de reanudación ya se reconoce en la prueba pura. Todavía falta demostrar el fragmento contextual original, el recorrido del shell, los argumentos y el audio real; esta tanda no cierra C03.
''', encoding='utf-8')
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
new = base / 'astra-context-level501'
private = local / 'C03-context-level501-private'
new.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
for relative in ['src/baxy_mind/effect_intent.py', 'src/baxy_mind/__main__.py', 'tests/test_effect_intent.py']:
    shutil.copy2(root / relative, private / (Path(relative).stem + '-before.py'))
write(new / 'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(),
    'cause': 'Owner51 begins with the numeric answer to an immediately preceding, now explicitly recognized missing-level request. Current turn and plan readers must retain this referent without importing unrelated old actions.',
    'hypothesis': 'Resolve only an explicit numeric first clause against a unique prior user request whose authenticated clarification contract is audio.volume/level. Reuse the closed resolver on the two exact user literals, with all denials/corrections/catalog guards. Assistant prose never supplies authority or a target.',
    'controls': 'Absent/other/multiple/negative antecedents; independent new requests; unavailable operations; current negation and retraction; additional positive/negative clauses. Check actual plan argument grounding as well as turn selection.',
    'heritage': 'CONTEXTO_RECUPERACION489.md; existing _contextual_output_level_target and clock-reference reader. 489 ranking alone and490 sampling alone failed. 500 repairs the actual prior missing-level contract. No new model sweep or blanket history concatenation.',
    'limits': 'No reserve cases or provider effects. Pure tests first, then integrated source validation and actual mind/plan before adoption of contextual behavior.'
})
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    path = base / name
    value = path.read_text(encoding='utf-8')
    value = value.replace('tramo 498', 'tramo 501 (preparación)')
    value += '\n500 cerrado: 3188 pass, cero skips, 47,04 s; Fast verde, Release 3,37 s sin advertencias ni errores. Fuente effect_intent500, llm466; registro intacto. 501 sólo preregistrado: respuesta numérica a un único pedido previo de volumen con nivel faltante. Falta baseline antes de editar. No prueba ni runtime activo.\n'
    path.write_text(value, encoding='utf-8')
record = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'))
record.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
              checkpoint='Fuente500 validada: 3188 pass y Fast verde. 501 preregistrado, sin cambios aún.',
              continuation='Baseline de referencia numérica acotada antes de editar; comprobar después turn y plan/argumentos. C03 íntegro activo.')
write(base / 'RELEVO_ACTIVO.json', record)
print('500 closed and pinned;501 preregistered, no context source changes yet.')
