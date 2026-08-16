"""Structural contract for R186/R187."""
from __future__ import annotations
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'experiments/mind_router_spike/preregister_bge_qwen_embedding_cascade_r186.py'
def test_r186_freezes_union_and_shared_oos() -> None:
    spec=importlib.util.spec_from_file_location('r186',SOURCE); assert spec and spec.loader
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); report=module.build(ROOT)
    assert report['candidate']['retrieval']['qwen_embedding_top_k']==5
    assert report['population']=={'model_owned_rows':77,'shared_oos_rows':9,'offered_operations_min':12,'offered_operations_max':30,'offered_operations_median':22}
    assert report['constraints']['opened_v9'] is False
