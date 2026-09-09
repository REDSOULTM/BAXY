"""Qualify inherited LoRA only for CPU prose, with untouched-role controls."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-native-compose-profile523.py').read_text(encoding='utf-8')
source = source.replace('astra-native-compose-profile523', 'astra-scoped-lora586').replace('C03-native-compose-profile523-private', 'C03-scoped-lora586-private')
start = source.index('ids='); end = source.index('manifest=Path(', start)
source = source[:start] + '''
capture=private.parent/'C03-tool-result-envelope585-private/cases.json'
cases=json.loads(capture.read_text(encoding='utf-8-sig'))
assert len(cases)==8
for case in cases:case['cpu_scope']=True
templates={case['id']:case for case in cases}
for i,(ident,text,usage,physical,logical) in enumerate([
    (10,'¿Cuánta CPU estoy consumiendo ahora?',7.25,6,8),
    (12,'How much processing power am I using?',64.5,10,16),
    (20,'Dime qué uso del procesador tengo ahora.',33.33,4,8),
    (23,'What percentage of my CPU is being used?',19.0,8,12),
]):
    case=copy.deepcopy(templates[ident]);case['case']='synthetic-'+str(i)
    case['origin']='Assistant-created development fixture, not observed hardware or human acceptance'
    lines=case['payload']['messages'][1]['content'].splitlines();lines[0]=text
    for j,line in enumerate(lines):
        if line.startswith('situation: '):
            facts=json.loads(line[11:]);facts['seen']['cpu'].update(usagePercent=usage,physicalCoreCount=physical,logicalProcessorCount=logical,model='Example Processor P'+str(i))
            lines[j]='situation: '+json.dumps(facts,ensure_ascii=False)
    case['payload']['messages'][1]['content']='\\n'.join(lines)
    cases.append(case)
controls=json.loads((private.parent/'C03-inherited-lora561-private/cases.json').read_text(encoding='utf-8-sig'))
for case in controls:
    if case['case'] in ('enable-confirmation','stored-name-en','stored-name-es'):
        case['cpu_scope']=False;cases.append(case)
assert len(cases)==15
''' + source[end:]
start = source.index('profiles='); end = source.index("write(private/'cases.json',cases)", start)
source = source[:start] + '''
adapter=Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-training-cdbee75f/c03-pilot-lora-v4-f32.gguf')
assert sha(adapter)=='e28d7728c915861a798b005c22e7b9148fdce729e4a402ac5d502abdbeaccce5'
command += ['--lora',str(adapter),'--lora-init-without-apply']
documented={'temperature':.7,'top_p':.8,'top_k':20,'min_p':0.,'presence_penalty':0.,'repeat_penalty':1.,'seed':0,'cache_prompt':False}
profiles=[('registered-base',{'seed':0,'cache_prompt':False,'lora':[{'id':0,'scale':0.}]}),
          ('documented-base',{**documented,'lora':[{'id':0,'scale':0.}]}),
          ('scoped-pilot4',{**documented,'lora':[{'id':0,'scale':1.}]})]
write(out/'PREREG.json',{'method':'Eight exact recent CPU writer inputs582, four new synthetic CPU fixtures varying request, values, core ratios and processor label; three inherited name/confirmation controls following CPU requests. Registered base, documented sampling base, identical sampling plus inherited pilot4 only on CPU inputs. Other-role controls keep their original registered sampling and explicit LoRA0 for every profile. No new training or instructions, no tool-role envelope585. Adapter default verified0 by GET/POST/GET before any request, explicit scale per request and no cache reuse.',
 'inheritance':'561 fixed CPU ownership but global LoRA broke names and memory capability. Test bounded role application on twelve CPU cases, including new real failures582 and changed values, while preserving three non-CPU controls.583 finite reasoning exposed deliberation/false count/truncation;585 native tool envelope did not fix four actors, neither adopted.',
 'sources':['artifacts/comprobaciones/C03/astra-inherited-lora561/RESULT.md','artifacts/comprobaciones/C03/astra-lora-pilot4-training/RESULT.json','https://raw.githubusercontent.com/ggml-org/llama.cpp/b9980/tools/server/README.md','https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507#best-practices'],
 'criteria':'CPU percentages and physical/logical counts faithful, Spanish/English fluent, no assistant process/ownership claim. Other roles retain base behavior after adapter requests. No promotion without additional seed/generalization, actual role gating/runtime/integration and joint resource measurement. Never count existing wrong base-name prose as correct merely because unchanged.',
 'profiles':profiles,'adapter_sha256':sha(adapter),'manifest_sha256':manifest_sha,'server_command':command,'case_count':len(cases),'limits':{'gpu_stop_mib':3800,'free_ram_mib':768,'total_seconds':360,'request_seconds':60}})
''' + source[end:]
source = source.replace("write(out/'READY.json',", """with urllib.request.urlopen(url+'/lora-adapters',timeout=5) as response:adapters=json.load(response)
    write(out/'INITIAL_ADAPTERS.json',adapters)
    assert len(adapters)==1 and adapters[0]['id']==0
    request=urllib.request.Request(url+'/lora-adapters',data=json.dumps([{'id':0,'scale':0.}]).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=5) as response:write(out/'SET_ADAPTERS.json',json.load(response))
    with urllib.request.urlopen(url+'/lora-adapters',timeout=5) as response:adapters=json.load(response)
    write(out/'ADAPTERS.json',adapters)
    assert adapters[0]['scale']==0
    write(out/'READY.json',""")
source = source.replace("payload=copy.deepcopy(case['payload']);payload.update(settings)", """payload=copy.deepcopy(case['payload'])
            payload.update(settings if case['cpu_scope'] else {'seed':0,'cache_prompt':False,'lora':[{'id':0,'scale':0.}]})""")
source = source.replace('if gpu.peak_mib>3800:', 'if gpu.peak_mib is not None and gpu.peak_mib>3800:')
source = source.replace('27 native writer requests collected', '45 scoped adapter writer requests collected')
exec(compile(source, __file__, 'exec'))
