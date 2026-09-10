"""Adopt validated model-independent input-scope source773."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'MACHINE_SCOPE773'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert not (OUT / 'ADOPTION.json').exists()
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only']).strip()
pins = read(OUT / 'SOURCE_PINS.json')
assert all(sha(ROOT / p) == h for p, h in pins.items())
for name, marker in [('final', b'2121 passed, 1 skipped in 79.73s'),
                     ('fast', b'source_quality_gate_passed: mode=Fast')]:
    raw = (Path(os.environ['TEMP']) / f'c03-machine-scope773-{name}.log').read_bytes().replace(b'\r\n', b'\n')
    assert marker in raw
    (OUT / (name + '.log')).write_bytes(raw)
now = datetime.now(timezone.utc).isoformat()
write(OUT / 'VALIDATION.json', {'utc': now,
    'python': 'C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe',
    'command': '-X utf8 -m pytest tests/test_c03_machine_preposition_scope.py tests/test_machine_status_scope.py tests/test_system_status_scope_grounding.py tests/test_effect_intent.py tests/test_stt_quality_evaluators.py tests/test_validate_physical_wake_v17_program.py tests/test_price_v8_veto_damage_by_cause.py -q',
    'passed': 2121, 'failed': 0, 'environmental_skips': 1, 'seconds': 79.73,
    'skip': 'Absent private blind STT campaign inputs; no voice credit.',
    'new_boundary_cases': 55, 'test_exit_code': 0, 'test_session': 42128, 'test_terminal_collected': True,
    'fast_command': 'scripts/test_source_quality.ps1 -Mode Fast', 'fast_exit_code': 0,
    'fast_session': 36710, 'fast_terminal_collected': True, 'release_seconds': 21.94, 'warnings': 0, 'errors': 0,
    'all_source_pins_unchanged_after_validation': True,
    'full_new': False, 'full_reason': 'Python-only source adoption; final Full still required.',
    'coverage_added': 0, 'real_product_pending': '774 seven-case battery category plus ten ES/EN/mixed development variants.'})
write(OUT / 'ADOPTION.json', {'utc': now, 'status': 'adopted_after_owners_integrity_fast',
    'source_pins': 'SOURCE_PINS.json', 'commit': 'Containing commit',
    'changed_layer': 'Existing deterministic input-scope rules, independent of model.',
    'new_model_or_profile': False, 'prompts_and_budgets_unchanged': True, 'coverage_added': 0})
(OUT / 'REPORT.md').write_bytes('''# La preposición española conserva la lectura de este equipo

La consulta de batería H0359 no llegaba a Core: el patrón de hardware ajeno interpretaba la preposición «a» de «a la notebook» como el artículo indefinido inglés. El mismo problema se reproducía con posesivos, demostrativos y otras denominaciones del equipo. Se corrigió esa distinción dentro del verificador existente; no hay condición por modelo, nombre de aplicación ni mensaje histórico completo.

La primera versión permitió correctamente las30variantes locales, pero dos controles negativos expusieron límites que el veto accidental ocultaba: «quedaría» es hipotético y el portátil de otra persona no es una observación de este PC. Se completaron las categorías de estado condicional y dueño ajeno explícito en las reglas existentes. Las hipótesis, estados pasados, negaciones, conocimiento sobre hardware y catálogo cerrado conservan sus límites.

La línea base fue30fallos/22pass. El primer conjunto dueño dio2094pass/2fallos; ambos fallos están preservados y reparados. La versión final supera55controles nuevos y el conjunto de pruebas dueñas e integridad:2121pass, cero fallos,1skip ambiental de datos STT privados ausentes,79,73s. Fast terminó0 con Release21,94s, cero advertencias y errores. Los seis pins permanecieron intactos. Las dos declaraciones vigentes del programa407 se actualizaron; V8 y los sellos históricos wake no cambian.

Modelo, backend, sampler, prompts y presupuestos siguen iguales.774 comprobará los siete casos originales de la categoría batería y diez variantes declaradas de desarrollo, con lecturas frescas y el criterio original. No es una comparación nativa entre modelos ni una certificación de UI/voz. Encuesta26cubiertos/716abiertos/0NA; C03 activo y Full final pendiente.
'''.encode('utf-8'))
note = ('773 adoptado: preposición española conserva scope local y límites de condicional/dueño ajeno. '
        '2121pass/1skipSTT/79,73s,55nuevos; Fast0/Release21,94s, sesiones42128/36710 recogidas. '
        '6pins intactos; programa407=7862ae1effb430cff9cbb057fa83912786bca493faba55b5c9636b5cd7181b18. '
        'Publicar y ejecutar774 categoría batería completa7+10variantes, no inferencia activa.26/716/0.\n\n')
cp = BASE / 'CHECKPOINT.md'
pending = cp.with_suffix('.pending.md')
pending.write_bytes(note.encode('utf-8') + cp.read_bytes())
pending.replace(cp)
state = read(BASE / 'RELEVO_ACTIVO.json')
state.update(checkpoint=note.strip(), confirmedAtUtc=now, activeValidation=None,
             workStatus='machine_scope773_adopted_pending_publication',
             continuation='Publish773, run prepared774 complete battery category and10 development variants. Require all guards then manually adjudicate fresh observations.')
write(BASE / 'RELEVO_ACTIVO.json', state)
handoff = BASE / 'HANDOFF.md'
text = handoff.read_text(encoding='utf-8')
start = text.index('Siguiente773:')
end = text.index('\n\nCambiar estrategia', start)
text = text[:start] + ('773 adoptado, pendiente publicación: MACHINE_SCOPE773/VALIDATION.json.2121pass/1skipSTT/79,73s,55nuevos; '
    'Fast0/Release21,94s, sesiones42128/36710 recogidas.6pins intactos, programa407=7862ae1effb430cff9cbb057fa83912786bca493faba55b5c9636b5cd7181b18. '
    'Repara a+determinante español frente a artículo inglés en hardware ajeno; prueba inicial30fail/22pass y2094pass/2límites expuestos preservados. '
    'Condicional quedar y otro dueño explícito conservan exclusión. No modelo/prompt/presupuesto nuevos. '
    'Siguiente: publicar773 y ejecutar scratchpad/c03-status-batch774.py con Python registrado;7casos batería originales+10variantes ES/EN/mixtas. '
    'No editar fuente durante ejecución; reviewer774 preparado. Generalización de valores/ausencia de batería aún pendiente si sólo se observa el mismo estado físico.') + text[end:]
handoff.write_bytes(text.encode('utf-8'))
artifacts = [OUT / name for name in ['SOURCE_PINS.json', 'PROGRAM.json', 'PLAN.json',
    'baseline-initial.log', 'owners-initial.log', 'boundary-initial.log', 'final.log', 'fast.log',
    'VALIDATION.json', 'ADOPTION.json', 'REPORT.md']]
artifacts += [ROOT / 'scratchpad' / name for name in ['c03-prepare-machine773.py',
    'c03-adopt-machine773.py', 'c03-status-batch774.py', 'c03-review-status774.py']]
artifact_pins = {p.relative_to(ROOT).as_posix(): sha(p) for p in artifacts}
write(OUT / 'PINS.json', artifact_pins)
paths = [ROOT / p for p in pins] + artifacts + [OUT / 'PINS.json'] + [BASE / name for name in ['CHECKPOINT.md', 'RELEVO_ACTIVO.json', 'HANDOFF.md']]
subprocess.run(['git', 'add', '--', *[p.relative_to(ROOT).as_posix() for p in paths]], check=True)
for p, h in {**pins, **artifact_pins}.items():
    assert hashlib.sha256(subprocess.check_output(['git', 'show', ':' + p])).hexdigest() == h, p
subprocess.run(['git', 'diff', '--cached', '--check'], check=True)
print(json.dumps({'source_pins': len(pins), 'artifact_pins': len(artifact_pins), 'staged': True}))
