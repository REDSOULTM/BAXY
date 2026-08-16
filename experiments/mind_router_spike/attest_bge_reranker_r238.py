"""Attest isolated R237 reranker weights without importing the model."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
REPO=Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:sys.path.insert(0,str(REPO))
from experiments.mind_router_spike import preregister_bge_reranker_r237 as r237
OUTPUT=REPO/'artifacts/audit/bge_reranker_r238.json'
def sha(path:Path)->str:
 h=hashlib.sha256()
 with path.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 return h.hexdigest()
def build()->dict[str,object]:
 prereg=json.loads(r237.OUTPUT.read_text(encoding='utf-8'))
 if prereg!=r237.build() or not r237.ROOT.is_dir():raise RuntimeError('R238 requires frozen R237 candidate')
 files=[];merkle=hashlib.sha256()
 for p in sorted(r237.ROOT.rglob('*')):
  if p.is_file() and '.cache' not in p.relative_to(r237.ROOT).parts:
   item={'path':p.relative_to(r237.ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)};files.append(item);merkle.update((item['path']+'\0'+item['sha256']+'\n').encode())
 if not files:raise RuntimeError('R238 candidate empty')
 return {'schema':'baxy.bge-reranker.r238-attestation.v1','authority':'weights_attested_without_model_import','candidate':{'model':f'{r237.MODEL}@{r237.REVISION}','files':len(files),'bytes':sum(x['bytes'] for x in files),'merkle_sha256':merkle.hexdigest()},'constraints':{'model_imported':False,'model_started':False,'r228_opened':False,'registered_runtime_modified':False,'providers_enabled':False,'effects_executed':0,'opened_v9':False,'voice_stt_wake_exercised':False},'identities':{'r237_sha256':sha(r237.OUTPUT),'program_sha256':sha(Path(__file__))}}
def main()->int:
 if OUTPUT.exists():raise RuntimeError('refusing to overwrite R238')
 OUTPUT.write_bytes((json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode());return 0
if __name__=='__main__':raise SystemExit(main())
