from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
old='astra-clarification-repaired-qwen';new='astra-clarification-grounded-qwen'
out=base/new
assert not out.exists()
(out/'profile').mkdir(parents=True)
shutil.copyfile(base/old/'profile/sitecustomize.py',out/'profile/sitecustomize.py')
shutil.copyfile(base/(old+'.turns.jsonl'),base/(new+'.turns.jsonl'))
s=(root/'scratchpad/c03-clarification-repaired.py').read_text(encoding='utf-8')
s=s.replace(old,new).replace('c03-clarification-repaired.py','c03-clarification-grounded.py')
s=s.replace('comprobaciones-c03-clarification-repaired-qwen','comprobaciones-c03-clarification-grounded-qwen')
(root/'scratchpad/c03-clarification-grounded.py').write_text(s,encoding='utf-8')
print('Prepared same12 after punctuation/domain repair; no other source change.')
