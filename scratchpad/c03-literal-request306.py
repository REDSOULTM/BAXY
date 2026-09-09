"""Cross-route regression of literal user framing after native role ablation305."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import copy
import json
import sys
import urllib.request

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from baxy_mind import llm
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-literal-request306'
out.mkdir(exist_ok=False)
tree=ast.parse((root/'scratchpad/c03-account-subject303.py').read_text(encoding='utf-8'))
adapter=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='Runtime')
exec(compile(ast.Module(body=[adapter],type_ignores=[]),'<transport303>', 'exec'))
cases=[
    ('account','quien soy','status',{'kind':'operation','operation':'system.identity','polarity':'success','verified':True,'succeeded':True,'observed':{'domain':'REDNOTE','userName':'usuario','qualifiedName':'REDNOTE'+chr(92)+'usuario'}}),
    ('clock','¿Qué hora es?','status',{'kind':'operation','operation':'system.time','polarity':'success','verified':True,'succeeded':True,'observed':{'utc':'2026-09-08T01:20:00Z','localUtcOffsetMinutes':-180}}),
    ('volume','Set the volume to 50.','status',{'kind':'operation','operation':'audio.volume','polarity':'success','verified':True,'succeeded':True,'observed':{'level':50,'muted':False,'applied':True}}),
    ('error','Read the file "c03-invalid-utf8.txt" in the sandbox.','error',{'kind':'failure','polarity':'failure','cause':'invalid_utf8'}),
    ('clarify','Set the volume, please.','clarification',{'kind':'clarification','polarity':'pending','cause':'missing_arguments'}),
    ('confirm','Cierra la ventana con cambios sin guardar.','confirmation',{'kind':'confirmation','polarity':'pending','cause':'confirmation_required','pendingRequest':'Cierra la ventana con cambios sin guardar.','choices':['confirmar','cancelar']}),
    ('progress','Abre Steam.','status',{'kind':'status','polarity':'success','cause':'acting','phase':'understanding'}),
    ('welcome','','welcome',{'kind':'welcome','polarity':'success'}),
    ('conversation','Explícame la fotosíntesis.','conversation',{'kind':'conversation','polarity':'success'}),
]
prereg={'utc':datetime.now(timezone.utc).isoformat(),
    'hypothesis':'305 isolated the identity improvement to preserving a literal user request rather than quoting it under Texto original de la persona. Native tool framing is unnecessary for this result; remove the redundant label rather than introduce a new message architecture.',
    'method':'Actual compose API and guards, before/after _compose_user_content label removal only. Registered2507 backend unchanged. Nine technical regression fixtures across account/clock/volume/error/clarification/confirmation/progress/welcome/conversation. The account and UTF8 controls inherit existing development cases; other typed fixtures are technical, never fresh human acceptance. No real operations or storage.',
    'criteria':'Account correctly addressed to user; no lost facts/false successes/cause or consent regressions. Read all first and final outputs. Progress should preserve its omitted request. Failed existing controls remain pending; no claim that publishing makes them correct.',
    'sources':['https://qwen.readthedocs.io/en/stable/framework/function_call.html','astra-account-frame305/RESULT.json'],
    'cases':[{'id':key,'request':request,'intent':intent,'facts':{'situation':situation}} for key,request,intent,situation in cases]}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
original=llm._compose_user_content
def literal_request(*args,**kwargs):
    return original(*args,**kwargs).removeprefix('Texto original de la persona: ')
results=[]
try:
    for key,request,intent,situation in cases:
        for variant,serialize in [('before',original),('literal',literal_request)]:
            llm._compose_user_content=serialize
            runtime=Runtime()
            row={'id':key,'variant':variant,'request':request}
            try:
                row['answer']=runtime.compose_user_message(request,intent,{'situation':situation})
            except Exception as error:
                row['error']=repr(error)
            row['posts']=runtime.posts
            results.append(row)
            (out/'RESULT.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({k:v for k,v in row.items() if k!='posts'},ensure_ascii=True),flush=True)
finally:
    llm._compose_user_content=original
