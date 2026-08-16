"""Seal isolated acquisition of the multilingual cross-encoder reranker."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
OUTPUT=REPO/'artifacts/development/bge_reranker_r237.preregistration.json'
R234=REPO/'artifacts/audit/turn_evidence_restoration_r234.json'
R228=REPO/'artifacts/holdout/situated_cut_b_r228.jsonl'
MODEL='BAAI/bge-reranker-v2-m3'
REVISION='953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e'
ROOT=Path(r'D:\BAXYRuntime\candidates\BAAI--bge-reranker-v2-m3')
def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def build()->dict[str,object]:
    restoration=json.loads(R234.read_text(encoding='utf-8'))
    if restoration['runtime_corpus']['sha256']!='8abff5805a93615c6f5a655b9af5559063e34226cfc0db58c5547d97a70ee680':raise RuntimeError('R237 requires canonical development corpus')
    return {'schema':'baxy.bge-reranker.r237-acquisition-preregistration.v1','authority':'sealed_before_external_weight_acquisition_or_model_start','candidate':{'model_id':MODEL,'revision':REVISION,'storage':str(ROOT),'architecture':'multilingual_cross_encoder_query_operation_relevance','runtime_integration':'none'},'future_measurement':{'calibration':'public development corpus only','r228_used':False,'public_holdout_used':False,'oos_requires_zero_candidates':True,'raw_scores_before_threshold':True},'constraints':{'model_started':False,'providers_enabled':False,'effects_executed':0,'opened_v9':False,'voice_stt_wake_exercised':False},'identities':{'r234_sha256':sha(R234),'r228_sha256':sha(R228),'program_sha256':sha(Path(__file__))}}
def main()->int:
    if OUTPUT.exists():raise RuntimeError(f'refusing to overwrite preregistration: {OUTPUT}')
    OUTPUT.write_bytes((json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode('utf-8'));return 0
if __name__=='__main__':raise SystemExit(main())
