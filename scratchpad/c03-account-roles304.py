"""Native transport-only comparison: preserve user/tool message roles."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import json
import urllib.request

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-account-roles304'
out.mkdir(exist_ok=False)
rows=json.loads((base/'astra-account-subject303/RESULT.json').read_text(encoding='utf-8'))
rows=[row for row in rows if row['variant']=='before']
prereg={'utc':datetime.now(timezone.utc).isoformat(),
    'hypothesis':'Preserve literal user query as a user turn and supplied account observation as tool output, rather than a quoted request and facts in one user message. This tests speaker binding with the native chat template.',
    'method':'First-completion-only transport comparison against exact baseline303 payloads; same system prompt/facts/language contract/sampling/limits. Previously supplied observation represented by assistant tool call and tool result; zero execution and no newly available functions. Technical fixtures are replay data, not live observations or acceptance. No production source edit.',
    'criteria':'Correct speaker/account attribution for four same ES/EN/name controls. Record all finish reasons, tool outputs and literal replies; native evidence only, no claim of integrated repair.',
    'sources':['https://qwen.readthedocs.io/en/stable/framework/function_call.html',
        'artifacts/comprobaciones/C03/INVESTIGACION_MODELO_C03.md'],
    'preceding':'Subject annotation303 did not repair Spanish quien soy; no adoption. Change representation instead of another annotation or phrase blacklist.'}
(out/'PREREG.json').write_text(json.dumps(prereg,indent=2)+'\n',encoding='utf-8')
results=[]
for row in rows:
    original=row['posts'][0]['payload']
    payload=copy.deepcopy(original)
    body=payload['messages'][-1]['content']
    fact_line=next(line for line in body.splitlines() if line.startswith('situation: '))
    language='\n'.join(line for line in body.splitlines() if line!=fact_line and not line.startswith('Texto original de la persona: '))
    payload['messages']=[*payload['messages'][:-1],
        {'role':'user','content':row['request']+'\n'+language},
        {'role':'assistant','content':None,'tool_calls':[{'id':'observed_identity','type':'function',
            'function':{'name':'system.identity','arguments':'{}'}}]},
        {'role':'tool','tool_call_id':'observed_identity','name':'system.identity','content':fact_line}]
    with urllib.request.urlopen('http://127.0.0.1:58916/slots',timeout=5) as response:
        assert not any(item['is_processing'] for item in json.load(response)), 'Backend/owner busy'
    req=urllib.request.Request('http://127.0.0.1:58916/v1/chat/completions',
        data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
    result={'request':row['request'],'before':row['posts'][0]['response']['choices'][0], 'payload':payload}
    try:
        with urllib.request.urlopen(req,timeout=90) as response:
            result['response']=json.load(response)
    except Exception as error:
        result['error']=repr(error)
    results.append(result)
    (out/'RESULT.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'request':row['request'],'result':result.get('response',{}).get('choices',result.get('error'))},ensure_ascii=True),flush=True)
