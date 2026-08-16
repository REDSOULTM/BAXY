from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCORER_PATH = ROOT / "experiments/stt_quality/msner_entity_scoring.py"
EVALUATOR_PATH = (
    ROOT / "experiments/stt_quality/evaluate_msner_spanish_entity_development.py"
)
EXTRACTOR_PATH = (
    ROOT / "experiments/stt_quality/extract_msner_spanish_entity_development.py"
)
PREREGISTER_PATH = (
    ROOT / "experiments/stt_quality/preregister_msner_spanish_entity_stt.py"
)
ANALYZER_PATH = (
    ROOT / "experiments/stt_quality/analyze_msner_spanish_parakeet_failure.py"
)
NEMOTRON_EVALUATOR_PATH = (
    ROOT / "experiments/stt_quality/evaluate_msner_spanish_nemotron_development.py"
)
NEMOTRON_ANALYZER_PATH = (
    ROOT / "experiments/stt_quality/analyze_msner_nemotron_comparison.py"
)
NUMERIC_SEMANTICS_PATH = (
    ROOT / "experiments/stt_quality/spanish_numeric_semantics.py"
)
NUMERIC_EVALUATOR_PATH = (
    ROOT
    / "experiments/stt_quality/evaluate_msner_spanish_numeric_semantic_development.py"
)
CONTEXTUAL_HOTWORDS_PATH = (
    ROOT / "experiments/stt_quality/contextual_hotwords.py"
)
CONTEXTUAL_ORACLE_EVALUATOR_PATH = (
    ROOT
    / "experiments/stt_quality/evaluate_msner_spanish_contextual_hotword_oracle.py"
)
CONTEXTUAL_ORACLE_MATRIX_PATH = (
    ROOT
    / "experiments/stt_quality/evaluate_msner_spanish_contextual_hotword_oracle_matrix.py"
)
FASTER_WHISPER_EVALUATOR_PATH = (
    ROOT
    / "experiments/stt_quality/evaluate_msner_spanish_faster_whisper_development.py"
)
DUAL_ASR_CEILING_PATH = (
    ROOT
    / "experiments/stt_quality/analyze_msner_spanish_dual_asr_ceiling_development.py"
)
ONNX_TDT_BOOSTING_PATH = (
    ROOT / "experiments/stt_quality/onnx_tdt_phrase_boosting.py"
)
ONNX_TDT_BOOSTING_EVALUATOR_PATH = (
    ROOT
    / "experiments/stt_quality/evaluate_msner_spanish_onnx_phrase_boosting_development.py"
)


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


scorer = _load("test_msner_entity_scorer", SCORER_PATH)
evaluator = _load("test_msner_entity_evaluator", EVALUATOR_PATH)
extractor = _load("test_msner_entity_extractor", EXTRACTOR_PATH)
preregister = _load("test_msner_entity_preregister", PREREGISTER_PATH)
analyzer = _load("test_msner_entity_failure_analyzer", ANALYZER_PATH)
nemotron_evaluator = _load(
    "test_msner_nemotron_evaluator", NEMOTRON_EVALUATOR_PATH
)
nemotron_analyzer = _load(
    "test_msner_nemotron_analyzer", NEMOTRON_ANALYZER_PATH
)
numeric_semantics = _load(
    "test_msner_numeric_semantics", NUMERIC_SEMANTICS_PATH
)
numeric_evaluator = _load(
    "test_msner_numeric_evaluator", NUMERIC_EVALUATOR_PATH
)
contextual_hotwords = _load(
    "test_msner_contextual_hotwords", CONTEXTUAL_HOTWORDS_PATH
)
contextual_oracle = _load(
    "test_msner_contextual_oracle", CONTEXTUAL_ORACLE_EVALUATOR_PATH
)
contextual_matrix = _load(
    "test_msner_contextual_matrix", CONTEXTUAL_ORACLE_MATRIX_PATH
)
faster_whisper_evaluator = _load(
    "test_msner_faster_whisper_evaluator", FASTER_WHISPER_EVALUATOR_PATH
)
dual_asr_ceiling = _load(
    "test_msner_dual_asr_ceiling", DUAL_ASR_CEILING_PATH
)
onnx_tdt_boosting = _load(
    "test_msner_onnx_tdt_boosting", ONNX_TDT_BOOSTING_PATH
)
onnx_tdt_boosting_evaluator = _load(
    "test_msner_onnx_tdt_boosting_evaluator",
    ONNX_TDT_BOOSTING_EVALUATOR_PATH,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Consejo —con la Comisión—.", ["Consejo", "—", "con", "la", "Comisión", "—."]),
        ("el4,8% del presupuesto", ["el", "4", ",", "8", "%", "del", "presupuesto"]),
        ("desarrollar el 5G", ["desarrollar", "el", "5", "G"]),
        ("un76%", ["un", "76", "%"]),
    ],
)
def test_corpus_tokenizer_reproduces_letters_digits_and_punctuation_groups(
    text: str, expected: list[str]
) -> None:
    assert [token.text for token in scorer.corpus_tokens(text)] == expected
    assert "".join(token.text for token in scorer.corpus_tokens(text)) == "".join(
        text.split()
    )


def test_entity_spans_preserve_reference_surface_and_bio_boundaries() -> None:
    person = scorer.UNIFIED_ENTITY_LABELS.index("B-person")
    person_inside = scorer.UNIFIED_ENTITY_LABELS.index("I-person")
    outside = scorer.UNIFIED_ENTITY_LABELS.index("O")
    reference = "Habló Ana María, hoy."
    labels = [outside, person, person_inside, outside, outside, outside]

    entities = scorer.extract_entities(reference, labels)

    assert [(entity.entity_type, entity.surface) for entity in entities] == [
        ("person", "Ana María")
    ]


def test_entity_scoring_separates_exact_phrase_and_token_recall() -> None:
    organization = scorer.UNIFIED_ENTITY_LABELS.index("B-organization")
    organization_inside = scorer.UNIFIED_ENTITY_LABELS.index("I-organization")
    outside = scorer.UNIFIED_ENTITY_LABELS.index("O")

    score = scorer.score_entity_preservation(
        reference="Visité Banco Central Europeo hoy",
        label_ids=[outside, organization, organization_inside, organization_inside, outside],
        hypothesis="visité banco central hoy",
        normalize_tokens=lambda text: text.casefold().split(),
    )

    assert score["entities"] == 1
    assert score["entitiesExactlyPreserved"] == 0
    assert score["entityTokens"] == 3
    assert score["entityTokensPreserved"] == 2


def test_bio_sequence_rejects_orphan_inside_label() -> None:
    inside = scorer.UNIFIED_ENTITY_LABELS.index("I-person")
    with pytest.raises(ValueError, match="msner_entity_bio_invalid"):
        scorer.extract_entities("Ana", [inside])


def test_partition_roles_and_sources_are_permanently_disjoint() -> None:
    assert preregister.COMMIT == "304333fb5eba28fcc72a4ad543cb779a33dbc767"
    assert preregister.SHARDS["development"]["path"].startswith("data/es-00000-")
    assert preregister.SHARDS["validationBlind"]["path"].startswith("data/es-00001-")
    assert preregister.SHARDS["finalBlind"]["path"].startswith("data/es-00002-")
    assert extractor.ROW_GROUPS == [0, 1, 2, 3, 4, 5]
    assert extractor.EXPECTED_ROWS == evaluator.EXPECTED_CASES == 504
    assert evaluator.FFMPEG_SHA256 == (
        "227af0691433b703ffc5725e47f7d06eefc34b4a72e7870e73d30e2cda483ecf"
    )
    assert evaluator.THRESHOLDS["minimumEntityExactRecall"] == 0.99
    assert evaluator.THRESHOLDS["minimumEntityTokenRecall"] == 0.99


def test_evaluator_opens_references_only_after_all_candidate_outputs() -> None:
    source = EVALUATOR_PATH.read_text(encoding="utf-8")
    candidate_output = source.index("recognizer.transcribe")
    oracle_boundary = source.index("Oracle/reference access begins here")
    manifest_open = source.index("manifest_path.read_text")
    reference_access = source.index('reference = str(reference_row["reference"])')

    assert candidate_output < oracle_boundary < manifest_open < reference_access


def test_failure_analyzer_pins_rejected_run_and_separates_numeric_entities() -> None:
    assert analyzer.SOURCE_ARTIFACT_SHA256 == (
        "e988aab17c350aa0c026673a3b4f00b0173b7e5b57de945dbb29d5974f258a12"
    )
    assert analyzer.SOURCE_DETAIL_SHA256 == (
        "1d0b32a62b2ebe25854fe62e5bc9118eeea85b9389cb5ebe52a80ceefab8d9be"
    )
    assert "percent" in analyzer.NUMERIC_TYPES
    assert "person" not in analyzer.NUMERIC_TYPES


def test_nemotron_evaluator_is_development_only_and_pins_model() -> None:
    source = NEMOTRON_EVALUATOR_PATH.read_text(encoding="utf-8")
    assert nemotron_evaluator.EXPECTED_CASES == 504
    assert nemotron_evaluator.THRESHOLDS["minimumEntityExactRecall"] == 0.99
    assert nemotron_evaluator.MODEL_FILES["tokens.txt"]["sha256"] == (
        "729cc103155bafa785f9cd45746cd41cabe97eab7182fc04d594129587958f8a"
    )
    assert "Oracle/reference access begins here" in source
    assert "validationBlindOpened\": False" in source
    assert "finalBlindOpened\": False" in source


def test_nemotron_analyzer_pins_both_complete_development_runs() -> None:
    assert nemotron_analyzer.PARAKEET_ARTIFACT_SHA256 == (
        "e988aab17c350aa0c026673a3b4f00b0173b7e5b57de945dbb29d5974f258a12"
    )
    assert nemotron_analyzer.NEMOTRON_ARTIFACT_SHA256 == (
        "cf00d336bceb0c87be08746a99f1369faf5f2c709d30a6573fd5e24998a3de85"
    )
    assert nemotron_analyzer.NEMOTRON_DETAIL_SHA256 == (
        "d2fec9837d2bef3f8abb0941e866510a160b00352ea5e5e94c64358c8fa3eddc"
    )


@pytest.mark.parametrize(
    ("written", "spoken"),
    [
        ("500 millones", "quinientos millones"),
        ("2010", "dos mil diez"),
        ("145", "ciento cuarenta y cinco"),
        ("76%", "setenta y seis"),
        ("56.000", "cincuenta y seis mil"),
        ("4,8%", "cuatro ocho"),
        ("16 de marzo", "dieciséis de marzo"),
        ("1,3%", "uno tres"),
    ],
)
def test_spanish_numeric_semantics_equates_written_and_spoken_forms(
    written: str, spoken: str
) -> None:
    assert numeric_semantics.semantic_tokens(written) == (
        numeric_semantics.semantic_tokens(spoken)
    )


def test_spanish_numeric_semantics_keeps_adjacent_years_separate() -> None:
    assert numeric_semantics.semantic_tokens("2008 2013") == (
        numeric_semantics.semantic_tokens("dos mil ocho dos mil trece")
    )


def test_numeric_semantic_evaluator_keeps_named_and_numeric_gates_separate() -> None:
    assert numeric_evaluator.SOURCE_ARTIFACT_SHA256 == (
        "e988aab17c350aa0c026673a3b4f00b0173b7e5b57de945dbb29d5974f258a12"
    )
    assert numeric_evaluator.THRESHOLDS["minimumNumericEntityExactRecall"] == 0.99
    assert numeric_evaluator.THRESHOLDS["minimumNamedEntityExactRecall"] == 0.99
    assert "percent" in numeric_evaluator.NUMERIC_TYPES
    assert "person" not in numeric_evaluator.NUMERIC_TYPES


def test_contextual_hotword_compiler_uses_exact_minimum_bpe_paths(
    tmp_path: Path,
) -> None:
    tokens = tmp_path / "tokens.txt"
    tokens.write_text(
        "<unk> 0\n"
        "▁ 1\n"
        "▁zona 2\n"
        "▁del 3\n"
        "▁euro 4\n"
        "z 5\n"
        "o 6\n"
        "n 7\n"
        "a 8\n"
        "d 9\n"
        "e 10\n"
        "l 11\n"
        "u 12\n"
        "r 13\n",
        encoding="utf-8",
    )

    compiled, commitments = contextual_hotwords.compile_hotwords(
        tokens,
        ["Zóna del euro", "zona_del_euro"],
    )

    assert compiled == "▁zona ▁del ▁euro"
    assert commitments == (
        {"surface": "Zóna del euro", "encoded": True, "pieces": 3},
    )
    assert contextual_hotwords.compile_stream_phrases(
        ["Zóna del euro", "zona_del_euro"]
    ) == "zona del euro"

    vocab = tmp_path / "bpe.vocab"
    contextual_hotwords.write_minimum_piece_vocab(tokens, vocab)
    assert vocab.read_text(encoding="utf-8").splitlines() == [
        f"{line.rsplit(' ', 1)[0]}\t-1.0"
        for line in tokens.read_text(encoding="utf-8").splitlines()
    ]


def test_contextual_oracle_selects_only_repeated_other_case_named_misses() -> None:
    rows = [
        {
            "caseId": "a",
            "entityCommitments": [
                {"type": "organization", "surface": "Unión Europea", "exactlyPreserved": False},
                {"type": "person", "surface": "Nombre Único", "exactlyPreserved": False},
                {"type": "date", "surface": "2010", "exactlyPreserved": False},
            ],
        },
        {
            "caseId": "b",
            "entityCommitments": [
                {"type": "organization", "surface": "Unión Europea", "exactlyPreserved": True},
                {"type": "organization", "surface": "Consejo", "exactlyPreserved": True},
            ],
        },
    ]

    specs = contextual_oracle.build_oracle_case_specs(
        rows,
        normalize_tokens=numeric_semantics.semantic_tokens,
        maximum_hotwords=2,
    )

    assert len(specs) == 1
    assert specs[0]["caseId"] == "a"
    assert specs[0]["targetTerms"] == ["Unión Europea"]
    assert specs[0]["distractorTerms"] == ["Consejo"]
    assert [target["entityIndex"] for target in specs[0]["targets"]] == [0]


def test_contextual_oracle_is_explicitly_non_promotable_and_development_only() -> None:
    source = CONTEXTUAL_ORACLE_EVALUATOR_PATH.read_text(encoding="utf-8")
    assert contextual_oracle.SOURCE_DETAIL_SHA256 == (
        "1d0b32a62b2ebe25854fe62e5bc9118eeea85b9389cb5ebe52a80ceefab8d9be"
    )
    assert contextual_oracle.EXPECTED_SELECTED_CASES == 15
    assert contextual_oracle.EXPECTED_TARGET_ENTITIES == 18
    assert contextual_oracle.HOTWORDS_SCORE == 5.0
    assert contextual_oracle.SCHEMA.endswith(".v2")
    assert contextual_oracle.INVALID_V1_ARTIFACT_SHA256 == (
        "f8a3ae6d662a31e7923ead6741a44afc3f2fb7bab53c23d661fd57bcb63852a8"
    )
    assert '"oracleTargetProvidedToAsr": True' in source
    assert '"candidatePromotable": False' in source
    assert 'modeling_unit="bpe"' in source
    assert "nativeHotwordEncodingErrors" in source
    assert '"validationBlindOpened": False' in source
    assert '"finalBlindOpened": False' in source


def test_contextual_oracle_matrix_freezes_safe_operating_region_before_run() -> None:
    assert contextual_matrix.SCORES == (0.75, 1.5, 3.0, 5.0)
    assert contextual_matrix.SHORTLISTS == (
        ("targets_only", None),
        ("maximum_4", 4),
        ("maximum_8", 8),
    )
    assert contextual_matrix.THRESHOLDS["minimumTargetRecoveryRate"] == 0.80
    assert contextual_matrix.THRESHOLDS[
        "maximumPreviouslyCorrectEntityDamages"
    ] == 0
    assert contextual_matrix.THRESHOLDS["maximumDistractorFalseInsertions"] == 0
    assert contextual_matrix.ORACLE_V2_ARTIFACT_SHA256 == (
        "6100a75aba1ec69fc535bf48abc8f96592c645d195675d50e50ece4e11bd6d79"
    )


def test_contextual_oracle_matrix_never_drops_oracle_targets_for_shortlist() -> None:
    case = {
        "targetTerms": ["uno", "dos", "tres"],
        "distractorTerms": ["cuatro", "cinco"],
    }

    assert contextual_matrix._terms_for(case, None) == ["uno", "dos", "tres"]
    assert contextual_matrix._terms_for(case, 4) == [
        "uno",
        "dos",
        "tres",
        "cuatro",
    ]
    assert contextual_matrix._terms_for(case, 2) == ["uno", "dos", "tres"]


def test_faster_whisper_evaluator_pins_cuda12_and_keeps_blinds_closed() -> None:
    parser = faster_whisper_evaluator.build_parser()
    source = FASTER_WHISPER_EVALUATOR_PATH.read_text(encoding="utf-8")

    assert "--ffmpeg" not in parser._option_string_actions  # noqa: SLF001
    assert parser.get_default("beam_size") == 1
    assert parser.get_default("max_new_tokens") == 256
    assert faster_whisper_evaluator.REQUIRED_RUNTIME_DLLS == {
        "cublas64_12.dll",
        "cublasLt64_12.dll",
        "cudart64_12.dll",
        "cudnn64_9.dll",
    }
    assert faster_whisper_evaluator.THRESHOLDS[
        "minimumEntityExactRecall"
    ] == 0.99
    assert source.index("model.transcribe") < source.index(
        "manifest_path.read_text"
    )
    assert '"validationBlindOpened": False' in source
    assert '"finalBlindOpened": False' in source


def test_dual_asr_ceiling_is_non_promotable_and_pins_complete_sources() -> None:
    source = DUAL_ASR_CEILING_PATH.read_text(encoding="utf-8")

    assert dual_asr_ceiling.PARAKEET_DETAIL_SHA256 == (
        "1d0b32a62b2ebe25854fe62e5bc9118eeea85b9389cb5ebe52a80ceefab8d9be"
    )
    assert dual_asr_ceiling.FASTER_WHISPER_DETAIL_SHA256 == (
        "9388ce72458893ef5107f658a68f7bf7cfd501c3904fe5c1148fb793c745aab7"
    )
    assert dual_asr_ceiling.MINIMUM_ENTITY_EXACT_RECALL == 0.99
    assert '"candidatePromotable": False' in source
    assert '"validationBlindOpened": False' in source
    assert '"finalBlindOpened": False' in source


def test_onnx_tdt_phrase_encoder_preserves_case_and_uses_minimum_pieces() -> None:
    pieces = {
        "▁": 0,
        "▁B": 1,
        "AX": 2,
        "Y": 3,
        "▁BAXY": 4,
        "▁baxy": 5,
        "▁ley": 6,
        "▁wert": 7,
    }

    assert onnx_tdt_boosting.encode_phrase("BAXY", pieces) == (4,)
    assert onnx_tdt_boosting.encode_phrase("baxy", pieces) == (5,)
    assert onnx_tdt_boosting.encode_phrase("ley wert", pieces) == (6, 7)
    assert onnx_tdt_boosting.encode_phrase("desconocido", pieces) is None


def test_onnx_tdt_boosting_graph_matches_nemo_nonuniform_scoring() -> None:
    graph = onnx_tdt_boosting.build_boosting_graph(
        ((1, 2, 3), (1, 2, 4), (3,)),
        vocabulary_size=5,
        context_score=1.0,
        depth_scaling=2.0,
    )

    first_score, state_after_1 = graph.advance(0, 1)
    second_score, state_after_12 = graph.advance(state_after_1, 2)
    third_score, _ = graph.advance(state_after_12, 3)
    assert first_score == pytest.approx(1.0)
    assert second_score == pytest.approx(2.0 + onnx_tdt_boosting.math.log(2.0))
    assert third_score == pytest.approx(2.0 + onnx_tdt_boosting.math.log(3.0))

    # A failed partial match pays back its accumulated boost, while a completed
    # phrase is never penalized on the following unrelated token.
    backoff_score, backoff_state = graph.advance(state_after_1, 0)
    final_score, final_state = graph.advance(0, 3)
    post_final_score, post_final_state = graph.advance(final_state, 0)
    assert backoff_score == pytest.approx(-1.0)
    assert backoff_state == 0
    assert final_score == pytest.approx(1.0)
    assert post_final_score == pytest.approx(0.0)
    assert post_final_state == 0


def test_onnx_tdt_boosting_never_converts_blank_to_nonblank() -> None:
    token_logits = onnx_tdt_boosting.np.asarray([1.0, 2.0, 9.0], dtype="float32")
    scores = onnx_tdt_boosting.np.asarray([100.0, 100.0], dtype="float32")

    assert (
        onnx_tdt_boosting.choose_boosted_token(
            token_logits,
            blank_id=2,
            state_scores=scores,
            alpha=10.0,
        )
        == 2
    )


def test_onnx_tdt_boosting_preserves_product_silence_contract() -> None:
    source = ONNX_TDT_BOOSTING_PATH.read_text(encoding="utf-8")

    assert "leading_silence_seconds: float = 0.2" in source
    assert "trailing_silence_seconds: float = 0.2" in source
    assert "CPUExecutionProvider" in source
    assert "urllib" not in source
    assert "requests" not in source


def test_onnx_tdt_boosting_evaluator_is_development_only_and_cached() -> None:
    source = ONNX_TDT_BOOSTING_EVALUATOR_PATH.read_text(encoding="utf-8")

    assert onnx_tdt_boosting_evaluator.ALPHAS == (0.0, 0.5, 1.0, 2.0, 4.0, 10.0)
    assert onnx_tdt_boosting_evaluator.SELECTED_ALPHA == 2.0
    assert onnx_tdt_boosting_evaluator.EXPECTED_CASES == 15
    assert onnx_tdt_boosting_evaluator.EXPECTED_TARGETS == 18
    assert '"candidatePromotable": False' in source
    assert '"validationBlindOpened": False' in source
    assert '"finalBlindOpened": False' in source
    assert source.index("decoder.encode_audio") < source.index(
        "decoder.decode_encoded"
    )
