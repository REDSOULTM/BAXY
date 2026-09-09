from pathlib import Path
import ast
import copy
import json
import sys
import urllib.request

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from baxy_mind import llm
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-request-speaker307'
tree=ast.parse((root/'scratchpad/c03-account-subject303.py').read_text(encoding='utf-8'))
adapter=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='Runtime')
exec(compile(ast.Module(body=[adapter],type_ignores=[]),'<transport303>', 'exec'))
cases=json.loads((base/'astra-literal-request306/PREREG.json').read_text(encoding='utf-8'))['cases']
previous=json.loads((base/'astra-literal-request306/RESULT.json').read_text(encoding='utf-8'))
results=[]
for case in cases:
    if case['id'] not in {'account','error'}:
        continue
    runtime=Runtime()
    row={'id':case['id'],'request':case['request']}
    row['answer']=runtime.compose_user_message(case['request'],case['intent'],case['facts'])
    row['posts']=runtime.posts
    prior=next(item for item in previous if item['id']==case['id'] and item['variant']=='literal')
    row['first_payload_equal306']=row['posts'][0]['payload']==prior['posts'][0]['payload']
    assert row['first_payload_equal306']
    results.append(row)
    print(json.dumps({key:value for key,value in row.items() if key!='posts'},ensure_ascii=True),flush=True)
(out/'NATIVE_RESULT.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
