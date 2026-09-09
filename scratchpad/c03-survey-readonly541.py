"""First owner-authorized survey behaviors through the actual isolated product."""
from pathlib import Path
import json
import os

root=Path(__file__).resolve().parents[1]
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-survey-readonly541-private'
private.mkdir(exist_ok=False)
registry=private.parent/'C03-survey-requirements336-private/requirements.jsonl'
with registry.open(encoding='utf-8-sig') as handle:
    requirements={r['case_id']:r for r in map(json.loads,handle)}
groups={
 'H0002':['¿Cuál es la capital de Italia?','What is the capital of Peru?'],
 'H0003':['Cuéntame un dato curioso sobre los océanos.','Tell me an interesting fact about the Moon.'],
 'H0007':['What CPU model and number of cores does this computer have?'],
 'H0012':['Oye, ¿quién eres tú?'],
 'H0016':['¿Quién fue Isaac Newton?','Who was Marie Curie?'],
 'H0021':['What is your name?'],
 'H0025':['¿Cuánto espacio libre queda en los discos?'],
 'H0026':['What GPU is installed, and how much dedicated video memory does it have?'],
 'H0037':['Is the battery charging right now?'],
 'H0040':['Is Spotify open?'],
 'H0041':['¿Cuánto es la raíz cuadrada de 225?','What is the square root of 81?'],
 'H0042':['Buenos días, BAXY.'],
 'H0062':['Thanks for your help.'],
 'H0063':['How much battery charge is left?'],
 'H0065':['How much CPU is being used right now?'],
 'H0073':['What is the current volume level?'],
 'H0078':['Eso era todo, gracias.'],
 'H0079':['How much battery is left, and what time is it?'],
 'H0080':['Am I connected to the internet?'],
 'H0087':['¿Qué tarjeta gráfica está instalada en este equipo?'],
}
panel=[]
for case_id,variants in groups.items():
    row=requirements[case_id]
    assert row['expected_capability'] is True
    panel.append({'case_id':case_id,'origin':'owner-reviewed historical literal',
                  'text':row['literal'],'note':row['owner_review']['note'],
                  'source_id':row['source_id']})
    for variant in variants:
        panel.append({'case_id':case_id,'origin':'assistant-authored generalization variant',
                      'text':variant})
(private/'panel.json').write_text(json.dumps(panel,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
hook=root/'scratchpad/c03-owner541-hook'
hook.mkdir(exist_ok=False)
hook_text=(root/'scratchpad/c03-owner521-hook/sitecustomize.py').read_text(encoding='utf-8')
(hook/'sitecustomize.py').write_text(hook_text.replace('C03-private-product521-private','C03-survey-readonly541-private'),encoding='utf-8')
source=(root/'scratchpad/c03-private-product521.py').read_text(encoding='utf-8')
source=source.replace('astra-private-product521','astra-survey-readonly541')
source=source.replace('C03-private-product521-private','C03-survey-readonly541-private')
source=source.replace('C03-private-profile521','C03-survey-profile541')
source=source.replace('c03-owner521-hook','c03-owner541-hook')
start=source.index('cases = ')
end=source.index('\n\ncommands =',start)
source=source[:start]+"cases = [row['text'] for row in json.loads((private/'panel.json').read_text(encoding='utf-8'))]"+source[end:]
start=source.index('prereg = {')
end=source.index("(out/'PREREG.json').write_text",start)
source=source[:start]+'''prereg={
 'utc':datetime.now(timezone.utc).isoformat(),
 'method':'Actual registered Qwen2507/b9980 product, isolated fresh profile, exact20 owner-reviewed survey messages plus24 new variants. Only knowledge, identity/social and read-only PC requests. No outgoing messages, filesystem mutation, app closing, audio mutation or owner profile changes. Full shared Core/mind/conductor; not desktop UI or voice proof.',
 'authorization':'AUTORIZACION_DUENO_536.md allows historical and new evaluation. Provenance is explicit per case; not a blind holdout. Contextual original sources are not claimed to be reconstructed: these selected standalone requests are exercised in the displayed test-session order.',
 'criteria':'Review each final and typed operation/observation. Knowledge facts and arithmetic must be correct; identity BAXY; social replies direct and natural. PC answers must agree with actual returned observations including units, availability, failed reads and composite battery/time completeness. No unrequested effects. A variant success alone does not cover the owner case. Record per-case evidence; no automatic covered marking or arbitrary threshold.',
 'manifest_sha256':sha(manifest),'panel_sha256':sha(private/'panel.json'),
 'survey_registry_sha256':sha(private.parent/'C03-survey-requirements336-private/requirements.jsonl'),
 'source_sha256':{name:sha(root/name) for name in ['src/baxy_mind/__main__.py','src/baxy_mind/llm.py','src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.dll']},
 'private':str(private),'case_count':len(cases),
 'resource_limits':{'gpu_stop_mib':3800,'minimum_free_ram_mib':768,'wall_time_seconds':600},
 'excluded_adoptions':'537–540 failed diagnostics are not installed; current source120713be remains unchanged.'}
''' +source[end:]
source=source.replace('time.monotonic()-started>240','time.monotonic()-started>600')
exec(compile(source,__file__,'exec'))
