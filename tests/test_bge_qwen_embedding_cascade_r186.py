"""Structural contract for R186/R187."""
from __future__ import annotations
import json
from pathlib import Path

from sealed_evidence import assert_sealed

ROOT=Path(__file__).resolve().parents[1]
ARTIFACT=ROOT/'artifacts/development/bge_qwen_embedding_cascade_r186_preregistration.json'
ARTIFACT_SEAL='5bddd16566865f789a428a4f27afaa2cf236945d94d0f7c055e15406435e39ed'


def test_r186_freezes_union_and_shared_oos() -> None:
    # The builder needs artifacts/development/bge_m3_operation_recovery_r160_attested.json,
    # a consumed R160 attestation that survives in no repository of this project.
    # The preregistration it produced is published, so it is read and sealed (§7).
    assert_sealed(ARTIFACT, ARTIFACT_SEAL)
    report=json.loads(ARTIFACT.read_text(encoding='utf-8'))
    assert report['candidate']['retrieval']['qwen_embedding_top_k']==5
    assert report['population']=={'model_owned_rows':77,'shared_oos_rows':9,'offered_operations_min':12,'offered_operations_max':30,'offered_operations_median':22}
    assert report['constraints']['opened_v9'] is False
