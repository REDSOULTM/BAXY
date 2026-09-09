"""No output/volume changes; compare the capture owner on main and worker threads."""
from pathlib import Path
import json
import sys
import threading
import traceback

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind.voice_capture import WasapiCaptureStream
from baxy_mind.voice_aec import LoopbackReference

out = root / 'artifacts/comprobaciones/C03/astra-capture145'
out.mkdir(exist_ok=False)
rows = []

def probe(label):
    row = {'label': label}
    try:
        with WasapiCaptureStream(threading.Event()) as capture:
            for _ in range(10):
                capture.read(512)
            row.update(ok=True, adc=capture.adc_time, device=capture.device)
    except Exception as error:
        row.update(ok=False, error=repr(error), traceback=traceback.format_exc())
    rows.append(row)

reference = LoopbackReference()
assert reference.start(), reference.last_error
try:
    probe('main')
    thread = threading.Thread(target=probe, args=('worker',))
    thread.start()
    thread.join(10)
    assert not thread.is_alive()
finally:
    reference.stop()
(out / 'RESULTS.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
print(json.dumps(rows, indent=2))
