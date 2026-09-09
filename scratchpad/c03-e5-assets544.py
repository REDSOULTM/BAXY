"""Acquire immutable official E5 graphs for an isolated resource comparison."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import urllib.request

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03/astra-e5-assets544'
out.mkdir(exist_ok=False)
destination=Path('D:/BAXYRuntime/experiments/models/e5-onnx-614241f6')
destination.mkdir(exist_ok=True)
revision='614241f622f53c4eeff9890bdc4f31cfecc418b3'
files={
 'model.onnx':(470268510,'ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665'),
 'model_qint8_avx512_vnni.onnx':(118346824,'dd476dd0c2514e9b9be83aeb3853fac0763e0bdf4a71645407587d77c48a2d88'),
}
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
write(out/'PREREG.json',{
 'utc':datetime.now(timezone.utc).isoformat(),
 'purpose':'Measured product543 encoder worker858.63MiB exceeds native generator720.71MiB. Resource pressure aborted541. Before larger generator or lower quality, compare same pinned E5 encoder through official ONNX FP32 and official INT8 graphs. Acquisition only; do not alter registered runtime, current encoder, caches, catalog or corpus.',
 'revision':revision,'files':files,
 'official_metadata':'https://huggingface.co/api/models/intfloat/multilingual-e5-small/tree/'+revision+'/onnx',
 'primary_sources':['https://www.sbert.net/docs/sentence_transformer/usage/efficiency.html','https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html','https://huggingface.co/intfloat/multilingual-e5-small/tree/'+revision],
 'inheritance':'Current SemanticEncoder uses pinned SentenceTransformer CPU FP32. encoder-cache-inheritance.json records25156 cached embeddings with query prefix/normalization/384dimensions; preserve semantics. No previous ONNX encoder comparison found in scoped filenames and index; that is a bounded search, not proof of absence.',
 'platform_caveat':'Published INT8 graph is named avx512_vnni; Ryzen5800H uses AVX2. It is a portable ONNX candidate, not an optimized AMD verdict. Inspect operators/configuration and use documented AVX2/U8U8 or reduced range if saturation appears; do not discard quantization from inappropriate defaults. FP32 direct backend is the first equivalence control.',
 'next_criteria':'Preserve tokenizer, max512 tokens, query/passage prefixes, masked mean pooling and L2 normalization. Compare embeddings and ranking on owner-authorized local messages and frozen vectors, recording drift and candidate changes. Measure RAM/latency in separate processes. No adoption from file size or benchmark speed alone.',
 'privacy':'Only public model asset URLs leave the machine; no user content, vectors, transcripts or logs are uploaded.',
 'destination':str(destination)})
result=[]
for filename,(size,digest) in files.items():
    path=destination/filename
    if path.exists():
        with path.open('rb') as handle:actual=hashlib.file_digest(handle,'sha256').hexdigest()
        assert path.stat().st_size==size and actual==digest
        result.append({'path':str(path),'bytes':size,'sha256':actual,'downloaded':False})
        continue
    temporary=destination/(filename+'.partial544')
    assert not temporary.exists()
    url='https://huggingface.co/intfloat/multilingual-e5-small/resolve/'+revision+'/onnx/'+filename+'?download=true'
    request=urllib.request.Request(url,headers={'User-Agent':'BAXY-local-model-evaluation'})
    total=0
    running=hashlib.sha256()
    with urllib.request.urlopen(request,timeout=45) as response, temporary.open('xb') as handle:
        while chunk:=response.read(4*1024*1024):
            total+=len(chunk)
            assert total<=size
            handle.write(chunk)
            running.update(chunk)
    assert total==size and running.hexdigest()==digest
    os.replace(temporary,path)
    result.append({'path':str(path),'bytes':total,'sha256':digest,'downloaded':True})
    print('Verified '+filename+' '+str(total)+' bytes',flush=True)
write(out/'RESULT.json',{'verified_assets':result,'runtime_modified':False,'benchmark_run':False})
print('Official assets ready; numerical and resource comparison still pending.',flush=True)
