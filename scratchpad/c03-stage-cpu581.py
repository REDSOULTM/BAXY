"""Record scoped CPU repair validation and refresh only current program attestations."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-cpu-actor581'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


for part in ('focal', 'owners', 'contracts', 'final-population-baseline'):
    (out / (part + '.log')).write_bytes((Path(os.environ['TEMP']) / f'c03-actor581-{part}.log').read_bytes())
files = {p.relative_to(root).as_posix(): p for folder in ('experiments/voice_latency', 'scripts', 'src/baxy_mind') for p in (root / folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest = hashlib.sha256()
for name in sorted(files):
    digest.update(name.encode() + b'\n' + sha(files[name]).encode() + b'\n')
tree = digest.hexdigest()
old = '9b75b8a888b69ddffdd90bd07d3acd3ea5fed2add9ef513fde1a57453ecfbeb7'
for relative in ('experiments/stt_quality/evaluate_reserved_stt.py', 'experiments/stt_quality/audit_fresh_postweight_stt_sources.py'):
    p = root / relative
    text = p.read_text(encoding='utf-8')
    assert text.count(old) == 1
    p.write_text(text.replace(old, tree).replace('# C03 576: current audio questions preserve coordinated reads and conditional scope.', '# C03 581: observed CPU claims retain their subject and numeric quantities.'), encoding='utf-8', newline='\n')
write(out / 'CURRENT_TREE.json', {'before': old, 'sha256': tree, 'files': len(files), 'historical_pins_unchanged': True})
write(out / 'PREREG.json', {'stage': 'After owner validation, before source Fast/STT/product582.', 'utc': datetime.now(timezone.utc).isoformat(), 'inheritance': '578 real-draft feedback fixes actors but greedy grammar fails;579 documented Qwen seed0 fixes four originals;580 three varied first-person failures corrected, already-correct ES control must not be repaired.', 'change': 'CPU-observation-scoped wrong_machine_actor guard; reuse existing retry/third slots with actual rejected draft and unchanged feedback, qualified Qwen2507 correction-only sampling. Correct first replies unchanged. Retry/third never receives contradictory First person instruction for this defect. Other models keep their sampling.', 'additional_blocker': 'A stub probe after adding actor detection showed the old fact guard accepted corrected subject with CPU99% although observed23.75. CPU-only numeric claims are now checked against observed usage (display-precision rounding) and physical/logical counts. Exclude mixed observations so an audio or other metric percentage is not misattributed to CPU. No claim of universal metric validation.', 'baseline': {'initial_population': 26, 'initial_failed': 20, 'initial_passed': 6, 'final_population': 39, 'final_failed': 25, 'final_passed': 14, 'final_seconds': .70, 'method': 'Saved exact pre581 llm source loaded in an isolated subprocess under its existing module/resource path; no working-tree overwrite, model or effects. Final tests against the same saved owner.', 'test_corrections': 'English actor tests use English requests. Existing exhaustion contract returns empty string, not ValueError; test now requires no publication and exactly3requests.'}, 'focal': {'passed': 39, 'seconds': .61}, 'owners': {'passed': 1993, 'subtests': 121, 'skipped': 0, 'seconds': 9.52}, 'compose_transport_contracts': {'passed': 156, 'skipped': 0, 'seconds': 1.27}, 'source_sha256': sha(root / 'src/baxy_mind/llm.py'), 'no_new_inference_slots': True})
print(json.dumps({'tree': tree, 'files': len(files)}))
