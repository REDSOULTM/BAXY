"""Record the validated source repair and prepare its bounded full-mind repeat."""
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-positive-adversative498'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-positive-adversative498-private'
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
fast = (out / 'fast.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in fast
owners = (out / 'owners.log').read_text(encoding='utf-8-sig')
assert '3174 passed in 48.78s' in owners
source = root / 'src/baxy_mind/effect_intent.py'
patch = difflib.unified_diff(
    (private / 'effect_intent-before.py').read_text(encoding='utf-8-sig').splitlines(True),
    source.read_text(encoding='utf-8-sig').splitlines(True),
    fromfile='source487/effect_intent.py', tofile='source498/effect_intent.py')
(out / 'SOURCE.patch').write_text(''.join(patch), encoding='utf-8')
write(out / 'RESULT.json', {
    'utc': datetime.now(timezone.utc).isoformat(),
    'baseline': {'failed': 7, 'passed': 2, 'seconds': 1.60},
    'first_intervention': {'failed': 2, 'passed': 23, 'seconds': 1.11,
                           'reason': 'New separator split actions inside quoted note content; preserved failed log.'},
    'focal_after_quote_mask': {'passed': 25, 'seconds': .88},
    'extra_controls': 'Ten cases: five quote forms in two languages, preserving literal content and a real outside action.',
    'owners': {'passed': 3174, 'skips': 0, 'seconds': 48.78, 'session': 68020, 'exit': 0},
    'fast': {'passed': True, 'release_seconds': 3.85, 'warnings': 0, 'errors': 0, 'session': 13436, 'exit': 0},
    'source_sha256': sha(source), 'tests_sha256': sha(root / 'tests/test_effect_intent.py'),
    'limits': 'Source-level compound coverage only. Does not qualify contextual clarification, full product, UI, voice or final acceptance.'
})
(out / 'RESULT.md').write_text('''# Segunda acción tras pero/but

El producto conserva las dos acciones explícitas y el orden solicitado. El catálogo sigue limitando las operaciones disponibles. Las comillas se protegen al localizar fronteras, manteniendo el contenido original de la nota y las órdenes exteriores.

El baseline falló siete de nueve casos. La primera intervención falló los dos controles citados y su registro permanece guardado. Tras corregirlo, los 25 controles originales pasaron. Se añadieron diez controles de comillas y acción exterior.

Validación: cinco suites Python, 3174 aprobadas y cero skips en 48,78 s. `scripts/test_source_quality.ps1`: Fast verde; build Release en 3,85 s, cero advertencias y errores. No Full durante reparación. El siguiente tramo verifica la mente completa y la cadena de aclaración; esta corrección no acredita por sí sola comprensión del antecedente ni ejecución de audio.
''', encoding='utf-8')
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
script = (root / 'scratchpad/c03-audio-mind488.py').read_text(encoding='utf-8-sig')
script = script.replace('488', '499').replace("'muted':False", "'state':False")
old = "cases=[\n"
new = """cases=[
 {'id':'positive-but','request':'Pon el volumen al 37 pero desmutéalo','history':[],'expected':['audio.volume','audio.mute'],'arguments':{'level':37,'state':False}},
 {'id':'owner51-resumed','request':by_index[49]['body']+'\\nAclaración confiable del usuario: '+by_index[51]['body'],'history':history([49,50]),'expected':['audio.volume','audio.mute'],'arguments':{'level':100,'state':False}},
"""
assert old in script
script = script.replace(old, new, 1)
script = script.replace('source487 negative adversative repair; exact comparison against486 source485',
                        'source498 positive adversative and quote repair; eight exact baseline488 cases plus explicit positive-but and the actual C# ResumeObjective string')
script = script.replace('Unresolved owner46/51 remain open until whole product is demonstrated.',
                        'Unresolved owner46/51 remain open until whole product is demonstrated. The resumed case uses the literal string built by current C# but does not run its UI policy or prove that the shell reaches that branch. state is the actual mute argument; muted in old expectation notes was an observation field, never a returned or verified argument.')
target = root / 'scratchpad/c03-audio-mind499.py'
assert not target.exists()
target.write_text(script, encoding='utf-8')
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    path = base / name
    value = path.read_text(encoding='utf-8')
    value = value.replace('Fuente 498 en validación.', 'Fuente 498 validada en sus suites dueñas y Fast.')
    value = value.replace('Fast en sesión 13436; recoger antes de editar fuente o cargar un runtime.',
                          'Fast verde, Release 3,85 s, cero advertencias y errores; sesión 13436 recogida con exit 0.')
    value = value.replace('Siguiente: terminar validación 498; repetir', 'Siguiente: ejecutar scratchpad/c03-audio-mind499.py para repetir')
    path.write_text(value, encoding='utf-8')
record = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'))
record.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
              checkpoint='Fuente498: 3174 pruebas aprobadas y Fast verde; 497 cerrado sin promoción.',
              continuation='Ejecutar499: repetición de mente completa y cadena real de aclaración, sin efectos. C03 íntegro activo.')
write(base / 'RELEVO_ACTIVO.json', record)
print('498 validated and pinned; full-mind499 script ready.')
