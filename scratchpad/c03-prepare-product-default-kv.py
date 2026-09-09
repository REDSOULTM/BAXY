from pathlib import Path
import shutil

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
old='astra-presentation-product-qwen'
new='astra-product-default-kv-qwen'
out=base/new
assert not out.exists()
(out/'profile').mkdir(parents=True)
shutil.copyfile(base/old/'profile/sitecustomize.py',out/'profile/sitecustomize.py')
shutil.copyfile(base/(old+'.turns.jsonl'),base/(new+'.turns.jsonl'))
s=(root/'scratchpad/c03-presentation-product-qwen.py').read_text(encoding='utf-8')
s=s.replace(old,new).replace('c03-presentation-product-qwen.py','c03-product-default-kv.py')
s=s.replace('comprobaciones-c03-presentation-product-qwen','comprobaciones-c03-product-default-kv-qwen')
s=s.replace(", BAXY_MIND_KV_CACHE_TYPE='q8_0'",'')
s=s.replace('GGUF override and q8 KV are explicit diagnostic settings.', 'Only the GGUF is overridden; KV uses the existing product default q4_0, no KV override. Compare with the consumed q8 diagnostic before deciding whether a cache-profile change is needed.')
(root/'scratchpad/c03-product-default-kv.py').write_text(s,encoding='utf-8')
print('Prepared21 with existing product KV default, not executed.')
