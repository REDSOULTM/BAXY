"""Numerical and memory comparison of the same E5 checkpoint, outside product."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
import time

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-e5-backend547-private'
out=root/'artifacts/comprobaciones/C03/astra-e5-backend547'
assets=Path('D:/BAXYRuntime/experiments/models/e5-onnx-614241f6')
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

if len(sys.argv)>1:
    import numpy as np
    from baxy_mind.router import SemanticEncoder, _verified_encoder_snapshot
    mode=sys.argv[1]
    rows=json.loads((private/'queries.json').read_text(encoding='utf-8'))
    started=time.perf_counter()
    snapshot,identity=_verified_encoder_snapshot()
    if mode=='torch':
        encoder=SemanticEncoder()
        encode=lambda texts:encoder.encode(texts,prefix='query')
        details={'max_seq_length':encoder._model.max_seq_length,
                 'torch_threads':__import__('torch').get_num_threads()}
        assert details['max_seq_length']==512
    else:
        import onnxruntime as ort
        from tokenizers import Tokenizer
        tokenizer=Tokenizer.from_file(str(snapshot/'tokenizer.json'))
        tokenizer.enable_truncation(max_length=512)
        special=json.loads((snapshot/'special_tokens_map.json').read_text(encoding='utf-8'))
        pad=special['pad_token']
        if isinstance(pad,dict):pad=pad['content']
        pad_id=tokenizer.token_to_id(pad)
        assert isinstance(pad_id,int)
        tokenizer.enable_padding(pad_id=pad_id,pad_token=pad)
        options=ort.SessionOptions()
        options.intra_op_num_threads=8
        options.inter_op_num_threads=1
        options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
        filename='model.onnx' if mode=='onnx-fp32' else 'model_qint8_avx512_vnni.onnx'
        expected={'onnx-fp32':'ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665',
                  'onnx-int8':'dd476dd0c2514e9b9be83aeb3853fac0763e0bdf4a71645407587d77c48a2d88'}[mode]
        assert sha(assets/filename)==expected
        session=ort.InferenceSession(str(assets/filename),sess_options=options,providers=['CPUExecutionProvider'])
        names=[node.name for node in session.get_inputs()]
        assert {'input_ids','attention_mask'}<=set(names)<={'input_ids','attention_mask','token_type_ids'}
        def encode(texts):
            encoded=tokenizer.encode_batch(['query: '+text for text in texts])
            ids=np.asarray([x.ids for x in encoded],dtype=np.int64)
            mask=np.asarray([x.attention_mask for x in encoded],dtype=np.int64)
            feed={'input_ids':ids,'attention_mask':mask}
            if 'token_type_ids' in names:
                feed['token_type_ids']=np.asarray([x.type_ids for x in encoded],dtype=np.int64)
            tokens=session.run(None,feed)[0]
            assert tokens.shape[:2]==ids.shape and tokens.shape[2]==384
            weights=mask[...,None].astype(np.float32)
            pooled=(tokens*weights).sum(axis=1)/weights.sum(axis=1)
            return pooled/np.linalg.norm(pooled,axis=1,keepdims=True)
        details={'providers':session.get_providers(),'inputs':names,'graph_sha256':expected,
                 'intra_threads':8,'inter_threads':1,'pooling':'attention-mask mean then L2 norm',
                 'tokenizer_sha256':sha(snapshot/'tokenizer.json')}
    load_seconds=time.perf_counter()-started
    vectors=[]
    durations=[]
    for start in range(0,len(rows),8):
        before=time.perf_counter()
        value=encode([row['text'] for row in rows[start:start+8]])
        durations.append(time.perf_counter()-before)
        assert value.shape==(min(8,len(rows)-start),384) and np.isfinite(value).all()
        vectors.append(value.astype(np.float32))
    np.save(private/(mode+'.npy'),np.concatenate(vectors))
    write(private/(mode+'.json'),{'load_seconds':load_seconds,'batch_seconds':durations,
          'encode_seconds':sum(durations),'queries':len(rows),'details':details,
          'torch_imported':'torch' in sys.modules,'identity':identity.public_dict()})
    print(mode+' encoded '+str(len(rows))+' queries',flush=True)
    raise SystemExit(0)

import psutil
sys.path.insert(0,str(root))
from scripts.measure_mind_budget import RamSampler
assert psutil.virtual_memory().available/2**20>2500
private.mkdir(exist_ok=False)
out.mkdir(exist_ok=False)
registry=private.parent/'C03-survey-requirements336-private/requirements.jsonl'
with registry.open(encoding='utf-8-sig') as stream:
    all_rows=list(map(json.loads,stream))
rows=[{'case_id':r['case_id'],'text':r['literal']} for r in all_rows if 0<len(r['literal'])<=4096]
excluded=[r['case_id'] for r in all_rows if not 0<len(r['literal'])<=4096]
write(private/'queries.json',rows)
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),
 'method':'Separate local processes: current SemanticEncoder CPU torch, official ONNX FP32, official INT8. Same immutable E5 revision/tokenizer, query prefix,512token limit, attention-mask mean/L2 normalization and384dimensions. Batch8 throughput and total process RSS; not interactive-turn latency, cold-boot latency or whole BAXY budget. No generator/process concurrently launched by this harness.',
 'sources':['https://www.sbert.net/docs/sentence_transformer/usage/efficiency.html','https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html'],
 'profile':'CPUExecutionProvider,8intra-op threads for8physical cores,1inter-op thread,sequential. Torch keeps current product defaults and records effective thread count. INT8 artifact namedAVX512_VNNI is only a portability/quality probe on AVX2, not final optimal AMD profile.',
 'cases':len(rows),'excluded_over_encoder_contract':excluded,'registry_sha256':sha(registry),
 'queries_sha256':sha(private/'queries.json'),'authorization':'AUTORIZACION_DUENO_536.md; consumed development data, never blind acceptance.',
 'criteria':'FP32 embedding equivalence first; report all numerical drift and nearest frozen-bank entry changes forINT8. Frozen intent-bank nearest entry is a diagnostic, not product operation authority or proof of correct retrieval. No adoption without actual operation-retrieval/product regression. No relaxed routing thresholds or replaced frozen vectors.',
 'limits':{'minimum_free_ram_mib':768,'process_seconds':360},
 'privacy':'Public graphs already downloaded544; all owner messages and vectors remain local; child processes offline.'})
summary={}
for mode in ('torch','onnx-fp32','onnx-int8'):
    env=os.environ.copy()
    env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
    with (out/(mode+'.log')).open('w',encoding='utf-8') as log:
        process=subprocess.Popen([sys.executable,'-X','utf8',__file__,mode],cwd=root,env=env,
                                 stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        sampler=RamSampler(process.pid)
        sampler.start()
        before=time.monotonic()
        violations=[]
        try:
            while process.poll() is None:
                if time.monotonic()-before>360:violations.append('time_limit')
                if psutil.virtual_memory().available/2**20<768:violations.append('low_free_ram')
                if violations:
                    process.kill()
                    break
                time.sleep(.25)
            process.wait(timeout=20)
        finally:
            sampler.stop()
        summary[mode]={'exit_code':process.returncode,'ram_peak_mib':sampler.peak_mib,
                       'seconds':time.monotonic()-before,'violations':violations}
        write(out/'RESOURCES.json',summary)
        assert process.returncode==0 and not violations,mode
    print(mode+' complete',flush=True)
import numpy as np
reference=np.load(private/'torch.npy',allow_pickle=False)
pool=np.load(root/'src/baxy_mind/data/intent_bank.embeddings.npy',allow_pickle=False)
reference_nearest=np.argmax(reference@pool.T,axis=1)
comparison={}
for mode in ('onnx-fp32','onnx-int8'):
    vectors=np.load(private/(mode+'.npy'),allow_pickle=False)
    cosine=(reference*vectors).sum(axis=1)/(np.linalg.norm(reference,axis=1)*np.linalg.norm(vectors,axis=1))
    changed=np.flatnonzero(reference_nearest!=np.argmax(vectors@pool.T,axis=1))
    comparison[mode]={'minimum_cosine':float(cosine.min()),'mean_cosine':float(cosine.mean()),
                      'max_abs_component_error':float(np.abs(reference-vectors).max()),
                      'nearest_bank_entry_changes':int(len(changed)),
                      'changed_case_ids':[rows[int(i)]['case_id'] for i in changed]}
write(out/'RESULT.json',{'resources':summary,'numerical_comparison':comparison,
      'timing':{mode:json.loads((private/(mode+'.json')).read_text(encoding='utf-8')) for mode in summary},
      'product_modified':False,'adoption':'pending actual retrieval and product evidence'})
print(json.dumps(comparison),flush=True)
