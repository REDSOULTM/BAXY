"""Same73 product inputs with the candidate shared actor recovery."""
from pathlib import Path
import hashlib
import json
import os

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
record=json.loads((base/'astra-machine-actor-source702/PREREG.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in record['sources'].items())
gate=Path(os.environ['TEMP'])/'c03-machine-actor702-fast.log'
assert 'source_quality_gate_passed: mode=Fast' in gate.read_text(encoding='utf-8-sig')
source=(root/'scratchpad/c03-status-batch694.py').read_text(encoding='utf-8').replace('694','702')
source=source.replace('Shared source693: decimal measurement projection, independent installed RAM observation and wifi.status read-only policy.',
    'Candidate702: extend the existing machine-subject recovery to typed network/WLAN observations, keeping the latest rejected draft and original facts. Source693 quantities and policies unchanged.')
source=source.replace('Shared candidate source693 product after Full693',
    'Candidate source702 product after Fast702 and79owner tests; inheritedFull693 is baseline only')
source=source.replace('Exact regression689 after shared quantities, installed RAM and wifi read policy changes;',
    'Exact regression689/694 after only machine-subject recovery;')
exec(compile(source,__file__,'exec'))
