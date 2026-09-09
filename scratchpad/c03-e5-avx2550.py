"""Quantize the same E5 for non-VNNI AVX2, then reuse549 retrieval faithfully."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys,time
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
out=root/'artifacts/comprobaciones/C03/astra-e5-avx2550'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-e5-avx2550-private'
assets=Path('D:/BAXYRuntime/experiments/models/e5-onnx-614241f6')
target=assets/'model_qint8_avx2_reduce_range550.onnx'
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if sys.argv[-1]=='build':
    sys.path.insert(0,'D:/BAXYRuntime/experiments/python/onnx550')
    import onnx
    from onnxruntime.quantization import quantize_dynamic,QuantType
    from collections import Counter
    official=onnx.load(str(assets/'model_qint8_avx512_vnni.onnx'))
    summary={'official_operator_counts':dict(Counter(n.op_type for n in official.graph.node)),
             'official_int8_initializers':sum(x.data_type==3 for x in official.graph.initializer)}
    del official
    assert not target.exists()
    quantize_dynamic(str(assets/'model.onnx'),str(target),weight_type=QuantType.QInt8,per_channel=True,reduce_range=True,
                     op_types_to_quantize=['MatMul','Gather'],extra_options={'MatMulConstBOnly':True})
    summary.update(onnx_version=onnx.__version__,sha256=sha(target),bytes=target.stat().st_size)
    write(out/'BUILD.json',summary)
    raise SystemExit(0)
if len(sys.argv)>1:
    # Use the exact549 inference code; only private path and quantized graph differ.
    source=(root/'scratchpad/c03-e5-retrieval549.py').read_text(encoding='utf-8')
    source=source.replace('C03-e5-retrieval549-private','C03-e5-avx2550-private').replace('astra-e5-retrieval549','astra-e5-avx2550')
    source=source.replace('model_qint8_avx512_vnni.onnx',target.name)
    exec(compile(source,__file__,'exec'))
    raise SystemExit(0)
import psutil
sys.path.insert(0,str(root))
from scripts.measure_mind_budget import RamSampler
assert psutil.virtual_memory().available/2**20>2500
out.mkdir(exist_ok=False);private.mkdir(exist_ok=False)
previous=private.parent/'C03-e5-retrieval549-private'
for name in ('tools.json','documents.json'):(private/name).write_bytes((previous/name).read_bytes())
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'method':'Documented AVX2 non-VNNI saturation countermeasure: dynamic per-channel QInt8 with reduce_range=True; same official FP32 graph and MatMul/Gather ops, no calibration or owner training. ONNX1.22.0 installed only in external experiments/python/onnx550; production runtime unchanged. Run same effective-tokenizer549 inference and actual PlannerCatalog comparison with saved torch vectors549.',
 'source':'https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html#when-to-use-reduce-range-and-per-channel-quantization',
 'rationale':'The official downloaded file names AVX512_VNNI.549 showed numerical drift and206 top1 changes on Ryzen5800H. Saturation is a hypothesis, not established cause; no model rejection from that profile. Reduce range sacrifices one weight bit to prevent AVX2 intermediate saturation. If it does not improve quality, stop this bounded quantization line and retain production encoder.',
 'limits':{'free_ram_mib':768,'seconds_per_process':180},'acceptance':'Compare numerical drift, actual shortlist inclusion and ordering, RAM and warmed latency. No promotion solely for speed or cosine. Public model assets only; owner text remains local.'})
resources={}
for mode in ('build','int8'):
    with (out/(mode+'.log')).open('w',encoding='utf-8') as log:
        process=subprocess.Popen([sys.executable,'-X','utf8',__file__,mode],cwd=root,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        sampler=RamSampler(process.pid);sampler.start();started=time.monotonic();violations=[]
        try:
            while process.poll() is None:
                if time.monotonic()-started>180:violations.append('wall_time')
                if psutil.virtual_memory().available/2**20<768:violations.append('free_ram')
                if violations:process.kill();break
                time.sleep(.25)
            process.wait(timeout=20)
        finally:sampler.stop()
        resources[mode]={'exit_code':process.returncode,'peak_ram_mib':sampler.peak_mib,'seconds':time.monotonic()-started,'violations':violations}
        write(out/'RESOURCES.json',resources)
        assert process.returncode==0 and not violations
    print(mode+' complete',flush=True)
import numpy as np
from baxy_mind.planner import PlannerCatalog
rows=json.loads((private.parent/'C03-e5-backend547-private/queries.json').read_text(encoding='utf-8'))
tools=json.loads((private/'tools.json').read_text(encoding='utf-8'))
queries=np.load(private/'int8-queries.npy',allow_pickle=False)
passages=np.load(private/'int8-passages.npy',allow_pickle=False)
reference=np.load(previous/'torch-queries.npy',allow_pickle=False)
lookup={r['text']:queries[i] for i,r in enumerate(rows)}
def encode(texts,prefix='query'):return passages if prefix=='passage' else np.stack([lookup[s] for s in texts])
catalog=PlannerCatalog(tools,encoder=encode)
rankings=[[t.name for t in catalog.shortlist(r['text'])] for r in rows]
baseline=json.loads((previous/'shortlists.json').read_text(encoding='utf-8'))['torch']
changed=[r['case_id'] for r,a,b in zip(rows,baseline,rankings) if a!=b]
membership=[r['case_id'] for r,a,b in zip(rows,baseline,rankings) if set(a)!=set(b)]
first=[r['case_id'] for r,a,b in zip(rows,baseline,rankings) if a[0]!=b[0]]
write(out/'RESULT.json',{'resources':resources,'minimum_cosine':float((queries*reference).sum(1).min()),'mean_cosine':float((queries*reference).sum(1).mean()),'changed_order_case_ids':changed,'changed_membership_case_ids':membership,'changed_top1_case_ids':first,'timing':json.loads((private/'int8-timing.json').read_text(encoding='utf-8')),'adopted':False})
write(private/'shortlists.json',rankings)
print(json.dumps({'order_changes':len(changed),'membership_changes':len(membership),'top1_changes':len(first)}),flush=True)
