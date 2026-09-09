"""One synthetic training-only example serialized by the existing composer."""
from pathlib import Path
import copy
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from baxy_mind.llm import LlmRuntime

class Captured(Exception):
    pass
class Recorder(LlmRuntime):
    def __init__(self):
        self._gguf='Qwen3-4B-Instruct-2507-Q4_K_M.gguf'
        self.payload=None
    def _post(self,payload):
        self.payload=copy.deepcopy(payload)
        raise Captured()

request='¿Cómo está el sonido? Answer in Spanglish.'
situation={'kind':'operation','operation':'audio.status','polarity':'success','verified':True,'succeeded':True,
           'observed':{'operation':'audio.status','state':{'volumePercent':38,'muted':False}}}
recorder=Recorder()
try:
    recorder.compose_user_message(request,'status',{'situation':json.dumps(situation)})
except Captured:
    pass
assert recorder.payload
data={'kind':'synthetic-training-only-memory-smoke-not-quality-evaluation','messages':recorder.payload['messages'],
      'answer':'El volumen está al 38%; audio is not muted.',
      'llmSha256':hashlib.sha256((ROOT/'src/baxy_mind/llm.py').read_bytes()).hexdigest(),
      'provenance':'Authored synthetic facts, never a PC observation; use only for three optimizer steps. Not acceptance or quality evidence.'}
out=ROOT/'artifacts/comprobaciones/C03/astra-lora-smoke-input.json'
assert not out.exists()
out.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'path':str(out),'messages':len(data['messages'])},ensure_ascii=False))
