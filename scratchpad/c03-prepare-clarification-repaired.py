from pathlib import Path
import shutil

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
old='astra-clarification-continuation-qwen'
new='astra-clarification-repaired-qwen'
out=base/new
assert not out.exists()
(out/'profile').mkdir(parents=True)
shutil.copyfile(base/old/'profile/sitecustomize.py',out/'profile/sitecustomize.py')
shutil.copyfile(base/(old+'.turns.jsonl'),base/(new+'.turns.jsonl'))
s=(root/'scratchpad/c03-clarification-continuation.py').read_text(encoding='utf-8')
s=s.replace(old,new).replace('c03-clarification-continuation.py','c03-clarification-repaired.py')
s=s.replace('comprobaciones-c03-clarification-continuation-qwen','comprobaciones-c03-clarification-repaired-qwen')
s=s.replace(", BAXY_MIND_KV_CACHE_TYPE='q8_0'",'')
s=s.replace('explicit GGUF and q8 KV diagnostic overrides', 'explicit GGUF override only, current product KV default q8 (no KV override)')
(root/'scratchpad/c03-clarification-repaired.py').write_text(s,encoding='utf-8')
print('Prepared same12 with repaired transition/clarification and native q8 default.')
