"""One descriptor-only correction to internal zero-effect classification."""
from pathlib import Path
from datetime import datetime,timezone
import copy
import json
import time
import urllib.request

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03/astra-zero291'
out.mkdir(exist_ok=False)
rows=[]
for folder in ['astra-abstain289','astra-abstain290']:
    rows += [row for row in json.loads((root/f'artifacts/comprobaciones/C03/{folder}/RESULT.json').read_text(encoding='utf-8')) if row['variant']=='explicit_no_effect']
description='Internal classification outcome only: the entire current request requires zero computer actions and zero external reads. Select this alone only if no requested effect remains. Otherwise select the functions for the remaining requested effects. This grants no operation authority and does not answer the person.'
prereg={'utc':datetime.now(timezone.utc).isoformat(),
    'hypothesis':'The prior descriptor lists negated requests without scoping no-effect to the entire request; scope3 loses an allowed clock clause and scope7 wrongly executes quoted translation content. Replace only that descriptor with a whole-request zero-effect predicate.',
    'method':'All18 controls289/290. Identical payload except the no_effect_decision description. Same backend, settings, functions/order and required selector. No source edit or effects. No further descriptor sweep if this fails.',
    'criteria':'Recover scope3 and scope7 with no loss of prior correct controls; preserve finished Paris abstention. Existing app05/compound failures remain visible, no acceptance.',
    'description':description,'cases':[row['case_id'] for row in rows]}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
results=[]
for row in rows:
    payload=copy.deepcopy(row['payload'])
    tool=next(tool for tool in payload['tools'] if tool['function']['name']=='baxy_no_effect_decision')
    tool['function']['description']=description
    with urllib.request.urlopen('http://127.0.0.1:58635/slots',timeout=5) as response:
        assert not any(item['is_processing'] for item in json.load(response))
    req=urllib.request.Request('http://127.0.0.1:58635/v1/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
    started=time.monotonic()
    with urllib.request.urlopen(req,timeout=90) as response:
        response=json.load(response)
    choice=response['choices'][0]
    names=[call['function']['name'] for call in choice['message'].get('tool_calls') or []]
    operations=[name.removeprefix('baxy_').replace('__','.') for name in names if name!='baxy_no_effect_decision']
    result={'case_id':row['case_id'],'expected':row['expected'],'names':names,'operations':operations,'finish':choice['finish_reason'],'seconds':round(time.monotonic()-started,3),'payload':payload,'response':response}
    results.append(result)
    (out/'RESULT.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('payload','response')},ensure_ascii=True),flush=True)
