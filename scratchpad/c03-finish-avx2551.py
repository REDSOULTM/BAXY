"""Complete only551 adjudication after its missing src import; do not rerun models."""
from pathlib import Path
import hashlib,json,os,sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-e5-avx2551-private'
previous=private.parent/'C03-e5-retrieval549-private'
out=root/'artifacts/comprobaciones/C03/astra-e5-avx2551'
resources=json.loads((out/'RESOURCES.json').read_text(encoding='utf-8'))
assert all(r['exit_code']==0 and not r['violations'] for r in resources.values())
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
source=(root/'scratchpad/c03-e5-avx2550.py').read_text(encoding='utf-8')
exec(compile(source[source.index('import numpy as np\nfrom baxy_mind.planner'):],__file__,'exec'))
