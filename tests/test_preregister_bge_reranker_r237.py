from __future__ import annotations
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'experiments/mind_router_spike/preregister_bge_reranker_r237.py'
def test_r237_seals_cross_encoder_before_acquisition()->None:
 spec=importlib.util.spec_from_file_location('r237',SOURCE);assert spec and spec.loader;module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);report=module.build();assert report['candidate']['architecture']=='multilingual_cross_encoder_query_operation_relevance';assert report['future_measurement']['r228_used'] is False;assert report['constraints']['model_started'] is False
