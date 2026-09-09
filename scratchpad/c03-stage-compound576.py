"""Seal the diagnosed clause fix and update current Python program attestations."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-compound-mute576'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


for part in ('focal', 'owners'):
    (out / (part + '.log')).write_bytes((Path(os.environ['TEMP']) / f'c03-compound576-{part}.log').read_bytes())
assert '2651 passed, 121 subtests passed' in (out / 'owners.log').read_text(encoding='utf-8-sig')
files = {p.relative_to(root).as_posix(): p for folder in ('experiments/voice_latency', 'scripts', 'src/baxy_mind') for p in (root / folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest = hashlib.sha256()
for name in sorted(files):
    digest.update(name.encode() + b'\n' + sha(files[name]).encode() + b'\n')
tree = digest.hexdigest()
old = '564e880c9d37bf3c26965006e34c98288a8793d7c37313c59e34271cd595d0b6'
for relative in ('experiments/stt_quality/evaluate_reserved_stt.py', 'experiments/stt_quality/audit_fresh_postweight_stt_sources.py'):
    p = root / relative
    text = p.read_text(encoding='utf-8')
    assert text.count(old) == 1
    p.write_text(text.replace(old, tree).replace('# C03 571: composer instructions retain nested observed audio state.', '# C03 576: current audio questions preserve coordinated reads and conditional scope.'), encoding='utf-8', newline='\n')
write(out / 'CURRENT_TREE.json', {'before': old, 'sha256': tree, 'files': len(files), 'historical_pins_unchanged': True})
write(out / 'PREREG.json', {'stage': 'After diagnosed source edit and owner validation, before Fast/product577; original baseline saved before edits.', 'utc': datetime.now(timezone.utc).isoformat(), 'inheritance': '545 quantity-question boundaries;572 native4–17 Spanish interpretation failure,18 English audio-only. Direct trace before576: one clause both languages, ES unsupported_deferred_effect=True, EN strict_catalog returns audio.status alone. No native sampler changes can restore an omitted requested read.', 'change': 'Add copular/subordinate question boundaries and consume their punctuation. Reuse governing observation head for a complete indirect current audio question. Only its si/if marker ceases to be conditional; every other clause remains subject to deferred-action guards. Quoted note body after explicit content marker is data; preserve conditional actions and scheduling outside it.', 'criteria': 'Both requested reads must be available and ordered. No authority for conditional actions, past states, other devices or quoted payload. No template, observation or new operation. Generalize ES/EN, ordering, interrogative versus imperative and explicit versus inherited head.', 'baseline': {'test_population': 26, 'failed': 11, 'passed': 15, 'seconds': .75}, 'focal': {'test_population': 29, 'passed': 29, 'seconds': .64, 'added_controls': 'Three note timing/conditional-tail tests added after baseline; no claim baseline29 was run.'}, 'owners': {'passed': 2651, 'subtests': 121, 'skipped': 0, 'seconds': 52.54}, 'initial_owner_invocation': 'Wrong filename test_state_corpus.py: no tests ran, retained log. Corrected to test_effect_intent_state_corpus.py before owner result.', 'source_sha256': sha(root / 'src/baxy_mind/effect_intent.py')})
print(json.dumps({'tree': tree, 'files': len(files)}))
