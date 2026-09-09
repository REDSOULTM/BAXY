"""Compare the phase projection's addressee with all other writer inputs fixed."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-native-compose-profile523.py').read_text(encoding='utf-8')
source = source.replace('astra-native-compose-profile523', 'astra-progress-addressee565').replace('C03-native-compose-profile523-private', 'C03-progress-addressee565-private')
start = source.index('ids=')
end = source.index('manifest=Path(', start)
source = source[:start] + '''
sys.path.insert(0,str(root/'src'))
from baxy_mind import llm
captured=json.loads((private.parent/'C03-gemma-current-writer557-private/cases.json').read_text(encoding='utf-8-sig'))
original=next(c['payload'] for c in captured if c['case']=='progress')
cases=[]
for language in ['es','en']:
    for phase in ['understanding','preparing_steps','acting','working']:
        facts=llm._compose_situation_payload({'kind':'status','cause':'acting','polarity':'success','phase':phase,'step':2,'totalSteps':5},language)
        payload=copy.deepcopy(original)
        contract=original['messages'][1]['content'].splitlines()[-1] if language=='es' else 'Mandatory language: English. Outside literal contract items, do not introduce Spanish words such as «Listo» or «encontré».'
        payload['messages'][1]['content']='situation: '+json.dumps(facts,ensure_ascii=False)+'\\n'+contract
        cases.append({'id':len(cases)+1,'case':language+':'+phase,'payload':payload})
''' + source[end:]
start = source.index('profiles=')
end = source.index("write(private/'cases.json',cases)", start)
source = source[:start] + '''
profiles=[('baseline',{'seed':0}),('addressee',{'seed':0})]
write(out/'PREREG.json',{'method':'Eight actual phase projections from current llm.py: ES/EN by understanding/preparing_steps/acting/working. Baseline versus changing only the request owner from third person to second person in the understanding phase. Other phase packets identical controls, not independent treatments. Same recorded system prompt, language, model, sampler, backend, token limit and step2/5. No original request or future goal inserted. No fixed visible response.',
 'inheritance':'Native521/561 repeats third-person request owner in Spanish. Source llm.py3288 introduces that third person. Historical97/99 used Qwen3.5-4B and validated phase scoping, not current Qwen2507 addressee behavior. Preserve that scoping and test only the misleading addressee.',
 'criteria':'All finals complete, directed to user, truthful current activity, no completion/effect/measurement claims. Exact supplied phase and step when present. Source adoption still requires owner tests, actual product and source gates. Development, no new survey or UI/voice credit.',
 'server_command':command,'manifest_sha256':manifest_sha,'profiles':profiles,'case_count':len(cases),
 'limits':{'gpu_stop_mib':3800,'free_ram_mib':768,'total_seconds':360,'request_seconds':60}})
''' + source[end:]
source = source.replace("payload=copy.deepcopy(case['payload']);payload.update(settings)", "payload=copy.deepcopy(case['payload']);payload.update(settings)\n            if profile=='addressee':\n                payload['messages'][1]['content']=payload['messages'][1]['content'].replace(\"reviewing the person's request\",'reviewing your request')")
source = source.replace('case_index%3', 'case_index%2')
source = source.replace('if gpu.peak_mib>3800:', 'if gpu.peak_mib is not None and gpu.peak_mib>3800:')
source = source.replace('if time.monotonic()-start>360:', "if gpu.peak_mib is None and time.monotonic()-start>10:violations.append('missing_gpu_telemetry')\n        if time.monotonic()-start>360:")
source = source.replace('27 native writer requests collected', '16 phase-writer requests collected')
exec(compile(source, __file__, 'exec'))
