"""Registered model vs frozen Qwen3.5 payloads, no source/prompt changes."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import time
import urllib.request

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03/astra-runtime287'
model=Path(r'D:\BAXYRuntime\experiments\models\qwen3-4b-instruct-2507-a06e946b\Qwen3-4B-Instruct-2507-Q4_K_M.gguf')
binary=Path(r'D:\BAXYRuntime\assets\llama-b9980-cuda12.4\llama-server.exe')
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()
hashes={'model':sha(model),'server':sha(binary),'manifest':sha(manifest)}
assert hashes['model']=='3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'
assert hashes['manifest']=='13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
args=[str(binary),'-m',str(model),'--host','127.0.0.1','--port','57485','-ngl','99','-c','12288','-b','2048','-ub','256','-fa','on','-ctk','q8_0','-ctv','q8_0','-np','3','--jinja','--reasoning','off','--reasoning-budget','0','--cont-batching']
prereg={'utc':datetime.now(timezone.utc).isoformat(),'method':'Only model changes from Qwen3.5 override to existing registered Qwen3-2507. Identical serialized payloads286, same llama binary/ctx/batch/KV/slots. No model promotion, no UI or effects. Compare raw replies for refusal/factuality and finish_reason; one case does not certify C03.', 'hashes':hashes,'args':args,
    'criteria':'Production baseline must answer stable visiting request with real named places and no unsupported limitation, invented landmarks, current access guarantees or truncation. Diagnostic deletions cannot substitute for production baseline.'}
(out/'MODEL_PREREG.json').write_text(json.dumps(prereg,indent=2)+'\n',encoding='utf-8')
prior=json.loads((root/'artifacts/comprobaciones/C03/astra-chat286/RESULT.json').read_text(encoding='utf-8'))
log=(out/'server2507.log').open('wb')
process=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
(out/'PROCESS.json').write_text(json.dumps({'pid':process.pid,'startUtc':datetime.now(timezone.utc).isoformat(),'owned':True})+'\n',encoding='utf-8')
results=[]
try:
    deadline=time.monotonic()+75
    while True:
        assert process.poll() is None, 'Server exited.'
        try:
            with urllib.request.urlopen('http://127.0.0.1:57485/health',timeout=1) as response:
                if response.status==200:
                    break
        except Exception:
            if time.monotonic()>deadline:
                raise TimeoutError('Model readiness exceeded75s')
            time.sleep(.25)
    for row in prior:
        with urllib.request.urlopen('http://127.0.0.1:57485/slots',timeout=5) as response:
            assert not any(item['is_processing'] for item in json.load(response))
        request=urllib.request.Request('http://127.0.0.1:57485/v1/chat/completions',data=json.dumps(row['payload'],ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=90) as response:
            result=json.load(response)
        record={'variant':row['variant'],'payload':row['payload'],'response':result}
        results.append(record)
        (out/'MODEL_RESULT.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'variant':row['variant'],'answer':result['choices'][0]['message'],'finish':result['choices'][0]['finish_reason']},ensure_ascii=True),flush=True)
finally:
    process.terminate()
    process.wait(timeout=10)
    log.close()
    (out/'MODEL_STOP.json').write_text(json.dumps({'pid':process.pid,'exitCode':process.returncode,'utc':datetime.now(timezone.utc).isoformat()})+'\n',encoding='utf-8')
