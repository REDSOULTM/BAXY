"""Original sidecar with timed thread diagnostics only; no monkeypatches."""
from pathlib import Path
import faulthandler
import os
import runpy
import json
import time

private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-sidecar162-private'
with (private/'stacks162.log').open('w',encoding='utf-8') as log:
    faulthandler.dump_traceback_later(15,repeat=True,file=log)
    try:
        started = time.monotonic()
        import scipy.signal
        (private/'preload.json').write_text(json.dumps({'seconds': time.monotonic()-started}), encoding='utf-8')
        runpy.run_module('baxy_mind',run_name='__main__')
    finally:
        faulthandler.cancel_dump_traceback_later()
