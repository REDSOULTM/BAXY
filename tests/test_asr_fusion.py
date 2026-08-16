from __future__ import annotations

from baxy_mind.asr_fusion import (
    select_transcript,
    select_transcript_with_pause_safe_redecode,
)


OPERATIONS = {
    "backup.list",
    "bluetooth.device.list",
    "clipboard.read.text",
    "filesystem.known.search",
    "message.send",
    "media.status",
    "note.list",
    "peripheral.list",
    "reminder.list",
    "routine.list",
    "task.list",
    "wifi.status",
}


def test_parakeet_wins_when_whisper_loses_a_complete_effect() -> None:
    result = select_transcript(
        "que words tengo ready to paste",
        "keywords tengo ready to paste",
        OPERATIONS,
    )

    assert result.source == "parakeet"
    assert result.text == "que words tengo ready to paste"
    assert result.reason == "parakeet_complete_effect"


def test_whisper_is_default_when_both_hypotheses_are_unresolved() -> None:
    result = select_transcript("say anything plain", "please anything plain", OPERATIONS)

    assert result.source == "whisper"
    assert result.reason == "quality_default"


def test_conversation_content_outranks_a_spurious_effect() -> None:
    result = select_transcript(
        "show wifi status",
        "write a story where OCR is an imaginary city",
        OPERATIONS,
    )

    assert result.source == "whisper"
    assert result.reason == "conversation_safety"


def test_conflicting_complete_effects_fail_closed() -> None:
    result = select_transcript(
        "show the text ready to paste",
        "show wifi status",
        OPERATIONS,
    )

    assert result.requires_clarification is True
    assert result.reason == "effect_conflict"


def test_independent_asrs_recover_the_same_explicit_terminal_status() -> None:
    result = select_transcript(
        "Oye, porfa, when you have a minute, please I am it in plain. "
        "Dame playback state.",
        "Oye, porfa, when you have a minute, please say anything plain. "
        "Dame playback state.",
        OPERATIONS,
    )

    assert result.source == "fusion"
    assert result.text == "Dame playback state"
    assert result.reason == "terminal_status_consensus"


def test_terminal_status_consensus_cannot_discard_a_conflicting_prefix_effect() -> None:
    result = select_transcript(
        "show wifi status. Dame playback state.",
        "show wifi status. Dame playback state.",
        OPERATIONS,
    )

    assert result.reason != "terminal_status_consensus"


def test_pause_safe_redecode_changes_only_a_new_dual_asr_status_proof() -> None:
    result = select_transcript_with_pause_safe_redecode(
        "please say anything plain",
        "please anything plain",
        "when you have a mean it, please I am it in plain. Dame playback state.",
        "when you have a minute, please say anything plain. Dame playback state.",
        OPERATIONS,
    )

    assert result.text == "Dame playback state"
    assert result.reason == "pause_safe_terminal_status_consensus"


def test_pause_safe_redecode_preserves_baseline_without_terminal_consensus() -> None:
    result = select_transcript_with_pause_safe_redecode(
        "que words tengo ready to paste",
        "keywords tengo ready to paste",
        "que words tengo ready to paste. Read them.",
        "keywords tengo ready to paste. Read them.",
        OPERATIONS,
    )

    assert result.text == "que words tengo ready to paste"
    assert result.reason == "parakeet_complete_effect"


def test_index_aligned_exhaustive_reports_merge_complementary_clauses() -> None:
    result = select_transcript(
        "sin omitir ninguno, revisa en este orden: las copiarables; después, "
        "las rutinas personales guardadas; después, los recordatorios aún "
        "programados; después, el índice de notas privadas; después, las tareas "
        "que siguen abiertas; después, los equipos visibles por Bluetooth; "
        "después, los accesorios físicos conectados, devolviendo cada resultado "
        "por separado",
        "sin omitir ninguno, revisa en este orden: las copias recuperables; "
        "después, las rutinas personales guardadas; después, los recordatorios "
        "aún programados; después, el índice de notas privadas; después, las "
        "tareas que siguen abiertas, resultado por separado",
        OPERATIONS,
    )

    assert result.source == "fusion"
    assert result.reason == "clause_union"
    assert result.text is not None
    assert "las copias recuperables" in result.text
    assert "los accesorios fisicos conectados" in result.text


def test_exhaustive_report_merge_rejects_index_conflicts() -> None:
    result = select_transcript(
        "sin omitir ninguno, revisa en este orden: las rutinas personales "
        "guardadas; después, los recordatorios aún programados",
        "sin omitir ninguno, revisa en este orden: las copias recuperables; "
        "después, los recordatorios aún programados",
        OPERATIONS,
    )

    assert result.reason != "clause_union"
