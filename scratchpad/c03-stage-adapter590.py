"""Checkpoint integrated adapter source before its mandatory cross-language Full."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-cpu-adapter590'
out.mkdir(exist_ok=False)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


for name in ('focal', 'registration', 'dotnet', 'owners', 'focal-final'):
    (out / (name + '.log')).write_bytes((Path(os.environ['TEMP']) / f'c03-adapter590-{name}.log').read_bytes())
files = {p.relative_to(root).as_posix(): p for folder in ('experiments/voice_latency', 'scripts', 'src/baxy_mind') for p in (root / folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest = hashlib.sha256()
for name in sorted(files):
    digest.update(name.encode() + b'\n' + sha(files[name]).encode() + b'\n')
tree = digest.hexdigest()
old = '6ca99187a3a2f97e5ba3736c5b61e2bae9710f97ed44441f8a4819f7bbeadb7d'
for relative in ('experiments/stt_quality/evaluate_reserved_stt.py', 'experiments/stt_quality/audit_fresh_postweight_stt_sources.py'):
    p = root / relative
    text = p.read_text(encoding='utf-8')
    assert text.count(old) == 1
    p.write_text(text.replace(old, tree).replace('# C03 584: possessive CPU usage claims enter the existing actor repair.', '# C03 590: registered CPU prose adapter is isolated from other model roles.'), encoding='utf-8', newline='\n')
write(out / 'CURRENT_TREE.json', {'before': old, 'sha256': tree, 'files': len(files), 'historical_pins_unchanged': True})
write(out / 'PREREG.json', {'utc': datetime.now(timezone.utc).isoformat(), 'cause': '587 base still breaks Spanish after actor repair.586/588 role-scoped inherited adapter succeeds across seeds/changed values/missions;58917 actual finals correct with experimental override.', 'source': 'Separate CPU adapter asset/profile owner; explicit zero on other POSTs, scoped CPU sampling at payload construction, no context/thread-local mutation in product. Startup verifies loaded adapter and resets/reads global0 before readiness; mismatches fail immediately outside the health retry catch. Hash-bound artifact and base. Optional closed registration in C#, Python tooling and PowerShell setup; explicit other-model overrides do not inherit adapter. Shared benchmark launchers export the profile consistently.', 'baseline_product': '587, unchanged prompts/facts versus589 experimental selection; no claim new unit tests existed before new owner module.', 'owners': {'python': 2240, 'subtests': 121, 'skips': 0}, 'final_new_tests': {'passed': 32, 'seconds': 8.96}, 'dotnet_discovery': {'passed': 29, 'skips': 0, 'seconds': .619}, 'pending': 'Mandatory Full because C#+Python shared registration, source review, actual source-built product without hook, joint memory/UI/voice, registration/promotion. No default manifest changed.'})
print(json.dumps({'sha256': tree, 'files': len(files)}))
