"""Original sidecar with timed thread diagnostics only; no monkeypatches."""
from pathlib import Path
import faulthandler
import os
import runpy

private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-sidecar165-private'
with (private/'stacks165.log').open('w',encoding='utf-8') as log:
    faulthandler.dump_traceback_later(15,repeat=True,file=log)
    try:
        runpy.run_module('baxy_mind',run_name='__main__')
    finally:
        faulthandler.cancel_dump_traceback_later()
