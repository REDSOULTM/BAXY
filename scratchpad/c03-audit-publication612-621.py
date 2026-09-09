"""Verify all sealed tranche bytes, including the staged Git representation."""
from pathlib import Path
import ast
import hashlib
import json
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
names=['native-subject612','gemma-subject613','gemma-product614','social-kind615',
       'social-thinking616','native-schema617','style618','style-source619',
       'gemma-product620','conversation-regression621']
verified=0
for name in names:
    folder=base/('astra-'+name)
    pins=json.loads((folder/'PINS.json').read_text(encoding='utf-8'))
    for relative,expected in pins.items():
        path=folder/relative
        assert path.resolve().is_relative_to(folder.resolve())
        assert hashlib.sha256(path.read_bytes()).hexdigest()==expected,path
        if '--staged' in sys.argv:
            staged=subprocess.check_output(['git','show',':'+path.relative_to(root).as_posix()],cwd=root)
            assert hashlib.sha256(staged).hexdigest()==expected,('staged',path)
        verified+=1
for name in subprocess.check_output(['git','diff','--cached','--name-only','--diff-filter=AM'],cwd=root,text=True).splitlines():
    if name.startswith('scratchpad/') and name.endswith('.py'):
        ast.parse((root/name).read_text(encoding='utf-8-sig'),filename=name)
assert hashlib.sha256((root/'src/baxy_mind/llm.py').read_bytes()).hexdigest()=='d9ace8ac4adcf83af955276d1ed072b9a9ddff2fe85a26f2fa4511433dcc9425'
assert subprocess.check_output(['git','rev-parse','main'],cwd=root,text=True).strip()=='5f572ee1b48cb5e2543ee5e06510e51057c9c845'
print(json.dumps({'campaigns':len(names),'pins':verified,'staged':'--staged' in sys.argv,'main_untouched':True}))
