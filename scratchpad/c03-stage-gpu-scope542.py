"""Record the measured scope repair and refresh only current-tree declarations."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import subprocess

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03/astra-gpu-scope542'
out.mkdir(exist_ok=False)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
write(out/'PREREG.json',{
 'utc':datetime.now(timezone.utc).isoformat(),
 'stage':'Source repair following original product541 and failing owner test reproduction; registered after the test-first edit, not misrepresented as a before-run seal.',
 'finding':'English GPU plus dedicated video memory was read as GPU+system RAM; explicit scope abstained, native argument grounding failed, then a summary without adapters led to a fabricated integrated-only GPU answer. Qualified video-memory nouns must belong only to GPU. A separate RAM clause must remain separate.',
 'change':'One shared lexical definition for video/graphics/GPU memory in EN and memoria gráfica/de video/de la GPU in ES. Reuse for GPU evidence and exclude only those noun phrases from generic RAM recognition. No catalog expansion, new layer, model profile or fixed reply.',
 'validation_so_far':{'baseline':'8 failed,43 passed in0.82s: six qualified GPU variants and two mixed GPU/RAM controls fail before source edit.',
 'owners':'1917 passed in45.50s; test_system_status_scope_grounding.py, test_machine_status_scope.py, test_effect_intent.py'},
 'limits':'Fixes selection/argument grounding, not the independent GPU byte-to-VRAM prose error or all survey failures. Full not required for this Python-only source adoption; final Full remains mandatory.'})
for relative in ('src/baxy_mind/effect_intent.py','tests/test_system_status_scope_grounding.py'):
    result=subprocess.run(['git','show','HEAD:'+relative],cwd=root,capture_output=True,check=True)
    (out/(Path(relative).name+'.before')).write_bytes(result.stdout)
files={}
for directory in ('experiments/voice_latency','scripts','src/baxy_mind'):
    for path in (root/directory).rglob('*.py'):
        if path.is_file() and not path.is_symlink():files[path.relative_to(root).as_posix()]=path
digest=hashlib.sha256()
for relative in sorted(files):
    digest.update(relative.encode()+b'\n')
    digest.update(sha(files[relative]).encode()+b'\n')
tree_hash=digest.hexdigest()
for relative in ('experiments/stt_quality/evaluate_reserved_stt.py','experiments/stt_quality/audit_fresh_postweight_stt_sources.py'):
    path=root/relative
    text=path.read_text(encoding='utf-8')
    (out/(path.name+'.before')).write_text(text,encoding='utf-8')
    assert '0eb1d84ae1d32b71f265c00ada735565b62566071260d09233c6faebbf036194' in text
    text=text.replace('0eb1d84ae1d32b71f265c00ada735565b62566071260d09233c6faebbf036194',tree_hash,1)
    text=text.replace('# C03 531: current program tree after sources506/520/530 and revalidation\n# adapter recovery handling. Historical STT/wake campaign pins remain unchanged;\n# this declaration does not claim new audio acceptance.',
                      '# C03 542: current program tree distinguishes GPU video memory from RAM.\n# Historical STT/wake campaign pins remain unchanged; this declaration does\n# not claim new audio acceptance.')
    path.write_text(text,encoding='utf-8',newline='\n')
write(out/'CURRENT_TREE.json',{'sha256':tree_hash,'files':len(files),
      'before':'0eb1d84ae1d32b71f265c00ada735565b62566071260d09233c6faebbf036194',
      'historical_campaign_pins_unchanged':True})
print(json.dumps({'tree':tree_hash,'files':len(files)}))
