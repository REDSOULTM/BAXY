from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
old = 'astra-clarification-error-qwen'
new = 'astra-boundary-product-qwen'
out = base/new
assert not out.exists()
(out/'profile').mkdir(parents=True)
shutil.copyfile(base/old/'profile/sitecustomize.py', out/'profile/sitecustomize.py')
shutil.copyfile(base/(old+'.turns.jsonl'), base/(new+'.turns.jsonl'))
s = (root/'scratchpad/c03-clarification-error-qwen.py').read_text(encoding='utf-8')
s = s.replace(old, new).replace('c03-clarification-error-qwen.py','c03-boundary-product.py')
s = s.replace('comprobaciones-c03-clarification-error-qwen','comprobaciones-c03-boundary-product-qwen')
(root/'scratchpad/c03-boundary-product.py').write_text(s, encoding='utf-8')
print('Prepared same 12 turns, fresh profile, existing typed error composer route.')
