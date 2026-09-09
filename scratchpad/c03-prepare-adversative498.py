"""Freeze the positive adversative defect before touching product source."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-positive-adversative498'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-positive-adversative498-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
source = root / 'src/baxy_mind/effect_intent.py'
tests = root / 'tests/test_effect_intent.py'
shutil.copy2(source, private / 'effect_intent-before.py')
shutil.copy2(tests, private / 'test_effect_intent-preregistered.py')
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
registration = {
    'utc': datetime.now(timezone.utc).isoformat(),
    'hypothesis': 'An explicit second action after pero/but is lost by the clause separator, independently of the model.',
    'source_before_sha256': sha(source),
    'tests_preregistered_sha256': sha(tests),
    'cases': 'Nine synthetic development cases in test_positive_adversative*: six positive ordered pairs, two quoted-content controls, one unavailable operation.',
    'intervention': 'Add pero/but as a positive separator only when the existing explicit action head follows; preserve independent negative and genuine correction guards.',
    'validation': 'Record new focal baseline first. Then new focal plus sixteen existing487 tests; five owner suites and Fast gate after green. No Full during repair.',
    'limits': 'Does not reconstruct the antecedent for owner264 turn51, execute effects, qualify a runtime, or use the fresh human reserve.'
}
(out / 'PREREG.json').write_text(json.dumps(registration, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'out': str(out), 'source_before_sha256': sha(source)}))
