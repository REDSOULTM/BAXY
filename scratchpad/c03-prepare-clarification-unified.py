from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
old='astra-clarification-grounded-qwen';new='astra-clarification-unified-qwen'
out=base/new
assert not out.exists()
(out/'profile').mkdir(parents=True)
shutil.copyfile(base/old/'profile/sitecustomize.py',out/'profile/sitecustomize.py')
shutil.copyfile(base/(old+'.turns.jsonl'),base/(new+'.turns.jsonl'))
s=(root/'scratchpad/c03-clarification-grounded.py').read_text(encoding='utf-8')
s=s.replace(old,new).replace('c03-clarification-grounded.py','c03-clarification-unified.py')
s=s.replace('comprobaciones-c03-clarification-grounded-qwen','comprobaciones-c03-clarification-unified-qwen')
(root/'scratchpad/c03-clarification-unified.py').write_text(s,encoding='utf-8')
print('Prepared12 for unified pending-clarification handling across all3 sources.')
