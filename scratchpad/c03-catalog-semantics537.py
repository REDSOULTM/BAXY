"""Bounded native ablation of canonical operation descriptions; inherits 523 guard."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-native-compose-profile523.py').read_text(encoding='utf-8')
source = source.replace('astra-native-compose-profile523', 'astra-catalog-semantics537')
source = source.replace('C03-native-compose-profile523-private', 'C03-catalog-semantics537-private')
source = source.replace("ids={1:", "ids={7:'stored-name-en',11:'stored-name-es',1:")
source = source.replace('len(cases)==9', 'len(cases)==11')
start = source.index('profiles=')
end = source.index("write(private/'cases.json',cases)", start)
source = source[:start] + '''import re
catalog_path=root/'src/Baxy.Kernel/Operations/ProductCatalog.cs'
catalog=catalog_path.read_text(encoding='utf-8-sig')
descriptions={}
for descriptor in catalog.split('Descriptor(')[1:]:
    name=re.match(r'\\s*"([^"]+)"',descriptor)
    description=re.search(r'ToolExposure\\.[A-Za-z]+,\\s*"([^"\\n]+)"',descriptor)
    if name and description:descriptions[name.group(1)]=description.group(1)
profiles=[('baseline',{'seed':0}),('catalog-description',{'seed':0})]
def treatment(payload):
    changed=[]
    for message in payload['messages']:
        lines=message['content'].splitlines()
        for i,line in enumerate(lines):
            if line.startswith('situation: '):
                facts=json.loads(line[len('situation: '):])
                operation=facts.get('operation')
                if operation in descriptions:
                    facts['operationDescription']=descriptions[operation]
                    lines[i]='situation: '+json.dumps(facts,ensure_ascii=False)
                    changed.append(operation)
        message['content']='\\n'.join(lines)
    return changed
write(out/'PREREG.json',{
 'utc':datetime.now(timezone.utc).isoformat(),
 'method':'Eleven exact native captures521, two arms. Sole treatment: append operationDescription from canonical ProductCatalog for the already supplied operation. Keep original request, all facts, prompts, sampling, backend and model. No inference of operation from request, no capability invented from enabled:false. This is a semantic-grounding diagnostic, not the rejected metadata filtering515, sampler523, larger-model524 or question removal525.',
 'criteria':'Repair disabled-capability denial and internal save receipt without losing cause, pending confirmation, recall subject/value, disable state, clock, language or adding unverified effects. Review every literal. A native improvement requires whole-product validation before source adoption.',
 'authorization':'AUTORIZACION_DUENO_536.md permits historical and survey reuse; these are consumed synthetic development captures, never a blind holdout.',
 'catalog_sha256':sha(catalog_path),'manifest_sha256':manifest_sha,
 'capture_sha256':sha(previous/'http-posts.jsonl'),'server_command':command,
 'profiles':profiles,'cases':[{'id':c['id'],'case':c['case']} for c in cases],
 'limits':{'gpu_stop_mib':3800,'free_ram_mib':768,'total_seconds':360,'request_seconds':60},
 'inheritance':'523 fixed-model sampling failed; retain registered greedy to isolate data semantics. No model ranking or joint UI/audio resource claim.'})
''' + source[end:]
source = source.replace('case_index%3', 'case_index%2')
source = source.replace("payload=copy.deepcopy(case['payload']);payload.update(settings)", "payload=copy.deepcopy(case['payload']);payload.update(settings)\n            if profile=='catalog-description':treatment(payload)")
source = source.replace('27 native writer requests collected', '22 native writer requests collected')
exec(compile(source, __file__, 'exec'))
