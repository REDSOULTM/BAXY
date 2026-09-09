"""Ablate the successful native-role representation304, correcting fixture separators."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import json
import urllib.request

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-account-frame305'
out.mkdir(exist_ok=False)
baseline=[row for row in json.loads((base/'astra-account-subject303/RESULT.json').read_text(encoding='utf-8')) if row['variant']=='before']
(out/'PREREG.json').write_text(json.dumps({
    'utc':datetime.now(timezone.utc).isoformat(),
    'method':'Component ablation of successful native-role304: compare original quoted-request framing, literal user request with existing inline facts, and native user/assistant/tool sequence. Four same controls, identical sampler/system/facts and limits; no product mutation. No new functions or operation effects.',
    'correction':'303 technical fixtures accidentally supplied a double backslash in qualifiedName, including the copied owner case.305 normalizes it to the actual Windows single separator in all variants. Preserve303/304 evidence as exact input delivered, do not label it an exact293 situation replay.',
    'criteria':'Attribute username to user/account, preserve literal observed value and no invented storage. Prefer the simplest demonstrated representation; if flat literal framing fails, do not assume native roles can be emulated by another header.'
},indent=2)+'\n',encoding='utf-8')
results=[]
for row in baseline:
    payload=copy.deepcopy(row['posts'][0]['payload'])
    body=payload['messages'][-1]['content']
    fact_line=next(line for line in body.splitlines() if line.startswith('situation: '))
    facts=json.loads(fact_line[len('situation: '):])
    facts['seen']['qualifiedName']=facts['seen']['domain']+chr(92)+facts['seen']['userName']
    fact_line='situation: '+json.dumps(facts,ensure_ascii=False)
    language='\n'.join(line for line in body.splitlines() if not line.startswith(('situation: ','Texto original de la persona: ')))
    for variant in ['quoted','literal','native_roles']:
        sent=copy.deepcopy(payload)
        if variant=='quoted':
            sent['messages'][-1]['content']='Texto original de la persona: '+row['request']+'\n'+fact_line+'\n'+language
        elif variant=='literal':
            sent['messages'][-1]['content']=row['request']+'\n'+fact_line+'\n'+language
        else:
            sent['messages']=[*sent['messages'][:-1],
                {'role':'user','content':row['request']+'\n'+language},
                {'role':'assistant','content':None,'tool_calls':[{'id':'observed_identity','type':'function',
                    'function':{'name':'system.identity','arguments':'{}'}}]},
                {'role':'tool','tool_call_id':'observed_identity','name':'system.identity','content':fact_line}]
        with urllib.request.urlopen('http://127.0.0.1:58916/slots',timeout=5) as response:
            assert not any(item['is_processing'] for item in json.load(response)), 'Backend/owner busy'
        req=urllib.request.Request('http://127.0.0.1:58916/v1/chat/completions',
            data=json.dumps(sent,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=90) as response:
            response=json.load(response)
        result={'request':row['request'],'variant':variant,'payload':sent,'response':response}
        results.append(result)
        (out/'RESULT.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'request':row['request'],'variant':variant,'reply':response['choices'][0]},ensure_ascii=True),flush=True)
