"""Regress all original73 turns after window-name and startup catalog corrections."""
from pathlib import Path
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
record = json.loads((base/'astra-catalog-source712/CANDIDATE.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256((root/name).read_bytes()).hexdigest() == expected for name, expected in record['sources'].items())
gate = Path(os.environ['TEMP'])/'c03-catalog712-full5.log'
assert 'source_quality_gate_passed: mode=Full' in gate.read_text(encoding='utf-8-sig')
exit_record = json.loads((gate.parent/'c03-catalog712-full5-exit.json').read_text(encoding='utf-8-sig'))
assert exit_record['exit_code'] == 0
source = (root/'scratchpad/c03-status-batch694.py').read_text(encoding='utf-8').replace('694', '706')
source = source.replace('c03-shared-status693-full.log', 'c03-catalog712-full5.log')
source = source.replace('Full693 must pass before product evaluation', 'Full705+712 must pass before product evaluation')
source = source.replace('Shared source693: decimal measurement projection, independent installed RAM observation and wifi.status read-only policy.',
    'Candidate705+712: verified window title/process-name spans are opaque to vocabulary/code/capitalization checks only. Original prose and factual checks stay intact. Catalog discovery uses one Shell enumeration with measured entry parity. Source703 continuity, other providers, model and parameters stay unchanged.')
source = source.replace('No clearing pending state between turns.',
    'No conductor clearing of pending state between turns; the existing source703 product transition still owns confirmation continuity.')
source = source.replace('Shared candidate source693 product after Full693',
    'Candidate source705+712 product after Full5')
source = source.replace('Exact regression689 after shared quantities, installed RAM and wifi read policy changes;',
    'Exact regression689/694/702/704 after observed-name vocabulary and catalog startup corrections;')
source = source.replace("'src/baxy_mind/measurement_prose_projection.py',",
    "'src/Baxy.App/ObservedResponseLiterals.cs', 'src/Baxy.App/UserMessagePolicy.cs', 'src/Baxy.Providers.Windows/Applications/WindowsInstalledApplicationOpenProvider.cs', 'src/baxy_mind/observed_response_literals.py', 'src/baxy_mind/measurement_prose_projection.py',")
exec(compile(source, __file__, 'exec'))
