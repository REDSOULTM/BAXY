"""Replay captured writer requests with registered versus documented Qwen3.5 sampling."""
from pathlib import Path
from datetime import datetime,timezone
import copy,hashlib,json,os,socket,subprocess,sys,threading,time,urllib.request,urllib.error
import psutil

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from scripts.measure_mind_budget import ProcessTreeGpuSampler,RamSampler

base=root/'artifacts/comprobaciones/C03'
out=base/'astra-native-compose-profile525';out.mkdir(exist_ok=False)
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-native-compose-profile525-private';private.mkdir(exist_ok=False)
previous=private.parent/'C03-private-product521-private'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def append(p,v):
    with p.open('a',encoding='utf-8') as f:f.write(json.dumps(v,ensure_ascii=False)+'\n')

ids={7:'stored-name-en',11:'stored-name-es',19:'memory-capability-disabled'}
rows=list(map(json.loads,(previous/'http-posts.jsonl').open(encoding='utf-8-sig')))
cases=[{'id':r['id'],'case':ids[r['id']],'payload':r['payload']} for r in rows if r['stage']=='request' and r['id'] in ids]
assert len(cases)==3 and all(c['payload']['messages'][0]['content'].startswith('Eres BAXY, un compañero. Eres un él.') for c in cases)
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
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'cause':'524 exact resolved private reads are reinterpreted as assistant identity or generic chatbot memory capability. _compose_user_content already separates request from situation/language; its existing include_request control can scope generation without changing the real input used for routing/guards. Prior code comment about account-read identity warns against broad changes: this test is only memory.recall/status completed data, not account queries or welcome.','method':'Three original524 payloads, same Qwen3.5/b10865 and three sampling profiles. Remove only the first raw natural-question line before situation, retaining all system text, JSON fields and values, language and literal contracts. No replacement words, role/provenance guesses, value extraction, output editing or source changes. Compare each of9responses against its exact524 baseline counterpart.','profiles':profiles,'sources':['https://huggingface.co/Qwen/Qwen3.5-4B','src/baxy_mind/llm.py:_compose_user_content','524 exact payloads and responses'],'criteria':'Stored EN/ES entry must report Jordan without claiming it is the assistant identity; disabled store must be described from observed facts without false loss of capability, erasure, playback or resets. Preserve explicit language and literal data. Any promising change needs bounded source guards, preservation of original request/readers/format requirements, and full product before adoption. No general deletion of user requests.','server_command':command,'model_sha256':sha(command[command.index('-m')+1]),'server_sha256':sha(command[0]),'manifest_sha256':manifest_sha,'capture_sha256':sha(previous/'http-posts.jsonl'),'limits':{'gpu_stop_mib':3800,'free_ram_mib':768,'total_seconds':360,'request_seconds':60},'exclusions':'Native consumed synthetic data only. No actual status/effects, source/runtime promotion, physicalUI/voice or acceptance. Native prototype removes one known frame line; production, if adopted, must operate on typed composition inputs.'})

original_cases=copy.deepcopy(cases)
for case in cases:
    messages=case['payload']['messages']
    assert len(messages)==2 and messages[-1]['role']=='user'
    content=messages[-1]['content'];request,separator,rest=content.partition('\n')
    assert separator and rest.startswith('situation: ')
    situation=json.loads(rest.splitlines()[0].removeprefix('situation: '))
    assert situation.get('kind')=='status' and situation.get('outcome')=='completed'
    assert situation.get('operation') in {'memory.recall','memory.status'}
    messages[-1]['content']=rest
    append(private/'input-treatment.jsonl',{'case':case['case'],'removed_raw_question':request,'situation_unchanged':True,'before_sha256':hashlib.sha256(content.encode()).hexdigest(),'after_sha256':hashlib.sha256(rest.encode()).hexdigest()})
write(private/'original-cases.json',original_cases)

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
print('9 native writer requests collected; adjudication pending.',flush=True)
