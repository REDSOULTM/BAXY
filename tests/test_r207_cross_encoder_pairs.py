from __future__ import annotations
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_r207_builds_balanced_binary_operation_pairs(tmp_path:Path):
 s=importlib.util.spec_from_file_location('r207',ROOT/'experiments/mind_router_spike/build_r207_cross_encoder_pairs.py');assert s and s.loader;m=importlib.util.module_from_spec(s);s.loader.exec_module(m);r=m.build(tmp_path/'pairs.jsonl',tmp_path/'audit.json')
 assert r['counts']=={'pairs':23700,'positive_pairs':4740,'negative_pairs':18960,'labels':170,'evaluation_overlap_claimed':0}
