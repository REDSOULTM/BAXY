"""Keep the preliminary counterexample before correcting its semantics."""
from pathlib import Path
import hashlib
import os
import subprocess

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03/astra-window-projection667'
out.mkdir(exist_ok=False)
temp=Path(os.environ['TEMP'])
for source,target in [('c03-window-projection667-baseline.log','INITIAL_BASELINE.log'),('c03-window-projection667-focal.log','INITIAL_FOCAL.log')]:
    (out/target).write_bytes((temp/source).read_bytes())
(out/'INITIAL_SOURCE.patch').write_bytes(subprocess.check_output(['git','diff','--','src/baxy_mind/llm.py'],cwd=root))
(out/'INITIAL_TEST.py').write_bytes((root/'tests/test_c03_window_prose_projection.py').read_bytes())
print({'initial_source_sha256':hashlib.sha256((root/'src/baxy_mind/llm.py').read_bytes()).hexdigest(),'initial_variant':'in_front_of_other_windows','adopted':False})
