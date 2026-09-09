"""Controlled insertion of BAXY conversation layers, starting with the registered bare LLM."""
from pathlib import Path
import copy,hashlib,json,os,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from baxy_mind.llm import LlmRuntime,SYSTEM_PROMPT
from scripts.measure_mind_budget import ProcessTreeGpuSampler,RamSampler
register=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
config=json.loads(register.read_text(encoding='utf-8-sig'))
model_key=sys.argv[1] if len(sys.argv)>1 else 'registered'
assert model_key in {'registered','qwen-base'}
MODEL=Path(config['gguf']) if model_key=='registered' else Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/Qwen3-4B-Instruct-2507-Q4_K_M.gguf')
OUT=ROOT/f'artifacts/comprobaciones/C03/astra-unsupported-evidence-{model_key}'
assert not OUT.exists();OUT.mkdir()
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
source=ROOT/'artifacts/comprobaciones/C03/astra-clarification-error-qwen/paired.json'
questions=[('Abre EstudioC03Inexistente.','es'),('Open EstudioC03Inexistente.','en'),('Open EstudioC03Inexistente, por favor.','mixed'),('Abre la aplicación EstudioC03.','es'),('Open the application EstudioC03.','en'),('Open la aplicación EstudioC03, please.','mixed'),('Abre el archivo AusenteC03.','es'),('Open the file MissingC03.','en'),('Open el archivo MissingC03, please.','mixed')]
cases=[{'id':f'unsupported-{i+1}','request':q,'language':lang,'kind':'unsupported','history':[]} for i,(q,lang) in enumerate(questions)]
class Captured(Exception):pass
class Recorder(LlmRuntime):
    def __init__(self):self._gguf=str(MODEL);self.payload=None
    def _post(self,payload):self.payload=copy.deepcopy(payload);raise Captured()
for case in cases:
    for name,previous in [('policies',None),('history',case['history'])]:
        recorder=Recorder()
        try:recorder.chat(case['request'],history=previous,conversation_kind=case['kind'],response_language=case['language'])
        except Captured:pass
        assert recorder.payload
        case[name+'_payload']=recorder.payload
for case in cases:
    captured=copy.deepcopy(case['history_payload'])
    case['product_history_payload']=captured
    case['history_payload']=copy.deepcopy(case['policies_payload'])
    prior=[m for m in captured['messages'] if m['role'] in {'user','assistant'}][:-1]
    case['history_payload']['messages'][-1:-1]=prior
stages=['guarded']
common={'temperature':.7,'top_p':.95,'top_k':40,'min_p':.05,'seed':0,'cache_prompt':False,'chat_template_kwargs':{'enable_thinking':False}}
prereg={'kind':'unsupported-boundary-without-observation-diagnostic-not-acceptance','modelRole':model_key,'model':str(MODEL),
 'stages':stages,'cases':cases,'sampling':common,'budgets':{'bareThroughHistory':512,'budgetAndGuarded':128,'perCaseSeconds':55,'gpuMiB':4096},
 'criterion':'Owner clarification applies: Spanish is valid for mixed input, simple useful explanations need not be exhaustive; explicit format, contradictions, inventions, failures and silence are still assessed. No fixed bilingual proportion.',
 'interpretation':'Bare has only the literal user message and native model template. Runtime helper only manages the same local llama-server and HTTP transport. Identity adds the short identity, system replaces it with complete system instructions, policies adds actual turn/language instructions, history adds the actual bounded transcript, budget changes only token cap, routed applies actual history-dependent presentation routing; guarded adds real chat validation and retry, asserting first payload equality. History contains prior captured model errors, preserved as a distinct causal factor.',
 'scope':'Explicit unsupported-mode prose only: this does not test whether the nine requests should be routed to unsupported. No PC observations/attempts. Nine cases; before/after input3fromcaptured app plus6controls. Only guarded stage executed. No PC effects or current-state questions without facts. Compositor, kernel/app and UI must be measured separately afterward.',
 'hashes':{str(p):digest(p) for p in [MODEL,Path(config['llama_server']),register,source,ROOT/'src/baxy_mind/llm.py']}}
(OUT/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2),encoding='utf-8')
os.environ.update(BAXY_MIND_LLM_GGUF=str(MODEL),BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config.get('ngl',99)),BAXY_MIND_KV_CACHE_TYPE='q8_0',BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(OUT/'raw-audit.jsonl'))
class Client(LlmRuntime):
    def __init__(self):super().__init__();self.stage=None;self.case=None
    def _post(self,payload,*args,**kwargs):
        payload=copy.deepcopy(payload);payload.update(common)
        payload['max_tokens']=128 if self.stage in {'budget','routed','guarded'} else 512
        if self.stage=='guarded' and not getattr(self,'checked_first',False):
            expected=next(c for c in cases if c['id']==self.case)['product_history_payload']['messages']
            assert payload['messages']==expected, 'Guarded first messages differ from recorded product history payload'
            self.checked_first=True
        response=super()._post(payload,*args,**kwargs)
        if self.stage:
            with (OUT/'posts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'stage':self.stage,'case':self.case,'payload':payload,'response':response},ensure_ascii=False)+'\n')
        return response
client=Client();gpu=ProcessTreeGpuSampler(os.getpid());ram=RamSampler(os.getpid());gpu.start();ram.start();started=time.monotonic();fatal=None
try:
    client.start_warmup();assert client.wait_warmup(90)
    (OUT/'SERVER_COMMAND.json').write_text(json.dumps(client._server_command(),ensure_ascii=False,indent=2),encoding='utf-8')
    for stage in stages:
        client.stage=stage
        for case in cases:
            assert gpu.peak_mib is not None and gpu.peak_mib<=4096
            client.case=case['id'];client.checked_first=False;client.begin_request(55);tick=time.monotonic();answer=None;error=None;finish=None
            try:
                if stage=='guarded':
                    answer,calls=client.chat(case['request'],history=case['history'],conversation_kind=case['kind'],response_language=case['language'])
                    assert not calls
                else:
                    if stage in {'policies','history','budget','routed'}:payload=copy.deepcopy(case['product_history_payload' if stage=='routed' else 'policies_payload' if stage=='policies' else 'history_payload'])
                    else:
                        messages=[{'role':'user','content':case['request']}]
                        if stage in {'identity','system'}:messages.insert(0,{'role':'system','content':SYSTEM_PROMPT if stage=='system' else 'Eres BAXY, un compañero que vive en el PC. Eres un él. Tuteas.'})
                        payload={'messages':messages}
                    response=client._post(payload);choice=response['choices'][0];answer=choice['message']['content'];finish=choice.get('finish_reason')
            except Exception as exc:error=f'{type(exc).__name__}: {exc}'
            finally:client.end_request()
            row={'stage':stage,'id':case['id'],'request':case['request'],'response':answer,'finishReason':finish,'error':error,'seconds':round(time.monotonic()-tick,3)}
            with (OUT/'replies.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
            print(json.dumps({'stage':stage,'case':case['id'],'seconds':row['seconds'],'error':error}),flush=True)
except Exception as exc:fatal=f'{type(exc).__name__}: {exc}'
finally:
    client.close();gpu.stop();ram.stop();result={'seconds':round(time.monotonic()-started,2),'gpuPeakMiB':gpu.peak_mib,'ramPeakMiB':ram.peak_mib,'error':fatal,'registrationUnchanged':digest(register)==prereg['hashes'][str(register)]}
    (OUT/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
