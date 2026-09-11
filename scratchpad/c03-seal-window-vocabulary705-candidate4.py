"""Seal the boundary correction only after its owner checks, before another Full."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-window-vocabulary-source705'
temp = Path(os.environ['TEMP'])
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
write = lambda p, v: p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert not (out / 'CANDIDATE4.json').exists()
record = read(out / 'CANDIDATE3.json')
files = {p.relative_to(root).as_posix(): p
         for folder in ['experiments/voice_latency', 'scripts', 'src/baxy_mind']
         for p in (root / folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest = hashlib.sha256()
for name in sorted(files):
    digest.update(name.encode() + b'\n' + sha(files[name]).encode() + b'\n')
tree = digest.hexdigest()
assert sha(root / 'src/baxy_mind/llm.py') == record['sources']['src/baxy_mind/llm.py']
logs = {}
for label in ['boundary-dotnet-baseline', 'python-owners3', 'python-owners4', 'dotnet-owners3', 'dotnet-boundary-final']:
    path = temp / ('c03-window-vocabulary705-' + label + '.log')
    logs[label] = path.read_text(encoding='utf-8-sig')
assert '706 passed' in logs['python-owners4']
assert 'Con error:     2, Superado:   188, Omitido:     0' in logs['dotnet-owners3']
assert 'Con error:     0' in logs['dotnet-boundary-final']
for label in logs:
    destination = out / (label.upper() + '.log')
    data = (temp / ('c03-window-vocabulary705-' + label + '.log')).read_bytes()
    if destination.exists():
        assert destination.read_bytes() == data
    else:
        destination.write_bytes(data)
for name in ['audit_fresh_postweight_stt_sources.py', 'evaluate_reserved_stt.py']:
    path = root / 'experiments/stt_quality' / name
    data = path.read_bytes()
    assert data.count(tree.encode()) == 1
record.update(utc=datetime.now(timezone.utc).isoformat(),
              sources={name: sha(root / name) for name in record['sources']},
              python_tree_sha256=tree, python_files=len(files),
              full_status='pending_fourth_attempt', full2_session=None, adopted=False,
              boundary_fix='Whole-name matching preserves compound identifiers through dots/hyphens and permits sentence punctuation. Original prose and factual checks remain untouched.',
              boundary_baseline={'python_failed': 5, 'python_passed': 69,
                                 'dotnet_failed': 4, 'dotnet_passed': 32},
              fixture_control='Atlas.route was also accepted with the mask entirely disabled by the pre-existing case-sensitive code policy. The fixture now proves uppercase compound preservation directly and tests the existing lowercase-code rejection separately; no product policy broadened.',
              expanded_python_owners={'passed': 706, 'skipped': 0, 'seconds': 8.06},
              dotnet_owners={'log': 'DOTNET-OWNERS3.log', 'passed': 188, 'failed': 2, 'skipped': 0,
                             'failures': ['Uppercase identifier fixture expected a broader policy than705 changes; corrected with explicit raw-span preservation plus lowercase-code check.',
                                          'RequestedSaveOffersEnableAndResumesOnlyAfterExactConfirmation: no outbox entry; isolated reproduction retained in final log.'],
                             'boundary_final_log': 'DOTNET-BOUNDARY-FINAL.log',
                             'prior_full_startup_failures': 'The three Full2 failures passed in this owner run; no cause is inferred from non-reproduction.'},
              full2={'exit_code': 1, 'intentionally_interrupted': True, 'completed_validation': False,
                     'reason': 'Known candidate defect and three observed startup failures; receipts preserved.'})
write(out / 'CANDIDATE4.json', record)
state = read(base / 'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=record['utc'], workStatus='window_vocabulary705_candidate4_ready_for_full',
             checkpoint='705 candidato4: límite corregido,706Python verdes; dueñasApp y3fallos de arranque reproducidos según DOTNET-OWNERS3.log. Full2 interrumpido, no aceptación. Fuente no adoptada; encuesta26/716/0.',
             continuation='Ejecutar Full4 completo sobre CANDIDATE4 sellado. Full3/94418 fue interrumpido antes de suites: arrancó por error después de fallar el sellado, no sirve como validación. Si Full4 verde, producto706 con73turnos originales, revisión y adopción delimitada. No atribuir Atlas.route a regresión705; control sin máscara conservado.')
write(base / 'RELEVO_ACTIVO.json', state)
print({'candidate': 4, 'python_tree_sha256': tree, 'adopted': False})
