from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative: str):
    specification = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_stt_evaluator_freezes_final_contract_and_blind_engines() -> None:
    evaluator = load_module(
        "baxy_stt_reserved_evaluator",
        "experiments/stt_quality/evaluate_reserved_stt.py",
    )

    assert evaluator.CONTRACT_SCHEMA == "baxy.stt-evaluator-preopen-contract.v3"
    assert evaluator.REPORT_SCHEMA == "baxy.stt-real-audio-evaluation.v3"
    assert evaluator.THRESHOLDS["minds14"]["blind"]["expectedCases"] == 196
    assert evaluator.THRESHOLDS["audio_arena"]["blind"]["expectedCases"] == 50
    assert (
        evaluator._program_tree(ROOT)["sha256"]
        == evaluator.EXPECTED_PROGRAM_TREE_SHA256
    )
    audit = load_module(
        "baxy_stt_audit_fresh",
        "experiments/stt_quality/audit_fresh_postweight_stt_sources.py",
    )
    assert (
        audit._program_tree(ROOT)["sha256"] == audit.EXPECTED_PROGRAM_TREE_SHA256
    )
    assert audit.EXPECTED_PROGRAM_TREE_SHA256 == evaluator.EXPECTED_PROGRAM_TREE_SHA256
    historical = load_module(
        "baxy_stt_minds14_preregister",
        "experiments/stt_quality/preregister_minds14_stt_holdout.py",
    )
    # Campaign contracts keep their own tree pin. C02 must not rewrite them to
    # the current evaluator seal (1d3a69df…, lineage of goal095_09512_integrate.py).
    assert historical.EXPECTED_PROGRAM_TREE_SHA256 != evaluator.EXPECTED_PROGRAM_TREE_SHA256
    diagnostic = json.loads(
        (ROOT / "artifacts/audit/goals_01_10_20260903/program-tree-diagnostic.json").read_text(
            encoding="utf-8"
        )
    )
    assert diagnostic["expectedSeal"] == (
        "08300d7cec3ef1d770fb1a10c9a6de7e9d8fdf64e69c7a3be9c4bf4221a5fc7b"
    )
    assert diagnostic["expectedSeal"] != evaluator.EXPECTED_PROGRAM_TREE_SHA256


def test_bounded_streaming_completion_selector_is_conservative() -> None:
    fusion = load_module(
        "baxy_stt_fusion_evaluator",
        "experiments/stt_quality/fuse_empty_primary_stt_fallback.py",
    )

    assert fusion.use_fallback("", "abre spotify") == (True, "primary_empty")
    assert fusion.use_fallback(
        "I cannot get into my account",
        "It is not working now, I cannot get into my account",
    ) == (True, "bounded_primary_prefix_completed_by_streaming_fallback")
    assert fusion.use_fallback(
        "open spotify",
        "please send a message and then open spotify",
    ) == (False, "primary_retained")
    assert fusion.use_fallback(
        "this primary transcript already contains seven complete words now",
        "please this primary transcript already contains seven complete words now",
    ) == (False, "primary_retained")


def test_fusion_thresholds_keep_development_and_blind_counts_separate() -> None:
    fusion = load_module(
        "baxy_stt_fusion_thresholds",
        "experiments/stt_quality/fuse_empty_primary_stt_fallback.py",
    )

    assert fusion.thresholds("minds14", "development")["expectedCases"] == 84
    assert fusion.thresholds("minds14", "blind")["expectedCases"] == 196
    assert fusion.thresholds("audio_arena", "development")["expectedCases"] == 12
    assert fusion.thresholds("audio_arena", "blind")["expectedCases"] == 50


def test_blind_stt_verdict_rejects_without_reusing_the_holdout() -> None:
    summary = load_module(
        "baxy_stt_blind_campaign_summary",
        "experiments/stt_quality/summarize_blind_stt_campaign.py",
    )

    # The campaign binds each of its inputs by SHA-256; that binding is what
    # stops a blind partition being reopened, and it is checkable here.
    bound = summary.EXPECTED_INPUTS
    assert len(bound) == 7
    assert all(len(entry["sha256"]) == 64 for entry in bound.values())

    missing = sorted(
        entry["path"]
        for entry in bound.values()
        if not (ROOT / entry["path"]).is_file()
    )
    if missing:
        # The six blind partition results live under artifacts/validation/,
        # which .gitignore excludes on purpose so a consumed blind result
        # cannot be read back for tuning. Without them only the binding above
        # is checkable.
        pytest.skip(f"environment: blind campaign inputs absent ({len(missing)})")

    verdict = summary.build_verdict(ROOT)

    assert verdict["status"] == "failed"
    assert verdict["candidatePromoted"] is False
    assert verdict["blindPartitionsConsumed"] is True
    assert verdict["blindResultsAllowedForTuning"] is False
    assert verdict["thresholdsChangedAfterOpening"] is False
    assert verdict["results"]["minds14"]["minimumIntentSemanticPreservation"] == 0.99
    assert verdict["results"]["audioArena"]["minimumCriticalAnchorRecall"] == 0.99
    assert verdict["results"]["audioArena"]["criticalAnchors"] == 100
    assert verdict["results"]["audioArena"]["criticalAnchorsPreserved"] == 88
    assert verdict["effectsExecuted"] == 0


def _fake_mdc_page(module, language: str) -> tuple[str, list[str]]:
    expected = module.MDC_EXPECTED[language]
    samples = [
        *(f"private {language} question sample {index}" for index in range(5)),
        *(f"private {language} response sample {index}" for index in range(5)),
    ]
    dataset = {
        "@type": "sc:Dataset",
        "@id": expected["url"],
        "name": expected["name"],
        "citeAs": expected["citeAs"],
        "dateCreated": expected["dateCreated"],
        "datePublished": expected["datePublished"],
        "inLanguage": language,
        "license": "https://spdx.org/licenses/CC0-1.0.html",
        "version": module.COMMON_VOICE_SNAPSHOT,
        "contentSize": expected["contentBytes"],
    }
    page = f"""
    <script type="application/ld+json">{json.dumps(dataset)}</script>
    <p>This dataset contains {expected["clips"]:,} clips representing
    {expected["recordedHours"]} hours of recorded speech
    ({expected["validatedHours"]} hours validated) from
    {expected["speakers"]:,} speakers</p>
    <h3>Audio clips</h3>
    <p>Transcribed &amp; Validated {expected["validatedClips"]:,}</p>
    <p>Transcribed &amp; Pending {expected["pendingClips"]:,}</p>
    <p>Not transcribed {expected["untranscribedClips"]:,}</p>
    <h3>Training splits</h3>
    <p>Train {expected["trainClips"]:,}</p>
    <p>Dev {expected["devClips"]:,}</p>
    <p>Test {expected["testClips"]:,}</p>
    <p>Unassigned {expected["unassignedClips"]:,}</p>
    <h3>Transcriptions</h3>
    <p>{module.MDC_FORBIDDEN_USAGE}</p>
    <p>{expected["citeAs"]}.tar.gz</p>
    <h2>Questions</h2><ul>
    {"".join(f"<li>{sample}</li>" for sample in samples[:5])}
    </ul><h2>Responses</h2><ul>
    {"".join(f"<li>{sample}</li>" for sample in samples[5:])}
    </ul>
    """
    return page, samples


def test_fresh_postweight_source_audit_is_preacquisition_and_text_blind() -> None:
    audit_module = load_module(
        "baxy_fresh_postweight_stt_source_audit",
        "experiments/stt_quality/audit_fresh_postweight_stt_sources.py",
    )
    pages: dict[str, str] = {}
    private_samples: list[str] = []
    for language in ("es", "en"):
        page, samples = _fake_mdc_page(audit_module, language)
        pages[audit_module.MDC_EXPECTED[language]["url"]] = page
        private_samples.extend(samples)
    pages[audit_module.GIGASPEECHBENCH_API] = json.dumps(
        {
            "sha": audit_module.GIGASPEECHBENCH_COMMIT,
            "lastModified": audit_module.GIGASPEECHBENCH_LAST_MODIFIED,
            "gated": False,
            "private": False,
            "tags": [],
            "siblings": [
                {"rfilename": f"data/file-{index:03d}.parquet"} for index in range(155)
            ],
        }
    )

    audit = audit_module.build_audit(
        repository_root=ROOT,
        audited_at_utc="2026-08-11T00:00:00Z",
        fetch_text=pages.__getitem__,
    )

    serialized = json.dumps(audit, ensure_ascii=False)
    assert audit["status"] == "ready_pending_authenticated_common_voice_acquisition"
    assert audit["decision"]["selectedSource"] == (
        "Common Voice Spontaneous Speech 4.0"
    )
    assert audit["decision"]["spanishSufficientAloneForFinalCertification"] is False
    assert (
        audit["sources"]["gigaSpeechBench"]["eligibleForFinalCertifiedHoldout"] is False
    )
    assert audit["auditContract"]["audioDecoded"] is False
    assert audit["auditContract"]["referenceTranscriptsOpened"] is False
    assert audit["auditContract"]["candidatePromoted"] is False
    assert audit["effectsExecuted"] == 0
    assert audit["wakeProgramTree"]["sha256"] == (
        audit_module.EXPECTED_PROGRAM_TREE_SHA256
    )
    assert all(sample not in serialized for sample in private_samples)


def test_qwen3_onnx_evaluator_is_development_only_and_pins_official_asset() -> None:
    evaluator = load_module(
        "baxy_qwen3_asr_onnx_development",
        "experiments/stt_quality/evaluate_qwen3_asr_onnx_development.py",
    )

    parser = evaluator.build_parser()
    source = parser._option_string_actions["--source"]  # noqa: SLF001
    assert source.choices == ("audio_arena", "minds14")
    assert "--partition" not in parser._option_string_actions  # noqa: SLF001
    assert evaluator.OFFICIAL_ARCHIVE_BYTES == 878_702_423
    assert evaluator.OFFICIAL_ARCHIVE_SHA256 == (
        "393f8a14e2f5fb96746aaab342997a40641001fbd5bf9592a080a8329178ee96"
    )


def test_qwen3_model_tree_digest_is_order_independent() -> None:
    evaluator = load_module(
        "baxy_qwen3_asr_onnx_tree_digest",
        "experiments/stt_quality/evaluate_qwen3_asr_onnx_development.py",
    )
    first = {
        "b": {"bytes": 2, "sha256": "bb"},
        "a": {"bytes": 1, "sha256": "aa"},
    }
    second = dict(reversed(list(first.items())))

    assert evaluator.model_tree_sha256(first) == evaluator.model_tree_sha256(second)


def test_qwen3_development_verdict_rejects_without_opening_blind_data() -> None:
    summary = load_module(
        "baxy_qwen3_asr_onnx_development_verdict",
        "experiments/stt_quality/summarize_qwen3_asr_onnx_development.py",
    )

    verdict = summary.build_verdict(ROOT)

    assert verdict["status"] == "rejected"
    assert verdict["decision"]["candidatePromoted"] is False
    assert verdict["blindHoldoutOpened"] is False
    assert verdict["thresholdsChanged"] is False
    assert verdict["results"]["audioArena"]["criticalAnchors"] == 18
    assert verdict["results"]["audioArena"]["criticalAnchorsPreserved"] == 16
    assert verdict["results"]["minds14"]["uniqueIntentRescuesBeyondNemotron"] == []
    assert verdict["effectsExecuted"] == 0


def test_canary180m_evaluator_is_development_only_and_pins_official_asset() -> None:
    evaluator = load_module(
        "baxy_canary180m_onnx_development",
        "experiments/stt_quality/evaluate_canary180m_onnx_development.py",
    )

    parser = evaluator.build_parser()
    source = parser._option_string_actions["--source"]  # noqa: SLF001
    assert source.choices == ("audio_arena", "minds14")
    assert "--partition" not in parser._option_string_actions  # noqa: SLF001
    assert evaluator.OFFICIAL_ARCHIVE_BYTES == 153_692_328
    assert evaluator.OFFICIAL_ARCHIVE_SHA256 == (
        "7a38ed8b13f014ad632b09ff8d22e0c6f1359dd046af9235d281dfae841b9ab9"
    )


def test_canary180m_development_verdict_rejects_without_opening_blind_data() -> None:
    summary = load_module(
        "baxy_canary180m_onnx_development_verdict",
        "experiments/stt_quality/summarize_canary180m_onnx_development.py",
    )

    verdict = summary.build_verdict(ROOT)

    assert verdict["status"] == "rejected"
    assert verdict["decision"]["candidatePromoted"] is False
    assert verdict["blindHoldoutOpened"] is False
    assert verdict["thresholdsChanged"] is False
    assert verdict["results"]["audioArena"]["criticalAnchors"] == 18
    assert verdict["results"]["audioArena"]["criticalAnchorsPreserved"] == 14
    assert verdict["results"]["minds14"]["emptyTranscripts"] == 12
    assert verdict["results"]["minds14"]["uniqueIntentRescuesBeyondNemotron"] == []
    assert verdict["effectsExecuted"] == 0


def test_servicenow_codeswitch_preregistration_uses_physical_row_group_split() -> None:
    preregistration = load_module(
        "baxy_servicenow_codeswitch_preregistration",
        "experiments/stt_quality/preregister_servicenow_codeswitch_stt.py",
    )
    footer = {
        "rows": 259,
        "rowGroups": 3,
        "rowGroupRows": [100, 100, 59],
        "schemaNames": list(preregistration.EXPECTED_SCHEMA),
    }

    selection = preregistration.validate_footer(footer)

    assert selection["blind"]["rowGroups"] == [0, 1]
    assert selection["blind"]["rows"] == 200
    assert selection["development"]["rowGroups"] == [2]
    assert selection["development"]["rows"] == 59


def test_servicenow_codeswitch_extractor_is_development_row_group_only() -> None:
    extractor = load_module(
        "baxy_servicenow_codeswitch_extractor",
        "experiments/stt_quality/extract_servicenow_codeswitch_development.py",
    )

    assert extractor.DEVELOPMENT_ROW_GROUP == 2
    assert extractor.EXPECTED_DEVELOPMENT_ROWS == 59
    assert extractor.audio_suffix(b"RIFF\x00\x00\x00\x00WAVE") == ".wav"
    assert extractor.audio_suffix(b"ID3payload") == ".mp3"


def test_servicenow_codeswitch_language_alignment_attributes_reference_errors() -> None:
    evaluator = load_module(
        "baxy_servicenow_codeswitch_evaluator",
        "experiments/stt_quality/evaluate_servicenow_codeswitch_development.py",
    )

    counts = evaluator.reference_language_errors(
        ["hola", "open", "spotify"],
        ["ES", "EN", "EN"],
        ["hola", "opens", "spotify", "now"],
    )

    assert counts["ES"] == {"referenceTokens": 1, "errors": 0}
    assert counts["EN"] == {"referenceTokens": 2, "errors": 1}
