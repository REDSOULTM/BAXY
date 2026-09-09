"""Inherited measured Gemma profile on current writer failures, without new prompts."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-native-compose-profile523.py').read_text(encoding='utf-8')
source=source.replace('astra-native-compose-profile523','astra-gemma-current-writer554').replace('C03-native-compose-profile523-private','C03-gemma-current-writer554-private')
source=source.replace("ids={1:","ids={7:'stored-name-en',11:'stored-name-es',1:").replace('len(cases)==9','len(cases)==11')
start=source.index("command=json.loads(")
end=source.index('with socket.socket()',start)
source=source[:start]+'''command=json.loads((base/'astra-gemma-resources462/command.json').read_text(encoding='utf-8-sig'))
assert sha(command[0])=='cb29f66008d4d73cce17cab2c2569ab318eb244b0b2ca2a15024b44d90dfcd3f'
assert sha(command[command.index('-m')+1])=='9d4a5a653f2733a5faeb5f58a0e30bc064dfd569b0059cabb2547dbc4ba0f4b7'
for campaign,selector in [
 ('C03-survey-readonly541-private',lambda r:r['id'] in {26,27,59}),
 ('C03-survey-resume543-private',None),
 ('C03-coordinate-product546-private',lambda r:r['id'] in {2,4}),
]:
    path=private.parent/campaign
    if selector is None:
        panel=json.loads((path/'panel.json').read_text(encoding='utf-8'))
        texts=[c['text'] for c in panel if c['case_id'] in {'H0078','H0065'}]
        selector=lambda r:any(r['payload']['messages'][-1]['content'].startswith(t+'\\n') for t in texts)
    for line in (path/'http-posts.jsonl').read_text(encoding='utf-8-sig').splitlines():
        row=json.loads(line)
        if row['stage']=='request' and row['payload'].get('messages') and row['payload']['messages'][0]['content'].startswith('Eres BAXY, un compañero.') and selector(row):
            cases.append({'id':row['id'],'case':campaign+':'+str(row['id']),'payload':row['payload']})
assert len(cases)==20
''' +source[end:]
start=source.index('profiles=')
end=source.index("write(private/'cases.json',cases)",start)
source=source[:start]+'''profiles=[('gemma-measured-thinking-seed0',{'temperature':1.,'top_p':.95,'top_k':64,'min_p':0.,'presence_penalty':0.,'repeat_penalty':1.,'seed':0,'max_tokens':3072,'reasoning_budget_tokens':-1})]
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),
 'method':'Twenty unmodified current native writer captures521/541/543/546 across private errors, confirmation, mutations, recall, capability, progress, hardware observations, social closing and compound readings. Change strategy after failed general prompt/metadata and quantity enrichment: reuse Gemma profile462 with documented thinking sampler and lazy PLE. Same system/user messages and raw facts; no numeric treatment552/553. Registered Qwen remains untouched.',
 'inheritance':'462 on same machine: thinking Gemma with lazy-mode on retained12 composition outcomes and reduced own RAM2832.90→1005.51MiB, VRAM1692.18MiB. This is evidence for a fair local profile, not certification of current response quality.464 product memory7/8 and first confirmation gap remain historical limits. No generic default-model rejection.',
 'profile':profiles,'server_command':command,'model_sha256':sha(command[command.index('-m')+1]),'server_sha256':sha(command[0]),'manifest_sha256':manifest_sha,
 'sources':['artifacts/comprobaciones/C03/astra-gemma-resources462/PREREG.json','https://github.com/ggml-org/llama.cpp/pull/27794','https://github.com/ggml-org/llama.cpp/pull/27837'],
 'criteria':'Review only visible content, never reasoning as final. Every response must preserve facts, speaker/subject, capability versus activation, pending confirmation and language. Native success is not product promotion: actual guards, desktop/UI/audio, resource budget and regression still required. EOS/length recorded, no truncation treated as pass. Single seed development screen, not blind acceptance or full model ranking.',
 'authorization':'AUTORIZACION_DUENO_536.md; all content local. No Core effects or private owner profile.',
 'case_count':len(cases),'cases':[{'case':c['case'],'source_id':c['id']} for c in cases],
 'limits':{'gpu_stop_mib':3800,'free_ram_mib':768,'total_seconds':360,'request_seconds':60}})
''' +source[end:]
source=source.replace('case_index%3','case_index%1')
source=source.replace("payload=copy.deepcopy(case['payload']);payload.update(settings)","payload=copy.deepcopy(case['payload']);payload.update(settings)\n            payload['chat_template_kwargs']={**payload.get('chat_template_kwargs',{}),'enable_thinking':True}")
source=source.replace('if gpu.peak_mib>3800:','if gpu.peak_mib is not None and gpu.peak_mib>3800:')
source=source.replace('if time.monotonic()-start>360:',"if gpu.peak_mib is None and time.monotonic()-start>10:violations.append('missing_gpu_telemetry')\n        if time.monotonic()-start>360:")
source=source.replace('27 native writer requests collected','20 current Gemma writer requests collected')
exec(compile(source,__file__,'exec'))
