"""Pin the bounded writer change without altering consumed evidence."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
out = base/'astra-window-scope-source652'
assert not (out/'SOURCE.json').exists()
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
files = {p.relative_to(root).as_posix(): p for folder in ['experiments/voice_latency', 'scripts', 'src/baxy_mind']
         for p in (root/folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest = hashlib.sha256()
for name in sorted(files):
    digest.update(name.encode()+b'\n'+sha(files[name]).encode()+b'\n')
tree = digest.hexdigest()
for name in ['audit_fresh_postweight_stt_sources.py', 'evaluate_reserved_stt.py']:
    path = root/'experiments/stt_quality'/name
    data = path.read_bytes()
    old = b'749fa59fcb7b40ee3e94f3eaddfe2cea5b6d4f724da3625876569c855918a534'
    assert data.count(old) == 1
    path.write_bytes(data.replace(old, tree.encode()))
path = root/'tests/test_price_v8_veto_damage_by_cause.py'
data = path.read_bytes()
old = b'464603566c9dc66204cc75e45a79c8058063d0bb06fe6ff554bf56529e5ea73e'
assert data.count(old) == 1
path.write_bytes(data.replace(old, sha(root/'src/baxy_mind/llm.py').encode()))
write(out/'SOURCE.json', {'utc': datetime.now(timezone.utc).isoformat(), 'source': 652,
    'llm_sha256': sha(root/'src/baxy_mind/llm.py'), 'python_tree_sha256': tree,
    'parity': json.loads((out/'PARITY.json').read_text(encoding='utf-8'))['compared'],
    'source_adopted': False, 'full_baseline': 651,
    'current_declarations': {p: sha(root/p) for p in ['tests/test_price_v8_veto_damage_by_cause.py',
        'experiments/stt_quality/audit_fresh_postweight_stt_sources.py', 'experiments/stt_quality/evaluate_reserved_stt.py']}})
print({'source': 652, 'llm_sha256': sha(root/'src/baxy_mind/llm.py'), 'python_tree_sha256': tree})
