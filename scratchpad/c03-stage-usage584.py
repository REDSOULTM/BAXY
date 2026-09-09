"""Record the actual uncovered ownership predicate and current-tree attestation."""
from pathlib import Path
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-usage-actor584'
out.mkdir(exist_ok=False)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


for stage in ('baseline', 'owners'):
    (out / (stage + '.log')).write_bytes((Path(os.environ['TEMP']) / f'c03-cpu584-{stage}.log').read_bytes())
files = {p.relative_to(root).as_posix(): p for folder in ('experiments/voice_latency', 'scripts', 'src/baxy_mind') for p in (root / folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest = hashlib.sha256()
for name in sorted(files):
    digest.update(name.encode() + b'\n' + sha(files[name]).encode() + b'\n')
tree = digest.hexdigest()
old = '7264631e11322195ec745c7ddceb9bba9e009c1336bd8d71f2faeb748ee8521a'
for relative in ('experiments/stt_quality/evaluate_reserved_stt.py', 'experiments/stt_quality/audit_fresh_postweight_stt_sources.py'):
    p = root / relative
    content = p.read_text(encoding='utf-8')
    assert content.count(old) == 1
    p.write_text(content.replace(old, tree).replace('# C03 581: observed CPU claims retain their subject and numeric quantities.', '# C03 584: possessive CPU usage claims enter the existing actor repair.'), encoding='utf-8', newline='\n')
write(out / 'CURRENT_TREE.json', {'before': old, 'sha256': tree, 'files': len(files), 'historical_pins_unchanged': True})
write(out / 'PREREG.json', {'cause': 'Actual product582 ordinal11 publishes Tengo un uso del50 por ciento de CPU. Existing guard catches Tengo un procesador but not possession of use/consumption.', 'change': 'Extend existing scoped actor predicate to tengo + optional article + uso/consumo + bounded same-sentence CPU reference. No new inference, prompt, model, visible phrase, or grammar claim. Existing repair carries the actually rejected draft.', 'controls': 'A reading of CPU use and a separate sentence saying Tengo el resultado remain valid. Three forms in direct and completed-mission observations; integration confirms actual draft and two requests.', 'baseline': {'failed': 6, 'passed': 48, 'seconds': 2.25, 'population': '54 tests before adding final integration case'}, 'owners': {'passed': 2165, 'subtests': 121, 'skipped': 0, 'seconds': 28.28}, 'timing_context': 'Owner tests ran while isolated583 inference was active; their speed and overlapping native timings are not clean performance benchmarks.', 'pending': 'Fast/STT and actual product verification; grammar failure remains open.'})
print(json.dumps({'sha256': tree, 'files': len(files)}))
