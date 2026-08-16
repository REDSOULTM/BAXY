"""Seal the public-development calibration of the isolated reranker."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
REPO=Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:sys.path.insert(0,str(REPO))
from experiments.mind_router_spike import attest_bge_reranker_r238 as r238
R234=REPO/'artifacts/audit/turn_evidence_restoration_r234.json'; R228=REPO/'artifacts/holdout/situated_cut_b_r228.jsonl'; OUTPUT=REPO/'artifacts/development/bge_reranker_calibration_r239.preregistration.json'
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def build()->dict[str,object]:
 a=json.loads(r238.OUTPUT.read_text(encoding='utf-8'));r=json.loads(R234.read_text(encoding='utf-8'))
 if a['candidate']['merkle_sha256']!='50d52ffd408e81baf7d0aa55b1ecbd8be05d7f4091773f1b71833b852e3c4249' or r['runtime_corpus']['rows']!=25156:raise RuntimeError('R239 inputs changed')
 return {'schema':'baxy.bge-reranker.r239-calibration-preregistration.v1','authority':'sealed_before_model_import','candidate':{'model':'BAAI/bge-reranker-v2-m3@953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e','score':'sigmoid cross-encoder relevance query-to-typed-family-document','abstention':'zero candidates below threshold'},'development':{'inside':256,'outside':256,'sources':['PRESTO v1','MASSIVE v1'],'threshold':'nextafter below minimum inside score; outside excluded from selection','r228_used':False,'public_holdout_used':False},'constraints':{'model_started':False,'r228_opened':False,'opened_v9':False,'effects_executed':0,'providers_enabled':False,'voice_stt_wake_exercised':False},'identities':{'r238_sha256':sha(r238.OUTPUT),'r234_sha256':sha(R234),'r228_sha256':sha(R228),'program_sha256':sha(Path(__file__))}}
def main()->int:
 if OUTPUT.exists():raise RuntimeError('refusing to overwrite R239')
 OUTPUT.write_bytes((json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode());return 0
if __name__=='__main__':raise SystemExit(main())
