"""Full mind proposals for actual unmute incidents; never execute audio effects."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,sys,time,threading
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/'src')]
import psutil
from scripts.measure_mind_budget import JsonLineProcess,current_core_catalog_snapshot,discover_core,ProcessTreeGpuSampler,RamSampler
base=root/'artifacts/comprobaciones/C03';local=Path(os.environ['LOCALAPPDATA'])/'BAXY'
out=base/'astra-audio-mind488';private=local/'C03-audio-mind488-private'
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
cases=[
 {'id':'owner44','request':by_index[44]['body'],'history':[],'expected':['audio.volume'],'arguments':{'level':100}},
 {'id':'owner46','request':by_index[46]['body'],'history':history([44,45]),'expected':['audio.mute'],'arguments':{'muted':False}},
 {'id':'owner51','request':by_index[51]['body'],'history':history([49,50]),'expected':['audio.volume','audio.mute'],'arguments':{'level':100,'muted':False}},
 {'id':'clitic-alone','request':'Desmutéalo','history':[],'expected':['audio.mute'],'arguments':{'muted':False}},
 {'id':'volume-unmute','request':'Pon el volumen al 37 y desmutéalo','history':[],'expected':['audio.volume','audio.mute'],'arguments':{'level':37,'muted':False}},
 {'id':'unmute-volume','request':'Desmutéalo y pon el volumen al 37','history':[],'expected':['audio.mute','audio.volume'],'arguments':{'level':37,'muted':False}},
 {'id':'negative-unmute','request':'Pon el volumen al 37 pero no quites el silencio','history':[],'expected':['audio.volume'],'arguments':{'level':37}},
 {'id':'word-meaning','request':'¿Qué significa desmutear?','history':[],'expected':[],'arguments':{}},
]
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json';config=json.loads(manifest.read_text(encoding='utf-8-sig'))
assert sha(manifest)=='13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
core=discover_core(None);capabilities,apps,games=current_core_catalog_snapshot(core)
write(private/'catalog.json',{'capabilities':capabilities,'applicationCatalog':apps,'gameCatalog':games})
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'method':'Full production mind sidecar with current catalogue/real app snapshots, source487 negative adversative repair; exact comparison against486 source485 and current registered model/runtime. Actual recovered owner264 indexes44/46/51 with exact immediately relevant pairs, plus five synthetic development controls. catalog.configure then turn.decide only: no provider invocations, volume/mute changes, UI or speech. Observe native requests/replies and route through actual lexical/semantic retrieval/argument guards; no forced selection/reply injection. Wait for actual E5 resources readiness as409; no fake readiness.','profile_reason':'Current registered runtime baseline for source regression, not a model-capability ranking or claim that defaults are optimal. Model-specific profile research448-484 remains; a bad result here is inspected at its first boundary, not a new default-based model rejection.','cases':cases,'criteria':'Useful operation-level proposal preserving both compound effects and order; correct grounded level and unmute=false where returned; negative/knowledge controls must not unmute. A plan with arguments to be bound later only proves selection, not provider success. Unresolved owner46/51 remain open until whole product is demonstrated. No reserve, acceptance or physical-resource credit.','model':config['gguf'],'model_sha256':sha(config['gguf']),'server':config['llama_server'],'server_sha256':sha(config['llama_server']),'manifest_sha256':sha(manifest),'core':str(core),'core_sha256':sha(core),'source_sha256':{str(p):sha(p) for p in [root/'src/baxy_mind/effect_intent.py',root/'src/baxy_mind/llm.py',root/'src/baxy_mind/__main__.py']},'private':str(private),'limits':{'gpu_stop_mib':3800,'minimum_free_ram_mib':768,'request_seconds':90}})
hook=private/'hook';hook.mkdir()
hook_source=(root/'scratchpad/c03-owner370-hook/sitecustomize.py').read_text(encoding='utf-8-sig').replace('C03-memory-product370-private','C03-audio-mind488-private')
hook_source+=(root/'scratchpad/c03-observe407-hook.py').read_text(encoding='utf-8-sig').replace("Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-retrieval-startup407-private/startup-observer.jsonl'","Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-audio-mind488-private/startup.jsonl'")
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
 config_req={'id':'catalog488','type':'catalog.configure','capabilities':capabilities}
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
  if violations:break
 complete=not violations
finally:
 stop.set();client.close(graceful_message={'id':'close488','type':'shutdown'},timeout=15);guard.join(timeout=5);gpu.stop();ram.stop()
 write(private/'stderr-tail.json',client._stderr_tail)
 write(out/'RESOURCES.json',{'completed':complete,'violations':violations,'gpu_peak_mib':gpu.peak_mib,'ram_peak_mib':ram.peak_mib,'seconds':round(time.monotonic()-start,3),'manifest_unchanged':sha(manifest)=='13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'})
assert complete
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
