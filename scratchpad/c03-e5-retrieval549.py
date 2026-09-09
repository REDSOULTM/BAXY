"""Same E5, effective tokenizer and actual PlannerCatalog; no product adoption."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys,time
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/'src')]
base=root/'artifacts/comprobaciones/C03'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-e5-retrieval549-private'
previous=private.parent/'C03-e5-backend547-private'
out=base/'astra-e5-retrieval549'
assets=Path('D:/BAXYRuntime/experiments/models/e5-onnx-614241f6')
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

if len(sys.argv)>1:
    import numpy as np
    mode=sys.argv[1]
    rows=read(previous/'queries.json')
    documents=read(private/'documents.json')
    before=time.perf_counter()
    if mode=='torch':
        from baxy_mind.router import SemanticEncoder
        model=SemanticEncoder()
        encode=lambda texts,prefix:model.encode(texts,prefix=prefix)
        details={'torch_threads':__import__('torch').get_num_threads()}
    else:
        import onnxruntime as ort
        from tokenizers import Tokenizer
        tokenizer=Tokenizer.from_file(str(previous/'effective-tokenizer548.json'))
        tokenizer.enable_truncation(max_length=512)
        tokenizer.enable_padding(pad_id=1,pad_token='<pad>')
        assert tokenizer.token_to_id('<pad>')==1
        options=ort.SessionOptions()
        options.intra_op_num_threads=8
        options.inter_op_num_threads=1
        options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
        options.enable_cpu_mem_arena=mode!='fp32-no-arena'
        filename='model_qint8_avx512_vnni.onnx' if mode=='int8' else 'model.onnx'
        session=ort.InferenceSession(str(assets/filename),sess_options=options,providers=['CPUExecutionProvider'])
        names={n.name for n in session.get_inputs()}
        def encode(texts,prefix):
            encoded=tokenizer.encode_batch([prefix+': '+s for s in texts])
            ids=np.asarray([e.ids for e in encoded],dtype=np.int64)
            mask=np.asarray([e.attention_mask for e in encoded],dtype=np.int64)
            inputs={'input_ids':ids,'attention_mask':mask}
            if 'token_type_ids' in names:inputs['token_type_ids']=np.asarray([e.type_ids for e in encoded],dtype=np.int64)
            vectors=session.run(None,inputs)[0]
            weights=mask[...,None].astype(np.float32)
            values=(vectors*weights).sum(1)/weights.sum(1)
            return values/np.linalg.norm(values,axis=1,keepdims=True)
        details={'cpu_mem_arena':options.enable_cpu_mem_arena,'threads':8,'providers':session.get_providers(),'graph_sha256':sha(assets/filename)}
    loaded=time.perf_counter()-before
    started=time.perf_counter()
    passages=np.concatenate([encode(documents[i:i+8],'passage') for i in range(0,len(documents),8)])
    if mode=='torch':
        queries=np.load(previous/'torch.npy',allow_pickle=False)
    else:
        queries=np.concatenate([encode([r['text'] for r in rows[i:i+8]],'query') for i in range(0,len(rows),8)])
    batch_seconds=time.perf_counter()-started
    timings=[]
    for text in ['Dime la hora y cuánta batería tengo.','What GPU is installed on this computer?',rows[165]['text']]:
        for _ in range(3):
            started=time.perf_counter()
            encode([text],'query')
            timings.append(time.perf_counter()-started)
    np.save(private/(mode+'-queries.npy'),queries)
    np.save(private/(mode+'-passages.npy'),passages)
    write(private/(mode+'-timing.json'),{'load_seconds':loaded,'batch_seconds':batch_seconds,'single_query_seconds':timings,'details':details,'torch_imported':'torch' in sys.modules,'torch_queries_reused547':mode=='torch'})
    print(mode+' complete',flush=True)
    raise SystemExit(0)

import psutil
from scripts.measure_mind_budget import RamSampler,current_core_catalog_snapshot,discover_core,DEFAULT_CORE_CANDIDATES
from baxy_mind.__main__ import configure_tools
from baxy_mind.planner import PlannerCatalog
assert psutil.virtual_memory().available/2**20>2500
private.mkdir(exist_ok=False)
out.mkdir(exist_ok=False)
capabilities,_,_=current_core_catalog_snapshot(discover_core(None,candidates=reversed(DEFAULT_CORE_CANDIDATES)))
tools=configure_tools(capabilities)
catalog=PlannerCatalog(tools)
write(private/'tools.json',tools)
write(private/'documents.json',catalog._tool_documents)
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'method':'Use effective tokenizer exported from pinned AutoTokenizer548, not an assumed strip patch. Compare current torch query vectors547 with newly encoded actual PlannerCatalog passages and three ONNX profiles. Query and passage prefixes, mean pooling, L2 norm,512 limit unchanged. Full actual shortlist ordering and inclusion compared on742 development survey messages. Diagnostic only; no execution authority or product adoption.',
 'cause':'547 FP32 drift isolated to H0166/H0704 trailing whitespace; AutoTokenizer changes normalizer and adds WhitespaceSplit versus tokenizer.json.548 confirms token difference and exports actual backend. INT8 still needs retrieval-quality evidence.',
 'tokenizer_sha256':sha(previous/'effective-tokenizer548.json'),'queries_sha256':sha(previous/'queries.json'),'catalog_sha256':sha(private/'tools.json'),'profiles':['torch','fp32','fp32-no-arena','int8'],
 'limits':{'free_ram_mib':768,'seconds_per_process':360},'criteria':'FP32 numerical equivalence and zero shortlist changes. INT8 changes require individual quality adjudication, not automatic rejection or acceptance. No-arena only disables ORT allocator retention; same FP32 graph and optimizations. Timings are warmed local queries, not product latency. No voice/UI or joint VRAM claim.'})
resources={}
for mode in ('torch','fp32','fp32-no-arena','int8'):
    env=os.environ.copy()
    env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
    with (out/(mode+'.log')).open('w',encoding='utf-8') as log:
        process=subprocess.Popen([sys.executable,'-X','utf8',__file__,mode],env=env,cwd=root,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        sampler=RamSampler(process.pid);sampler.start();started=time.monotonic();violations=[]
        try:
            while process.poll() is None:
                if time.monotonic()-started>360:violations.append('wall_time')
                if psutil.virtual_memory().available/2**20<768:violations.append('free_ram')
                if violations:process.kill();break
                time.sleep(.25)
            process.wait(timeout=20)
        finally:sampler.stop()
        resources[mode]={'exit_code':process.returncode,'peak_ram_mib':sampler.peak_mib,'seconds':time.monotonic()-started,'violations':violations}
        write(out/'RESOURCES.json',resources)
        assert process.returncode==0 and not violations
    print(mode+' collected',flush=True)
import numpy as np
rows=read(previous/'queries.json')
rankings={}
numeric={}
for mode in resources:
    queries=np.load(private/(mode+'-queries.npy'),allow_pickle=False)
    passages=np.load(private/(mode+'-passages.npy'),allow_pickle=False)
    lookup={r['text']:queries[i] for i,r in enumerate(rows)}
    def cached(texts,prefix='query'):
        if prefix=='passage':return passages
        return np.stack([lookup[text] for text in texts])
    current=PlannerCatalog(tools,encoder=cached)
    rankings[mode]=[[t.name for t in current.shortlist(r['text'])] for r in rows]
    if mode!='torch':
        reference=np.load(private/'torch-queries.npy',allow_pickle=False)
        passage_ref=np.load(private/'torch-passages.npy',allow_pickle=False)
        numeric[mode]={'min_query_cosine':float((queries*reference).sum(1).min()),'max_query_component_difference':float(np.abs(queries-reference).max()),'min_passage_cosine':float((passages*passage_ref).sum(1).min())}
write(private/'shortlists.json',rankings)
comparison={}
for mode in resources:
    if mode=='torch':continue
    changed=[rows[i]['case_id'] for i,(a,b) in enumerate(zip(rankings['torch'],rankings[mode])) if a!=b]
    membership=[rows[i]['case_id'] for i,(a,b) in enumerate(zip(rankings['torch'],rankings[mode])) if set(a)!=set(b)]
    first=[rows[i]['case_id'] for i,(a,b) in enumerate(zip(rankings['torch'],rankings[mode])) if a[0]!=b[0]]
    comparison[mode]={'changed_order_case_ids':changed,'changed_membership_case_ids':membership,'changed_top1_case_ids':first,'numeric':numeric[mode]}
write(out/'RESULT.json',{'resources':resources,'comparison':comparison,'timing':{mode:read(private/(mode+'-timing.json')) for mode in resources},'adopted':False})
print(json.dumps({m:{'order':len(r['changed_order_case_ids']),'membership':len(r['changed_membership_case_ids']),'top1':len(r['changed_top1_case_ids'])} for m,r in comparison.items()}),flush=True)
