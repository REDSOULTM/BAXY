"""Declare and pin the shared present-frame/current-read repair before adoption."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-fresh-window-source683'
out.mkdir(exist_ok=False)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
files = {p.relative_to(root).as_posix(): p for folder in ['experiments/voice_latency', 'scripts', 'src/baxy_mind']
         for p in (root / folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest = hashlib.sha256()
for name in sorted(files):
    digest.update(name.encode() + b'\n' + sha(files[name]).encode() + b'\n')
tree = digest.hexdigest()
for name in ['audit_fresh_postweight_stt_sources.py', 'evaluate_reserved_stt.py']:
    path = root / 'experiments/stt_quality' / name
    data = path.read_bytes()
    old = b'03d2cb9ef539220225bb0efff7fc499cd2707466cf98fb1160d899b5a0ba67d7'
    assert data.count(old) == 1
    path.write_bytes(data.replace(old, tree.encode()))
owners = subprocess.check_output(['git', 'grep', '-l', '-E', 'effect_intent|resolve_explicit_effects', '--', 'tests/test_*.py'], cwd=root, text=True).splitlines()
owners = sorted(set(owners + ['tests/test_c03_fresh_window_queries.py', 'tests/test_window_query_context.py']))
for suffix, name in [('baseline', 'BASELINE'), ('focal', 'FOCAL')]:
    (out / (name + '.log')).write_bytes((Path(os.environ['TEMP']) / f'c03-fresh-window683-{suffix}.log').read_bytes())
assert '36 failed, 16 passed' in (out / 'BASELINE.log').read_text(encoding='utf-8-sig')
assert '52 passed' in (out / 'FOCAL.log').read_text(encoding='utf-8-sig')
record = {'utc': datetime.now(timezone.utc).isoformat(), 'adopted': False,
    'parent_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
    'sources': {name: sha(root / name) for name in ['src/baxy_mind/effect_intent.py',
        'src/baxy_mind/window_prose_facts.py', 'src/baxy_mind/llm.py', 'src/baxy_mind/__main__.py',
        'tests/test_c03_fresh_window_queries.py']},
    'python_tree_sha256': tree, 'python_files': len(files), 'owner_tests': owners,
    'design': 'The existing request-envelope grammar preserves delimited present-time frames. The existing immediate-user contextual-read branch, previously clock-only, also recognizes bounded nominal focus questions. Inherit only a prior independently resolved window.active read; no assistant prose, old state or past action grants authority. No new model call, new dispatcher, reply template, UI or backend change.',
    'baseline': {'failed': 36, 'passed': 16}, 'focal_passed': 52,
    'inheritance': '681 corrected679 scoring reveals t3/t5 native conversation decisions. Local probe: removing only the present-time preface restores window.active. Existing _REQUEST_PREFIX and clock contextual-read branch own these two lost distinctions. Application-window reference tests preserve their separate named-app scope.',
    'limits': 'Immediate user antecedent only; no claim of universal chained-reference understanding. Mixed lexical defect682 remains separate.',
    'next': 'Declared owners, current declarations, Fast, then identical seven-query product684. Require fresh observed window.active for every accepted turn; no credit from remembered titles.'}
(out / 'PREREG.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
state_path = base / 'RELEVO_ACTIVO.json'
state = json.loads(state_path.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='683 candidata:52nuevas pruebas,baseline36fallos16pases→52pases.680publicada;encuesta26/716/0 intacta.',
    continuation='Validar683 con dueñas/declaraciones/Fast y producto684 idéntico681. No adoptada aún. No cambiar prosa mixta ni responder desde historial.')
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print({'owner_files': len(owners), 'python_tree': tree, 'adopted': False})
