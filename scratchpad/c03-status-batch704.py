"""Run the original73 status turns after the shared confirmation-continuity fix."""
from pathlib import Path
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
record = json.loads((base / 'astra-continuity-source703/VALIDATED.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256((root / p).read_bytes()).hexdigest() == h for p, h in record['sources'].items())
gate = Path(os.environ['TEMP']) / 'c03-continuity703-fast.log'
assert 'source_quality_gate_passed: mode=Fast' in gate.read_text(encoding='utf-8-sig')
source = (root / 'scratchpad/c03-status-batch694.py').read_text(encoding='utf-8').replace('694', '704')
source = source.replace('Shared source693: decimal measurement projection, independent installed RAM observation and wifi.status read-only policy.',
    'Candidate703: distinguish an independent new request from a pending confirmation with one ordinary decision, retaining exact bindings and uncertain effects. Actor702 and all earlier providers and policies unchanged.')
source = source.replace('No clearing pending state between turns.', 'No conductor clearing of pending state between turns; only the declared product continuity transition may retire an unstarted confirmation.')
source = source.replace('Shared candidate source693 product after Full693',
    'Candidate source703 product after owner validation and Fast703; inheritedFull693 is baseline only')
source = source.replace('Exact regression689 after shared quantities, installed RAM and wifi read policy changes;',
    'Exact regression689/694/702 after only confirmation continuity;')
source = source.replace("'src/baxy_mind/measurement_prose_projection.py',", "'src/Baxy.App/MainWindowViewModel.cs', 'src/Baxy.App/MindPlanSession.cs', 'src/baxy_mind/measurement_prose_projection.py',")
exec(compile(source, __file__, 'exec'))
