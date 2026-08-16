import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'experiments/mind_router_spike/preregister_bge_reranker_calibration_r239.py'
def test_r239_seals_calibration_without_opening_r228():
 s=importlib.util.spec_from_file_location('r239',SOURCE);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);r=m.build();assert r['development']['r228_used'] is False;assert r['constraints']['model_started'] is False
