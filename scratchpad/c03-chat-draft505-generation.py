"""Full mind proposals for actual unmute incidents; never execute audio effects."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,sys,time,threading
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/'src')]
import psutil
from scripts.measure_mind_budget import JsonLineProcess,current_core_catalog_snapshot,discover_core,ProcessTreeGpuSampler,RamSampler
base=root/'artifacts/comprobaciones/C03';local=Path(os.environ['LOCALAPPDATA'])/'BAXY'
out=base/'astra-audio-mind505-generation';private=local/'C03-audio-mind505-generation-private'
out.mkdir(exist_ok=False);private.mkdir(exist_ok=False)
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def append(p,v):
 with p.open('a',encoding='utf-8') as f:f.write(json.dumps(v,ensure_ascii=False)+'\n')
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
transcript=local/'C03-owner264-heap280/TRANSCRIPT282.json'
assert sha(transcript)=='9658a77505564ec1384e58aba91ed75d03b078f865182f94b6ecc3b0ee839ef6'
raw=json.loads(transcript.read_text(encoding='utf-8-sig'));rows=raw['messages'] if isinstance(raw,dict) else raw
by_index={r['index']:r for r in rows}
def history(indices):return [{'role':'user' if by_index[i]['isUser'] else 'assistant','content':by_index[i]['body']} for i in indices]
cases=[{'id': 'definition-es', 'request': '¿Qué significa desmutear?', 'history': [], 'expected': []}, {'id': 'definition-en', 'request': 'What does unmute mean?', 'history': [], 'expected': []}, {'id': 'ram-new-topic', 'request': 'Explain what RAM is.', 'history': [{'role': 'user', 'content': 'My name is Jordan.'}, {'role': 'assistant', 'content': 'Hello Jordan.'}], 'expected': []}, {'id': 'name-es', 'request': 'Me llamo Álvaro. ¿Cuál es mi nombre?', 'history': [], 'expected': []}, {'id': 'name-en', 'request': 'My name is Jordan. What is my name?', 'history': [], 'expected': []}, {'id': 'recall-es', 'request': '¿Cómo me llamo?', 'history': [{'role': 'user', 'content': 'Me llamo Álvaro.'}], 'expected': []}, {'id': 'recall-en', 'request': 'What is my name?', 'history': [{'role': 'user', 'content': 'My name is Jordan.'}, {'role': 'assistant', 'content': 'Your name is Morgan.'}], 'expected': []}]
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json';config=json.loads(manifest.read_text(encoding='utf-8-sig'))
assert sha(manifest)=='13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
core=discover_core(None);capabilities,apps,games=current_core_catalog_snapshot(core)
write(private/'catalog.json',{'capabilities':capabilities,'applicationCatalog':apps,'gameCatalog':games})
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'method':'505 generation: identical seven consumed development conversations, fresh sidecar; private chat-boundary observer. See parent astra-chat-draft505/PREREG.json.','profile_reason':'Current registered runtime baseline for source regression, not a model-capability ranking or claim that defaults are optimal. Model-specific profile research448-484 remains; a bad result here is inspected at its first boundary, not a new default-based model rejection.','cases':cases,'criteria':'Seven prior development cases: useful direct definition, correct human name/actor, correct language, no selector prose, no invented machine state or operation. All guards retained. Compare latency and resources; no provider, reserve, acceptance or model-ranking credit.','model':config['gguf'],'model_sha256':sha(config['gguf']),'server':config['llama_server'],'server_sha256':sha(config['llama_server']),'manifest_sha256':sha(manifest),'core':str(core),'core_sha256':sha(core),'source_sha256':{str(p):sha(p) for p in [root/'src/baxy_mind/effect_intent.py',root/'src/baxy_mind/llm.py',root/'src/baxy_mind/__main__.py']},'private':str(private),'limits':{'gpu_stop_mib':3800,'minimum_free_ram_mib':768,'request_seconds':90}})
hook=private/'hook';hook.mkdir()
hook_source=(root/'scratchpad/c03-owner370-hook/sitecustomize.py').read_text(encoding='utf-8-sig').replace('C03-memory-product370-private','C03-audio-mind505-generation-private')
hook_source+=(root/'scratchpad/c03-observe407-hook.py').read_text(encoding='utf-8-sig').replace("Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-retrieval-startup407-private/startup-observer.jsonl'","Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-audio-mind505-generation-private/startup.jsonl'")
hook_source += "\nfrom baxy_mind.llm import LlmRuntime as _DraftRuntime\n_draft_original_chat = _DraftRuntime.chat\ndef _draft_observed_chat(self, *args, **kwargs):\n    import json as _j\n    from pathlib import Path as _P\n    _draft = kwargs.get('initial_reply')\n    with (_P(os.environ['LOCALAPPDATA']) / 'BAXY/C03-audio-mind505-generation-private/chat-boundary.jsonl').open('a', encoding='utf-8') as _f:\n        _f.write(_j.dumps({'request': args[0] if args else kwargs.get('text'), 'mode': 'generation', 'initial_reply': _draft, 'kind': kwargs.get('conversation_kind')}, ensure_ascii=False) + '\\n')\n    if 'generation' == 'generation':\n        kwargs.pop('initial_reply', None)\n    return _draft_original_chat(self, *args, **kwargs)\n_DraftRuntime.chat = _draft_observed_chat\n"
(hook/'sitecustomize.py').write_text(hook_source,encoding='utf-8')
env=os.environ.copy()
for k in list(env):
 if k.startswith(('BAXY_MIND_','BAXY_VOICE_','BAXY_C03_')) or k in {'PYTHONPATH','BAXY_DATA_DIR'}:env.pop(k)
env.update(PYTHONPATH=str(hook)+os.pathsep+str(root/'src'),PYTHONUTF8='1',HF_HUB_OFFLINE='1',BAXY_MIND_LLM_GGUF=config['gguf'],BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config['ngl']),BAXY_VOICE_WAKE_ON_START='0',BAXY_MIND_TURN_AUDIT_PATH=str(private/'turn-audit.jsonl'),BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(private/'raw-replies.jsonl'),BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(private/'compose-audit.jsonl'),BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1')
client=JsonLineProcess([config['python'],'-u','-X','utf8','-m','baxy_mind'],environment=env,cwd=root)
write(out/'PROCESS.json',{'pid':client.pid})
gpu=ProcessTreeGpuSampler(os.getpid());ram=RamSampler(os.getpid());stop=threading.Event();violations=[];complete=False;start=time.monotonic()
def watch():
 while not stop.wait(.25):
  if gpu.peak_mib is not None and gpu.peak_mib>=3800:violations.append('gpu_bound')
  if psutil.virtual_memory().available<768*2**20:violations.append('system_free_ram_bound')
  if violations:client.close(timeout=2);return
guard=threading.Thread(target=watch,daemon=True)
try:
 gpu.start();ram.start();guard.start()
 hello=client.next_message(90);write(private/'hello.json',hello);assert hello.get('type')=='hello'
 config_req={'id':'catalog505-generation','type':'catalog.configure','capabilities':capabilities}
 if apps is not None:config_req['applicationCatalog']=apps
 if games is not None:config_req['gameCatalog']=games
 ready=client.request(config_req,90);assert ready.get('type')=='catalog.ready'
 wait_start=time.monotonic();observed=[]
 while time.monotonic()-wait_start<195:
  observed=list(map(json.loads,(private/'startup.jsonl').open(encoding='utf-8-sig'))) if (private/'startup.jsonl').exists() else []
  if any(r['event']=='resources_built' and r.get('semantic') for r in observed):break
  if any(r['event'] in {'router_failed','resources_failed'} for r in observed) or violations:break
  time.sleep(.25)
 write(out/'STARTUP.json',{'seconds':time.monotonic()-wait_start,'events':observed})
 assert any(r['event']=='resources_built' and r.get('semantic') for r in observed), 'No semantic readiness; do not label this warm'
 print('Mind and semantic resources ready',flush=True)
 for case in cases:
  before=time.monotonic();request={'id':case['id'],'type':'turn.decide','text':case['request'],'history':case['history'],'pendingClarification':False,'uiLanguage':'es'}
  append(private/'requests.jsonl',request)
  try:reply=client.request(request,90)
  except Exception as error:reply={'error':type(error).__name__+': '+str(error)}
  result={'id':case['id'],'seconds':round(time.monotonic()-before,3),'reply':reply};append(out/'replies.jsonl',result);print(json.dumps(result,ensure_ascii=True),flush=True)
  binding_request = None
  if reply.get('kind') == 'plan':
   binding_request = {'id':case['id']+'-plan','type':'plan','text':case['request'],'history':case['history'],'expectedOperations':reply['effectOperations']}
  elif reply.get('kind') == 'action' and reply.get('operation'):
   selected = next(c for c in capabilities if c['name'] == reply['operation'])
   if selected['argumentsSchema'].get('properties'):
    binding_request = {'id':case['id']+'-arguments','type':'arguments','operation':reply['operation'],'text':case['request']}
  if binding_request is not None:
   append(private/'binding-requests.jsonl',binding_request)
   bind_start = time.monotonic()
   try: binding_reply = client.request(binding_request,90)
   except Exception as error: binding_reply = {'error':type(error).__name__+': '+str(error)}
   binding_row = {'id':case['id'],'type':binding_request['type'],'seconds':round(time.monotonic()-bind_start,3),'reply':binding_reply}
   append(out/'bindings.jsonl',binding_row)
   print(json.dumps({'binding':case['id'],'type':binding_request['type'],'reply':binding_reply},ensure_ascii=True),flush=True)
  if violations:break
 complete=not violations
finally:
 stop.set();client.close(graceful_message={'id':'close505-generation','type':'shutdown'},timeout=15);guard.join(timeout=5);gpu.stop();ram.stop()
 write(private/'stderr-tail.json',client._stderr_tail)
 write(out/'RESOURCES.json',{'completed':complete,'violations':violations,'gpu_peak_mib':gpu.peak_mib,'ram_peak_mib':ram.peak_mib,'seconds':round(time.monotonic()-start,3),'manifest_unchanged':sha(manifest)=='13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'})
assert complete
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
