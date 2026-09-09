"""Replay captured writer requests with registered versus documented Qwen3.5 sampling."""
from pathlib import Path
from datetime import datetime,timezone
import copy,hashlib,json,os,socket,subprocess,sys,threading,time,urllib.request,urllib.error
import psutil

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from scripts.measure_mind_budget import ProcessTreeGpuSampler,RamSampler

base=root/'artifacts/comprobaciones/C03'
out=base/'astra-native-compose-profile524';out.mkdir(exist_ok=False)
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-native-compose-profile524-private';private.mkdir(exist_ok=False)
previous=private.parent/'C03-private-product521-private'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def append(p,v):
    with p.open('a',encoding='utf-8') as f:f.write(json.dumps(v,ensure_ascii=False)+'\n')

ids={1:'disabled-save-error',2:'enable-confirmation',3:'enable-result',4:'save-result',6:'app-clarification',7:'stored-name-en',11:'stored-name-es',12:'progress',17:'disable-result',18:'clock-result',19:'memory-capability-disabled'}
rows=list(map(json.loads,(previous/'http-posts.jsonl').open(encoding='utf-8-sig')))
cases=[{'id':r['id'],'case':ids[r['id']],'payload':r['payload']} for r in rows if r['stage']=='request' and r['id'] in ids]
assert len(cases)==11 and all(c['payload']['messages'][0]['content'].startswith('Eres BAXY, un compañero. Eres un él.') for c in cases)
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
manifest_sha=sha(manifest);assert manifest_sha=='13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
command=json.loads((previous/'effective-server-command.json').read_text(encoding='utf-8-sig'))
command[0]='D:/BAXYRuntime/assets/llama-b10865-cuda12.4/llama-server.exe'
command[command.index('-m')+1]='D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf'
assert sha(command[0])=='16eac28198d6218a9892f08dac0f0c81612a72872b4dd9741c4c6c36f88c4fd7'
assert sha(command[command.index('-m')+1])=='00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
command[command.index('--port')+1]=str(port)
command[command.index('--log-file')+1]=str(private/'server.log')
profiles=[('production-greedy-seed0',{'seed':0}),('documented-seed0',{'temperature':0.7,'top_p':0.8,'top_k':20,'min_p':0.0,'presence_penalty':1.5,'repeat_penalty':1.0,'seed':0}),('documented-seed17',{'temperature':0.7,'top_p':0.8,'top_k':20,'min_p':0.0,'presence_penalty':1.5,'repeat_penalty':1.0,'seed':17})]
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'method':'Eleven exact captured521 writer payloads: nine523 cases plus both protected stored-name controls associated with the old437 wrong-speaker failure. Qwen3.5-4B Q4, compatible b10865; compare generic production greedy with its official non-thinking profile at seeds0/17. No prompt/data/output edits or Core effects.','source':'https://huggingface.co/Qwen/Qwen3.5-4B','profile_rationale':'Qwen3.5 non-thinking general tasks: temperature0.7,top_p0.8,top_k20,min_p0,presence_penalty1.5,neutral repetition1. Greedy is the existing composition baseline, not claimed to be optimal. Explicit enable_thinking=false and server reasoning off retained. Max256 for brief native replies, every length finish is a failure.','profiles':profiles,'cases':[{'id':c['id'],'case':c['case'],'payload_sha256':hashlib.sha256(json.dumps(c['payload'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()} for c in cases],'criteria':'Review all outputs for fact/cause/decision/language/voice. Save metadata and disabled-capability errors must improve; both stored-name results must keep the human subject and literal value. Read-only clock, disable, clarification, progress and confirmation remain controls. No success just from one fluent sample orHTTP200. No promotion before full path and guards.','server_command':command,'model_sha256':sha(command[command.index('-m')+1]),'server_sha256':sha(command[0]),'manifest_sha256':manifest_sha,'capture_sha256':sha(previous/'http-posts.jsonl'),'limits':{'gpu_stop_mib':3800,'free_ram_mib':768,'total_seconds':360,'request_seconds':60},'exclusions':'All consumed synthetic development; no fresh acceptance, physicalUI/voice or global model ranking. Same local resources ceiling, but model and compatible backend deliberately differ from523. Compare common9 separately; extra2 recover known Qwen3.5 defect. No blind replay of437: native composition payload/source520 and per-model sampling now tested.'})
write(private/'cases.json',cases)
with (private/'launch.log').open('w',encoding='utf-8') as launch:
    process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=launch,stderr=subprocess.STDOUT,cwd=root,creationflags=subprocess.CREATE_NO_WINDOW)
write(out/'PROCESS.json',{'pid':process.pid,'command':command})
gpu=ProcessTreeGpuSampler(process.pid);ram=RamSampler(process.pid)
gpu.start();ram.start();start=time.monotonic();stop=threading.Event();violations=[];complete=False
def terminate_owned():
    try:
        parent=psutil.Process(process.pid)
        for child in parent.children(recursive=True):
            try:child.kill()
            except psutil.Error:pass
        parent.kill()
    except psutil.Error:pass
def guard():
    while not stop.wait(.25):
        if gpu.peak_mib>3800:violations.append('gpu_stop')
        if psutil.virtual_memory().available/(1024**2)<768:violations.append('low_free_ram')
        if time.monotonic()-start>360:violations.append('wall_time')
        if violations:terminate_owned();return
thread=threading.Thread(target=guard,daemon=True);thread.start()
url=f'http://127.0.0.1:{port}'
try:
    while time.monotonic()-start<90:
        assert process.poll() is None and not violations,'server stopped before readiness'
        try:
            with urllib.request.urlopen(url+'/health',timeout=2) as response:health=json.load(response)
            if health.get('status')=='ok':break
        except (urllib.error.URLError,TimeoutError):pass
        time.sleep(.25)
    else:raise TimeoutError('server readiness')
    write(out/'READY.json',{'seconds':time.monotonic()-start,'health':health})
    for case_index,case in enumerate(cases):
        # Rotate order to avoid assigning every cold request to the same profile.
        order=profiles[case_index%3:]+profiles[:case_index%3]
        for profile,settings in order:
            payload=copy.deepcopy(case['payload']);payload.update(settings)
            append(private/'requests.jsonl',{'case':case['case'],'source_id':case['id'],'profile':profile,'payload':payload})
            before=time.monotonic()
            request=urllib.request.Request(url+'/v1/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
            try:
                with urllib.request.urlopen(request,timeout=60) as response:result=json.load(response)
                record={'case':case['case'],'source_id':case['id'],'profile':profile,'seconds':time.monotonic()-before,'response':result}
            except Exception as error:
                record={'case':case['case'],'source_id':case['id'],'profile':profile,'seconds':time.monotonic()-before,'error':type(error).__name__+': '+str(error)}
            append(private/'responses.jsonl',record)
            assert not violations
        print('completed '+case['case'],flush=True)
    complete=True
finally:
    stop.set();terminate_owned();process.wait(timeout=20);thread.join(timeout=5);gpu.stop();ram.stop()
    write(out/'RESOURCES.json',{'completed':complete,'violations':violations,'gpu_peak_mib':gpu.peak_mib,'ram_peak_mib':ram.peak_mib,'seconds':round(time.monotonic()-start,3),'manifest_unchanged':sha(manifest)==manifest_sha,'server_exit_after_intentional_cleanup':process.returncode})
assert complete and not violations
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
print('33 native writer requests collected; adjudication pending.',flush=True)
