"""Draft-aware repair on changed requests, observed numbers and CPU labels."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-cpu-dialogue-repair578.py').read_text(encoding='utf-8')
source = source.replace('astra-cpu-dialogue-repair578', 'astra-cpu-repair-generalization580').replace('C03-cpu-dialogue-repair578-private', 'C03-cpu-repair-generalization580-private')
needle = "    cases.append({'id':ident,'case':folder+':'+str(ident),'payload':request['payload'],'draft':draft})"
assert needle in source
source = source.replace(needle, needle + '''
templates=copy.deepcopy(cases)
specs=[(0,'¿Qué porcentaje de CPU estoy usando?',7.25,6,8),
       (1,'How much CPU am I using right now?',64.5,10,16),
       (0,'cuánto procesador estoy ocupando en este momento',19.0,8,12),
       (2,'¿Qué procesador tengo y cuántos núcleos físicos son?',33.33,6,8),
       (3,'Which CPU do I have, and how many physical cores does it have?',27.0,10,14),
       (2,'¿Cuántos núcleos lógicos y físicos tiene mi equipo?',12.0,4,8)]
cases=[]
for index,(template,text,usage,physical,logical) in enumerate(specs):
    case=copy.deepcopy(templates[template]);case['case']='counterfactual-'+str(index)
    case['origin']='assistant-created synthetic development; changed request, measurements and model label, never observed hardware or human acceptance'
    def update(value):
        if isinstance(value,dict):
            if isinstance(value.get('cpu'),dict):
                value['cpu'].update(usagePercent=usage,physicalCoreCount=physical,logicalProcessorCount=logical,model='Example Processor R'+str(index))
            if 'completedRequest' in value:value['completedRequest']=text
            for child in value.values():update(child)
        elif isinstance(value,list):
            for child in value:update(child)
    lines=case['payload']['messages'][1]['content'].splitlines();lines[0]=text
    for i,line in enumerate(lines):
        if line.startswith('situation: '):
            facts=json.loads(line[11:]);update(facts);lines[i]='situation: '+json.dumps(facts,ensure_ascii=False)
    case['payload']['messages'][1]['content']='\\\\n'.join(lines)
    case.pop('draft');cases.append(case)
''')
source = source.replace("profiles=[('baseline',{'seed':0}),('draft-feedback',{'seed':0})]", "profiles=[('baseline',{'seed':0}),('draft-feedback',{'temperature':0.7,'top_p':0.8,'top_k':20,'min_p':0.0,'presence_penalty':0.0,'repeat_penalty':1.0,'seed':0})]")
source = source.replace('Four consumed actual writer captures: CPU usage ES failure/EN control, CPU model+core ES ownership failure575 and EN core control. Compare exact initial writer with a second dialogue turn carrying its actual captured draft plus explicit subject feedback. Preserve original facts, request, model and sampling. This tests draft-aware correction, not another stateless naming/instruction sweep.', 'Six explicitly synthetic development fixtures change question wording/ES/EN, measured CPU percentage, physical/logical ratio and processor label. Generate each initial draft with registered greedy first, then feed that actual draft into the unchanged feedback578 with documented sampling579 seed0. This is twelve native requests and no production-source change. Tests generalization and preservation; no human acceptance or observed-hardware claim.')
# This wrapper produces the complete runner; keep generation and its repair sequential.
source = source.replace("exec(compile(source, __file__, 'exec'))", "source = source.replace('order=profiles[case_index%2:]+profiles[:case_index%2]', 'order=profiles')\nsource = source.replace(\"append(private/'responses.jsonl',record)\", \"append(private/'responses.jsonl',record)\\n            if profile=='baseline':case['draft']=record['response']['choices'][0]['message']['content']\")\nexec(compile(source, __file__, 'exec'))")
source = source.replace('8 draft-repair comparisons collected', '12 counterfactual draft-repair requests collected')
exec(compile(source, __file__, 'exec'))
