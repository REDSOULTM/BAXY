"""Freeze the corrected candidate before Full, preserving the earlier red owner run."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
out = base/'astra-window-vocabulary-source705'
assert not (out/'CANDIDATE2.json').exists()
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
write = lambda p, v: p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
record = read(out/'PREREG.json')
files = {p.relative_to(root).as_posix(): p for folder in ['experiments/voice_latency', 'scripts', 'src/baxy_mind']
         for p in (root/folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest = hashlib.sha256()
for name in sorted(files):
    digest.update(name.encode()+b'\n'+sha(files[name]).encode()+b'\n')
tree = digest.hexdigest()
for name in ['audit_fresh_postweight_stt_sources.py', 'evaluate_reserved_stt.py']:
    path = root/'experiments/stt_quality'/name
    data = path.read_bytes()
    assert data.count(record['python_tree_sha256'].encode()) == 1
    path.write_bytes(data.replace(record['python_tree_sha256'].encode(), tree.encode()))
path = root/'tests/test_price_v8_veto_damage_by_cause.py'
data = path.read_bytes()
assert data.count(record['sources']['src/baxy_mind/llm.py'].encode()) == 1
path.write_bytes(data.replace(record['sources']['src/baxy_mind/llm.py'].encode(), sha(root/'src/baxy_mind/llm.py').encode()))
for name in ['python-owners', 'python-owners2']:
    (out/(name.upper()+'.log')).write_bytes((Path(os.environ['TEMP'])/('c03-window-vocabulary705-'+name+'.log')).read_bytes())
assert '691 passed' in (out/'PYTHON-OWNERS2.log').read_text(encoding='utf-8-sig')
record.update(utc=datetime.now(timezone.utc).isoformat(),
              sources={name: sha(root/name) for name in record['sources']},
              python_tree_sha256=tree, python_files=len(files),
              expanded_python_owners={'passed': 691, 'skipped': 0, 'seconds': 6.13,
                  'previous': {'passed': 689, 'failed': 1, 'cause': 'A verified lowercase filename was rejected as lowercase prose. The same lexical scratch copy now preserves that exact identity; lowercase surrounding prose still fails. Added a control, no test removed.'}},
              full_status='pending', adopted=False)
write(out/'CANDIDATE2.json', record)
state = read(base/'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=record['utc'],
             checkpoint='705 candidato:691dueñasPython pass/0skip. App ampliada26335 sigue en curso. Replay de18borradores694:12 ahora pasan idénticos,6fallan por gramática;18ventanal704 siguen fallando. No inferencia nueva ni cobertura.',
             continuation='Recoger26335, conservar resultado App. Si verde,Full705 con candidato2 sellado. No repetir dueñas verdes sin cambio. Después producto/regresión completa y adopción si evidencia suficiente. Encuesta26/716/0.')
write(base/'RELEVO_ACTIVO.json', state)
print({'candidate2': True, 'tree': tree, 'python_passed': 691, 'adopted': False})
