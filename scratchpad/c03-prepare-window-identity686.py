"""Pin the window identity/Boolean coverage candidate and inherited regression owners."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-window-identity-source686'
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
    old = b'6c474bfe4350dd0203b70a509a39d816feda4b0bf85a9a620e43512e6ae23ae5'
    assert data.count(old) == 1
    path.write_bytes(data.replace(old, tree.encode()))
owners = json.loads((base / 'astra-focus-subject-source680/PREREG.json').read_text(encoding='utf-8'))['owner_tests']
owners = sorted(set(owners + ['tests/test_c03_window_identity_answers.py', 'tests/test_c03_fresh_window_queries.py']))
logs = [('baseline', 'BASELINE_INITIAL'), ('expanded-baseline', 'BASELINE'),
        ('punctuation-before', 'PUNCTUATION_BEFORE'), ('focal', 'FOCAL')]
for suffix, name in logs:
    (out / (name + '.log')).write_bytes((Path(os.environ['TEMP']) / f'c03-window-identity686-{suffix}.log').read_bytes())
assert '50 failed, 21 passed' in (out / 'BASELINE.log').read_text(encoding='utf-8-sig')
assert '415 passed' in (out / 'FOCAL.log').read_text(encoding='utf-8-sig')
record = {'utc': datetime.now(timezone.utc).isoformat(), 'adopted': False,
    'parent_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
    'sources': {name: sha(root / name) for name in ['src/baxy_mind/window_prose_facts.py',
        'src/baxy_mind/effect_intent.py', 'src/baxy_mind/llm.py',
        'tests/test_c03_window_identity_answers.py', 'tests/test_c03_window_focus_coverage.py']},
    'python_tree_sha256': tree, 'python_files': len(files), 'owner_tests': owners,
    'design': 'Distinguish explicitly requested window identity from Boolean focus state. Bind nominal and postposed claims to unambiguous observed title/process aliases; quoted titles are opaque identifiers. Preserve typed contradictions, uncertainty and compound requested predicate coverage. No new model, visible reply template, dispatcher, UI or backend change.',
    'baseline': {'failed': 50, 'passed': 21}, 'focal_passed': 415,
    'inheritance': 'Product684 has seven fresh window.active observations but three valid identifying drafts rejected missing_fact. Source680 owns relative-clause scope; source676 owns requested focus completeness. Native685 prompt ablation was partial and not adopted.',
    'limits': 'Bounded existing factual grammar, not universal semantic verification. Intermediate quoted filename failures are preserved. One previous nameless WH-answer test now uses its proper Boolean question; new controls require a name for WH identity.',
    'next': 'Owners, current declarations and Fast, then exact seven-query product687 and exact17 compositor regression688. Do not infer survey coverage from unit tests.'}
(out / 'PREREG.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print({'owner_files': len(owners), 'python_tree': tree, 'adopted': False})
