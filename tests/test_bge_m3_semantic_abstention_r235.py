from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/preregister_bge_m3_semantic_abstention_r235.py"
RUNNER = ROOT / "experiments/mind_router_spike/run_bge_m3_semantic_abstention_r236.py"


def _module():
    spec = importlib.util.spec_from_file_location("r235", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r235_seals_semantic_abstention_before_model_import() -> None:
    report = _module().build()
    assert report["candidate"]["score"] == "maximum normalized dense cosine over family documents"
    assert report["candidate"]["threshold_rule"] == "next representable value below the minimum selected public in-catalog score"
    assert report["development_population"]["r228_used"] is False
    assert report["constraints"]["opened_v9"] is False
    assert "SentenceTransformer" not in SOURCE.read_text(encoding="utf-8")
    assert "sentence_transformers" in RUNNER.read_text(encoding="utf-8")


def test_r236_published_cpu_probe_preserves_r235_identities() -> None:
    result = json.loads(
        (
            ROOT / "artifacts/development/bge_m3_semantic_abstention_r236.json"
        ).read_text(encoding="utf-8")
    )
    assert result["identities"]["program_sha256"]
    assert result["constraints"]["r228_opened"] is False
    assert result["constraints"]["opened_v9"] is False
    assert result["observed"]["inside_rows_lost"] == 0
    assert result["observed"]["outside_zero_candidates"] == 15
