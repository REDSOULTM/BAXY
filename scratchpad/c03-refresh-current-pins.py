from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
files = {}
for relative in ('experiments/voice_latency', 'scripts', 'src/baxy_mind'):
    for path in (root / relative).rglob('*.py'):
        if path.is_file() and not path.is_symlink():
            files[path.relative_to(root).as_posix()] = path
digest = hashlib.sha256()
for relative, path in sorted(files.items()):
    digest.update((relative + '\n' + sha(path) + '\n').encode())
tree = digest.hexdigest()
old_tree = 'c40f25c69199f341afbf606796d4f5ec6f630bfa20c0e41d4f64649d7d4d244e'
old_llm = '03d23cbf7ca2af7d05f88dcd42db6ae4bf2d329025769bf244fd1a7fb814d088'
llm = sha(root / 'src/baxy_mind/llm.py')
for relative in ('experiments/stt_quality/evaluate_reserved_stt.py',
                 'experiments/stt_quality/audit_fresh_postweight_stt_sources.py',
                 'tests/test_price_v8_veto_damage_by_cause.py',
                 'artifacts/comprobaciones/C03/CHECKPOINT.md'):
    path = root / relative
    text = path.read_text(encoding='utf-8')
    path.write_text(text.replace(old_tree, tree).replace(old_llm, llm), encoding='utf-8')
print(json.dumps({'llm': llm, 'tree': tree,
                  'effect_intent': sha(root/'src/baxy_mind/effect_intent.py')}))
