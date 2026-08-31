"""Load and validate the shipped Goal 09.5.11C revalidation matrix.

The JSON under artifacts/goal095/synthesis/ is the source of truth. This
module does not clone the planner, first_signal, or voice engines. Holdout
numbers come from the shipped functions and from campaign pytest that
drives those same functions. A sealed R6 population is revalidated, not
reopened.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from baxy_mind.__main__ import (
    _explicit_arguments_from_evidence,
    _explicit_plan_skeleton,
    apply_compound_effect_conservation_veto,
)
from baxy_mind.effect_intent import (
    operation_domain_is_grounded,
    resolve_explicit_effects,
    unresolved_compound_contract,
)
from baxy_mind.first_signal import (
    KIND_MILESTONE,
    PATH_CLOSED_CONVERSATION,
    PATH_MODEL,
    PATH_RECOGNIZER,
    SILENCE_BUDGET_SECONDS,
    formulate_progress,
    should_emit_early,
    should_emit_milestone,
    turn_signal_payload,
    visible_after_verification,
)
from baxy_mind.voice import (
    SAMPLE_RATE,
    _complete_stt_bundle,
    _transcript_is_doubtful,
    resolve_stt_directory,
)
from baxy_mind.voice_output import (
    NeuralSpeechOutput,
    create_speech_output,
    resolve_neural_tts_model,
)
from baxy_mind.wakeword import (
    AcousticWakeDetector,
    WakeWordRuntimeError,
    WINDOW_SAMPLES,
    load_wakeword_config,
)
from experiments.mind_router_spike import (
    build_compound_execution_current_tree_r6 as r6_campaign,
)
from experiments.mind_router_spike.run_compound_execution_current_tree_r6 import (
    count_orphans,
)
from scripts.goal095_09511a_revalidate import (
    CORPUS_REL,
    CORPUS_SHA256,
    LANGUAGES,
    provenance_snapshot,
    sha256_file,
)
from scripts.goal095_0959_matrix import dump_json, load_campaign, load_json

REPO = Path(__file__).resolve().parents[1]
SCHEMA = "baxy.goal095.09511c-revalidate.v1"
LEDGER_SCHEMA = "baxy.goal095.09511c-ledger.v1"
VERSION = "v1"
SYNTHESIS_REL = "artifacts/goal095/synthesis/09.5.11C_revalidar_07_09.v1.json"
LEDGER_REL = "artifacts/goal095/ledger/revalidate-09.5.11C.json"
MARKDOWN_REL = "documentacion/herencia/09_5_11C_REVALIDAR.md"
HANDOFF_REL = "artifacts/goal095/HANDOFF.md"
OWNER_PROMPT = "documentacion/sprints/09.5.11C_REVALIDAR_07_09.md"
NEXT_PROMPT = "documentacion/sprints/09.5.12_INTEGRAR_Y_REPLANIFICAR.md"
FORBIDDEN_NEXT = (
    OWNER_PROMPT,
    "documentacion/sprints/09.5.11C_REVALIDAR_07_09.md",
    "documentacion/sprints/09.5.11B_REVALIDAR_04_06.md",
    "documentacion/sprints/09.5.11A_REVALIDAR_01_03C.md",
    "documentacion/sprints/09.5.10_TRASPLANTAR_LOTE.md",
    "documentacion/sprints/10.0_BASE_VERDE.md",
)
CAMPAIGN_REL = "artifacts/goal095/revalidate/goal09511c_campaigns.json"
R6_OUTPUT_REL = "artifacts/holdout/compound_execution_current_tree_r6.json"
R6_PREREG_REL = (
    "artifacts/holdout/compound_execution_current_tree_r6.preregistration.json"
)
FIRST_SIGNAL_LAT_REL = "artifacts/product/first_signal_latency.json"
FIRST_SIGNAL_CPU_REL = "artifacts/product/first_signal_latency_cpu.json"
SIMPLE_COMPLETE_REL = "artifacts/product/simple_complete_latency.json"
TURN_CALLS_REL = "artifacts/development/turn_call_decomposition_goal08.json"
GOAL09_STT_REL = "artifacts/goal09/stt_holdout.json"
GOAL09_TTS_REL = "artifacts/goal09/tts_measure.json"
GOAL09_WAKE_REL = "artifacts/goal09/wake_holdout.json"
GOAL09_FAR_REL = "artifacts/goal09/wake_far.json"
GOAL09_EOU_REL = "artifacts/goal09/eou_first_signal.json"
GOAL09_IDLE_REL = "artifacts/goal09/idle_listen.json"
GOAL09_RUNTIME_REL = "artifacts/goal09/runtime_voice_identity.json"
GOAL09_VOICE_MD = "documentacion/herencia/09_VOZ.md"
BASE08_REL = "documentacion/base/08_PRIMERA_SENAL.md"
COSTURAS_REL = "documentacion/03_COSTURAS.md"
APLAZADOS_REL = "documentacion/APLAZADOS.md"
VOICE_TEST_REL = "tests/test_goal09_voice_engines.py"
COMPOUND_TEST_REL = "tests/test_compound_missions.py"
FIRST_SIGNAL_TEST_REL = "tests/test_first_signal.py"
OWNER_TEST_REL = "tests/test_goal095_09511c_revalidate.py"
R6_TEST_REL = "tests/test_compound_execution_current_tree_r6.py"
CASCADE_FILES = (
    "src/Baxy.Providers.Windows/External/DesktopClickVisible.ps1",
    "src/Baxy.Providers.Windows/External/WindowsVisibleControlAdapter.cs",
    "src/Baxy.Providers.Windows/External/WindowsVisibleOcrLocator.cs",
    "src/Baxy.Providers.Windows/External/WindowsVisibleVisionLocator.cs",
    "src/Baxy.Providers.Windows/External/VisibleControlSurface.cs",
)
INSCOPE_TEST_REL = (
    VOICE_TEST_REL,
    COMPOUND_TEST_REL,
    FIRST_SIGNAL_TEST_REL,
    OWNER_TEST_REL,
    R6_TEST_REL,
)
AVAILABLE = frozenset(
    {
        "app.open",
        "audio.status",
        "input.visible.click",
        "network.status",
        "note.create",
        "note.read",
        "system.status",
    }
)
APPS = ("Steam", "Notepad", "Spotify")
CHAIN_CASES = (
    ("es", "Abre Steam y ve a la biblioteca", "biblioteca"),
    ("en", "Open Steam and go to Library", "library"),
    ("es_en", "Abre Steam and click Library", "library"),
)
BANNED_APP_NAMES = ("steam", "spotify", "discord", "chrome")
LABELS = frozenset({"fisica", "fixture"})
_WAKE_RUNTIME_MARKER = "BAXY_09511C_WAKE_INPROCESS"


class EnvironmentFailure(RuntimeError):
    """Hardware, asset, or sidecar runtime is missing. Never skip or pass."""


def _posix(path: str) -> str:
    return path.replace("\\", "/")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def report_path(repo: Path = REPO) -> Path:
    return repo / SYNTHESIS_REL


def ledger_path(repo: Path = REPO) -> Path:
    return repo / LEDGER_REL


def load_report(repo: Path = REPO) -> dict[str, Any]:
    path = report_path(repo)
    if not path.is_file():
        raise FileNotFoundError(path)
    return load_json(path)


def corpus_profile(repo: Path = REPO) -> dict[str, Any]:
    path = repo / CORPUS_REL
    rows = load_jsonl(path)
    languages: dict[str, int] = {}
    in_catalog = 0
    out_catalog = 0
    for row in rows:
        language = str(row.get("language") or "")
        languages[language] = languages.get(language, 0)
        languages[language] += 1
        if row.get("in_catalog"):
            in_catalog += 1
        else:
            out_catalog += 1
    return {
        "path": CORPUS_REL,
        "sha256": sha256_file(path),
        "rows": len(rows),
        "in_catalog": in_catalog,
        "out_of_catalog": out_catalog,
        "languages": dict(sorted(languages.items())),
    }


def aplazados_defers_11c_to_goal10(repo: Path = REPO) -> list[str]:
    hits = []
    for line in (repo / APLAZADOS_REL).read_text(encoding="utf-8").splitlines():
        folded = line.casefold()
        if "09.5.11c" not in folded:
            continue
        if "goal 10" in folded:
            hits.append("APLAZADOS.md names 09.5.11C together with Goal 10")
        if "10.0" in folded:
            hits.append("APLAZADOS.md names 09.5.11C together with 10.0")
    return hits


def baseline_trace() -> dict[str, Any]:
    """Why the four pre-campaign extract files stay out of this tree.

    `bdb8919` dropped the two files that existed at `5405efa`. The blob
    cache and Carter v2 fragments file were never versioned. 11C does not
    consume them; hashes are not invented.
    """
    return {
        "not_restored": [
            {
                "path": "artifacts/goal095/extract/_evidence_profile.txt",
                "present_at": "5405efa",
                "blob": "53e36625c8fef324ae21d7ce24cbfdc26f00c405",
                "dropped_by": "bdb8919",
                "reason": "pre-campaign evidence profile; 11C does not consume it",
            },
            {
                "path": "scripts/_goal095_profile_evidence.py",
                "present_at": "5405efa",
                "blob": "f1ff21f16e572cf6a3be7ce47f764691b017e4ca",
                "dropped_by": "bdb8919",
                "reason": "pre-campaign generator; 11C does not consume it",
            },
        ],
        "never_versioned": [
            {
                "path": "artifacts/goal095/extract/_schema_agent_blobs/",
                "present_in_5405efa": False,
                "identity": "artifacts/goal095/sources/baxy_schema_agent.keep.sha256.jsonl",
                "identity_blob": "0205119bcc86e1ecdcca54e9c2133551cf085ae9",
                "reason": "derived git-blob cache; hashes not invented",
            },
            {
                "path": "artifacts/goal095/extract/code_tests-002-carter-carter_legacy_Carter_v2.fragments.txt",
                "present_in_5405efa": False,
                "source": "artifacts/goal095/extract/code_tests-002-carter-carter_legacy_Carter_v2.inspect.json",
                "source_blob": "3d02a3549f9e4e232e3d7211a8e78c983b863670",
                "generator": "scripts/_goal095_code002_fragments.py",
                "reason": "derived extract; hashes not invented",
            },
        ],
    }


def _require_voice_interpreter_modules() -> None:
    missing: list[str] = []
    try:
        import silero_vad  # noqa: F401
    except ModuleNotFoundError:
        missing.append("silero_vad")
    try:
        import sounddevice  # noqa: F401
    except ModuleNotFoundError:
        missing.append("sounddevice")
    if missing:
        raise EnvironmentFailure(
            f"{', '.join(missing)} is not on this interpreter"
        )


def in_scope_source_skips(repo: Path = REPO) -> list[str]:
    hits = []
    for relative in INSCOPE_TEST_REL:
        text = (repo / relative).read_text(encoding="utf-8")
        if "pytest.skip(" in text:
            hits.append(relative)
    return hits


def _criterion(
    criterion_id: str,
    goal: str,
    text: str,
    evidence: list[str],
    *,
    label: str,
    holdout: bool = False,
    command: str | None = None,
    historical_result: str,
    scored_kind: str | None = None,
) -> dict[str, Any]:
    if label not in LABELS:
        raise ValueError(f"label {label!r} is not fisica/fixture")
    return {
        "id": criterion_id,
        "goal": goal,
        "criterion": text,
        "label": label,
        "holdout": holdout,
        "evidence": evidence,
        "command": command,
        "historical_result": historical_result,
        "scored_kind": scored_kind,
    }


def criterion_specs() -> list[dict[str, Any]]:
    missions_ev = [COMPOUND_TEST_REL, R6_OUTPUT_REL, R6_PREREG_REL, R6_TEST_REL]
    signal_ev = [FIRST_SIGNAL_TEST_REL, BASE08_REL, FIRST_SIGNAL_LAT_REL]
    voice_ev = [VOICE_TEST_REL, GOAL09_VOICE_MD, COSTURAS_REL]
    return [
        _criterion(
            "07-90-completo-verificado",
            "07",
            "≥ 90 % de misiones completas y verificadas, con cada paso verificado.",
            missions_ev,
            label="fixture",
            holdout=True,
            command="py -m pytest tests/test_compound_missions.py tests/test_compound_execution_current_tree_r6.py -q",
            historical_result="R6 sello 6/6 misiones, 22/22 pasos, 0 huérfanos. Planner vivo ES/EN/spanglish.",
            scored_kind="missions",
        ),
        _criterion(
            "07-cero-huerfanos",
            "07",
            "Cero pasos huérfanos: sin ejecutar, sin verificar, o ejecutados fuera del plan.",
            missions_ev,
            label="fixture",
            holdout=True,
            command="count_orphans(R6) + veto de conservación",
            historical_result="R6 orphan=0. Un segundo cláusula no reconocida no corre como subconjunto.",
            scored_kind="missions",
        ),
        _criterion(
            "07-steam-biblioteca",
            "07",
            "«Abre Steam y ve a la biblioteca» sobre el planner heredado (fixture; no sesión física).",
            missions_ev + [COMPOUND_TEST_REL],
            label="fixture",
            holdout=True,
            command="resolve_explicit_effects + _explicit_plan_skeleton",
            historical_result="Cierre vigente fixture/sello. Click Steam 2026-08-23 no se reabre ni se convierte en efecto físico.",
            scored_kind="missions",
        ),
        _criterion(
            "07-cascada-uia-ocr",
            "07",
            "La cascada UIA → OCR → visión funciona sin una sola app codificada a mano.",
            list(CASCADE_FILES) + [COMPOUND_TEST_REL],
            label="fixture",
            historical_result="VisibleClick sin steam/spotify/discord/chrome. OCR antes que visión.",
            scored_kind="missions",
        ),
        _criterion(
            "07-tres-segundos",
            "07",
            "Ninguna misión pasa más de 3 s sin salida visible.",
            signal_ev,
            label="fixture",
            holdout=True,
            command="should_emit_milestone / formulate_progress kind=hito",
            historical_result="Hito a 3,01 s. Goal 08 cubre el silencio; 07 lo hereda.",
            scored_kind="first_signal",
        ),
        _criterion(
            "07-tres-ceros",
            "07",
            "Los tres ceros intactos durante toda la misión.",
            missions_ev,
            label="fixture",
            historical_result="R6 ambiguous_effects=0. Veto de conservación impide el subconjunto silencioso.",
            scored_kind="missions",
        ),
        _criterion(
            "07-publicado",
            "07",
            "Publicado. git status --short vacío y git rev-list --count origin/main..main en 0.",
            missions_ev,
            label="fixture",
            historical_result="Goal 07 sello R6 en origin/main. 11C no reabre el sello.",
        ),
        _criterion(
            "08-numeros-poblacion-dificil",
            "08",
            "Los números, sobre población que incluye lo difícil, con el perfil CPU aparte.",
            signal_ev + [FIRST_SIGNAL_CPU_REL, SIMPLE_COMPLETE_REL],
            label="fixture",
            historical_result="GPU p50 0,009–0,011 s p95 0,146–0,161 s. CPU p50 0,026 s máx 2,973 s.",
            scored_kind="first_signal",
        ),
        _criterion(
            "08-cero-silencio-3s",
            "08",
            "Ninguna tarea, de ninguna duración, pasa 3 s en silencio.",
            signal_ev,
            label="fixture",
            holdout=True,
            command="should_emit_early / should_emit_milestone",
            historical_result="Camino modelo avisa; reconocedor calla. Hito > 3 s.",
            scored_kind="first_signal",
        ),
        _criterion(
            "08-senal-condicional-formulada",
            "08",
            "La señal temprana es condicional y es prosa formulada, no una constante.",
            signal_ev,
            label="fixture",
            holdout=True,
            command="should_emit_early + formulate_progress",
            historical_result="Reconocedor/conversación cerrada no emiten. ES ≠ EN.",
            scored_kind="first_signal",
        ),
        _criterion(
            "08-no-afirma-resultado",
            "08",
            "Ninguna señal temprana afirma un resultado; la autocorrección sustituye el acuse.",
            signal_ev,
            label="fixture",
            holdout=True,
            command="turn_signal_payload / visible_after_verification",
            historical_result="asserted_result=false. visible_after_verification reemplaza el acuse.",
            scored_kind="first_signal",
        ),
        _criterion(
            "08-llamadas-modelo",
            "08",
            "Publicado cuántas llamadas por modelo quedan por turno y por qué cada una sigue.",
            [TURN_CALLS_REL, BASE08_REL],
            label="fixture",
            historical_result="5–8 llamadas, p50 pared 2,53 s. No se recortó el shortlist.",
            scored_kind="first_signal",
        ),
        _criterion(
            "08-sin-regresion-ceros",
            "08",
            "Sin regresión en exactitud ni en los tres ceros.",
            signal_ev + ["artifacts/goal095/synthesis/09.5.11B_revalidar_04_06.v1.json"],
            label="fixture",
            historical_result="11B honesty 0/0/0. Señal temprana no es Listo ni constante.",
            scored_kind="first_signal",
        ),
        _criterion(
            "08-publicado",
            "08",
            "Publicado. git status --short vacío y git rev-list --count origin/main..main en 0.",
            [BASE08_REL],
            label="fixture",
            historical_result="Goal 08 cerrado 2026-08-23 y en origin/main.",
        ),
        _criterion(
            "09-wake-stt-tts-maquina",
            "09",
            "Wake, transcripción y habla funcionando en esta máquina, medidos ES/EN/spanglish.",
            voice_ev + [GOAL09_STT_REL, GOAL09_WAKE_REL, GOAL09_TTS_REL],
            label="fixture",
            holdout=True,
            command="py -m pytest tests/test_goal09_voice_engines.py -q",
            historical_result="WAV inyectado + motores registrados. No micrófono vivo.",
            scored_kind="voice",
        ),
        _criterion(
            "09-frontera-proceso-manifiesto",
            "09",
            "Las tres detrás de la frontera de proceso, declaradas en el manifiesto con su hash.",
            [GOAL09_RUNTIME_REL, COSTURAS_REL],
            label="fixture",
            historical_result="engines_in_python_sidecar=true. STT/TTS/wake SHA en runtime.",
            scored_kind="voice",
        ),
        _criterion(
            "09-falsas-activaciones",
            "09",
            "Falsas activaciones medidas sobre audio que no le habla a BAXY.",
            [GOAL09_FAR_REL, COSTURAS_REL],
            label="fixture",
            historical_result="FAR 2,00 h sellada. Umbral 0,5 no se retoca. No se reabre el holdout.",
            scored_kind="voice",
        ),
        _criterion(
            "09-eou-primera-senal",
            "09",
            "De fin de habla a primera señal, p50 ≤ 1,5 s, y nunca 3 s en silencio.",
            [GOAL09_EOU_REL, VOICE_TEST_REL],
            label="fixture",
            holdout=True,
            command="test_end_of_speech_to_first_signal_is_under_budget",
            historical_result="EOU p50 0,21 s, máx 0,31 s. Revalidado con PCM inyectado.",
            scored_kind="voice",
        ),
        _criterion(
            "09-interrupcion",
            "09",
            "Se le puede interrumpir a media frase.",
            [GOAL09_TTS_REL, VOICE_TEST_REL],
            label="fisica",
            holdout=True,
            command="test_neural_speak_starts_and_cancel_stops_mid_utterance",
            historical_result="NeuralSpeechOutput.cancel corta. Holdout físico de altavoz, no micrófono.",
            scored_kind="voice",
        ),
        _criterion(
            "09-accesibilidad-sin-pantalla",
            "09",
            "Ninguna capacidad de BAXY exige ver la pantalla o usar el ratón.",
            [GOAL09_VOICE_MD, COSTURAS_REL],
            label="fixture",
            historical_result="Toda respuesta se dice. Confirmaciones sí/no por MissionInput. Interruptor de escucha por voz.",
            scored_kind="voice",
        ),
        _criterion(
            "09-herencia-publicada",
            "09",
            "Publicado qué se heredó, de dónde, qué cambió y qué se descartó.",
            [GOAL09_VOICE_MD],
            label="fixture",
            historical_result="documentacion/herencia/09_VOZ.md. SAPI no es voz de producto.",
        ),
        _criterion(
            "09-consumo-reposo",
            "09",
            "Consumo en reposo medido, con la escucha permanente encendida.",
            [GOAL09_IDLE_REL],
            label="fixture",
            historical_result="idle_listen.json 60 s, STT/TTS en CPU, VRAM del decisor intacta.",
            scored_kind="voice",
        ),
        _criterion(
            "09-publicado",
            "09",
            "Publicado. git status --short vacío y git rev-list --count origin/main..main en 0.",
            [GOAL09_VOICE_MD],
            label="fixture",
            historical_result="Goal 09 cerrado 2026-08-24 y en origin/main.",
        ),
        _criterion(
            "095-transplant-vacio",
            "09.5",
            "Cola transplant vacía: 09.5.10 no aportó lotes; 07–09 se revalidan igual.",
            ["artifacts/goal095/campaigns/transplant.json"],
            label="fixture",
            holdout=True,
            command="provenance_snapshot()",
            historical_result="pending=0 claimed=0. Empty queue does not skip 07–09 holdouts.",
            scored_kind="provenance",
        ),
    ]


def required_criterion_ids() -> tuple[str, ...]:
    return tuple(item["id"] for item in criterion_specs())


def live_mission_chains() -> dict[str, Any]:
    chains = []
    for language, text, label in CHAIN_CASES:
        intent = resolve_explicit_effects(text, AVAILABLE, application_names=APPS)
        operations = list(intent.operations) if intent is not None else []
        skeleton = (
            _explicit_plan_skeleton(intent.operations, intent.evidence)
            if intent is not None
            else {"steps": []}
        )
        steps = list(skeleton.get("steps") or [])
        click_args = {}
        open_args = {}
        if intent is not None and len(intent.evidence) >= 2:
            click_args = _explicit_arguments_from_evidence(
                "input.visible.click",
                intent.evidence[1],
                APPS,
            )
            open_args = _explicit_arguments_from_evidence(
                "app.open",
                intent.evidence[0],
                APPS,
            )
        unresolved = unresolved_compound_contract(
            text, AVAILABLE, application_names=APPS, resolved_intent=intent
        )
        chains.append(
            {
                "language": language,
                "text": text,
                "operations": operations,
                "step_count": len(steps),
                "open_args": open_args,
                "click_args": click_args,
                "expected_click_label": label,
                "unresolved": unresolved is not None,
                "holds": (
                    operations == ["app.open", "input.visible.click"]
                    and len(steps) == 2
                    and open_args.get("appId") == "Steam"
                    and str(click_args.get("label") or "").casefold() == label
                    and unresolved is None
                ),
            }
        )
    halt_text = "Abre Steam y envía un mensaje a Ana"
    halt_intent = resolve_explicit_effects(
        halt_text, AVAILABLE, application_names=APPS
    )
    halt_contract = unresolved_compound_contract(
        halt_text, AVAILABLE, application_names=APPS
    )
    vetoed = apply_compound_effect_conservation_veto(
        {
            "mode": "plan",
            "operation": "app.open",
            "effect_operations": ["app.open"],
            "effect_count": "one",
            "effect_verification": "pending",
        },
        halt_contract,
    )
    return {
        "chains": chains,
        "languages": [item["language"] for item in chains],
        "all_hold": all(item["holds"] for item in chains),
        "halt": {
            "intent_is_none": halt_intent is None,
            "minimum_effects": getattr(halt_contract, "minimum_effects", None),
            "veto_mode": vetoed.get("mode"),
            "veto_effects": list(vetoed.get("effect_operations") or []),
            "holds": (
                halt_intent is None
                and halt_contract is not None
                and vetoed.get("mode") == "conversation"
                and list(vetoed.get("effect_operations") or []) == []
            ),
        },
        "click_domain": {
            "library": operation_domain_is_grounded(
                "ve a la biblioteca", "input.visible.click"
            ),
            "coat": operation_domain_is_grounded(
                "Sew the button on my coat.", "input.visible.click"
            ),
        },
    }


def live_cascade(repo: Path = REPO) -> dict[str, Any]:
    banned_hits = []
    ocr_before_vision = False
    adapter = repo / CASCADE_FILES[1]
    text = adapter.read_text(encoding="utf-8")
    ocr_before_vision = text.index("_ocr") < text.index("_vision")
    for relative in CASCADE_FILES:
        folded = (repo / relative).read_text(encoding="utf-8").casefold()
        for name in BANNED_APP_NAMES:
            if name in folded:
                banned_hits.append(f"{relative}:{name}")
    return {
        "banned_hits": banned_hits,
        "ocr_before_vision": ocr_before_vision,
        "holds": not banned_hits and ocr_before_vision,
    }


def live_r6(repo: Path = REPO) -> dict[str, Any]:
    output = load_json(repo / R6_OUTPUT_REL)
    prereg = load_json(repo / R6_PREREG_REL)
    cases = r6_campaign.build_cases("RUNID", "DOCUMENT")
    orphans = count_orphans(output, cases)
    summary = output.get("summary") or {}
    unverified = []
    for result in output.get("cases") or []:
        if result.get("status") != "passed":
            continue
        for step in result.get("steps") or []:
            if step.get("verified") is not True or step.get("status") != "completed":
                unverified.append(
                    f"{result.get('case')}:{step.get('id')}:{step.get('operation')}"
                )
    return {
        "passed": summary.get("passed"),
        "total": summary.get("total"),
        "verified_steps": summary.get("verified_steps"),
        "orphan": summary.get("orphan"),
        "orphans_recounted": orphans,
        "ambiguous_effects": summary.get("ambiguous_effects"),
        "real_llm_plan_cases_passed": summary.get("real_llm_plan_cases_passed"),
        "unverified_successes": unverified,
        "reuse_forbidden": prereg.get("supersedes", {}).get(
            "reuse_for_promotion_forbidden"
        )
        is True,
        "blind_holdout": prereg.get("blind_holdout") is True,
        "holds": (
            summary.get("passed") == 6
            and summary.get("total") == 6
            and summary.get("verified_steps") == 22
            and summary.get("orphan") == 0
            and orphans == 0
            and summary.get("ambiguous_effects") == 0
            and not unverified
            and prereg.get("supersedes", {}).get("reuse_for_promotion_forbidden")
            is True
        ),
    }


def _fill_missions(repo: Path) -> dict[str, Any]:
    chains = live_mission_chains()
    cascade = live_cascade(repo)
    sealed = live_r6(repo)
    return {
        "chains": chains,
        "cascade": cascade,
        "r6": sealed,
        "holds": chains["all_hold"]
        and chains["halt"]["holds"]
        and cascade["holds"]
        and sealed["holds"],
    }


def live_first_signal() -> dict[str, Any]:
    spanish = "Abre Steam y ve a la biblioteca"
    english = "Open Steam and go to the library"
    early_es = formulate_progress(spanish)
    early_en = formulate_progress(english)
    hito_es = formulate_progress(spanish, kind=KIND_MILESTONE, step=2, total=3)
    hito_en = formulate_progress(english, kind=KIND_MILESTONE, step=2, total=3)
    payload = turn_signal_payload("req-11c", early_es)
    correction = visible_after_verification(early_es, "No pude: Steam no responde.")
    started = 10.0
    return {
        "recognizer_emits": should_emit_early(PATH_RECOGNIZER),
        "closed_emits": should_emit_early(PATH_CLOSED_CONVERSATION),
        "model_emits": should_emit_early(PATH_MODEL),
        "compound_recognizer_emits": should_emit_early(PATH_RECOGNIZER, step_count=3),
        "early_es": early_es,
        "early_en": early_en,
        "hito_es": hito_es,
        "hito_en": hito_en,
        "languages_differ": early_es != early_en and hito_es != hito_en,
        "asserted_result": payload.get("asserted_result"),
        "payload_type": payload.get("type"),
        "correction": correction,
        "milestone_at_budget": should_emit_milestone(
            started, started + SILENCE_BUDGET_SECONDS
        ),
        "milestone_after_budget": should_emit_milestone(
            started, started + SILENCE_BUDGET_SECONDS + 0.01
        ),
        "listo_in_early": "listo" in early_es.casefold() or "listo" in early_en.casefold(),
        "holds": (
            should_emit_early(PATH_RECOGNIZER) is False
            and should_emit_early(PATH_CLOSED_CONVERSATION) is False
            and should_emit_early(PATH_MODEL) is True
            and should_emit_early(PATH_RECOGNIZER, step_count=3) is True
            and payload.get("asserted_result") is False
            and payload.get("type") == "turn.signal"
            and correction != early_es
            and should_emit_milestone(started, started + SILENCE_BUDGET_SECONDS)
            is False
            and should_emit_milestone(
                started, started + SILENCE_BUDGET_SECONDS + 0.01
            )
            is True
            and early_es != early_en
            and "listo" not in early_es.casefold()
        ),
    }


def live_first_signal_records(repo: Path = REPO) -> dict[str, Any]:
    payload = load_json(repo / FIRST_SIGNAL_LAT_REL)
    stats = payload.get("first_signal_seconds") or {}
    asserted = []
    languages = set()
    for row in payload.get("records") or []:
        languages.add(str(row.get("language") or ""))
        text = str(row.get("early_signal_text") or "")
        if text.casefold().startswith("listo"):
            asserted.append(row.get("case_id"))
    return {
        "p50": stats.get("p50"),
        "p95": stats.get("p95"),
        "max": stats.get("max"),
        "meets_p50": payload.get("meets_p50_target") is True,
        "meets_p95": payload.get("meets_p95_target") is True,
        "languages": sorted(languages),
        "asserted_listo": asserted,
        "holds": (
            payload.get("meets_p50_target") is True
            and payload.get("meets_p95_target") is True
            and float(stats.get("max") or 99) < 3.0
            and not asserted
        ),
    }


def _fill_first_signal(repo: Path) -> dict[str, Any]:
    live = live_first_signal()
    records = live_first_signal_records(repo)
    return {"live": live, "records": records, "holds": live["holds"] and records["holds"]}


def _wake_onnx_from_runtime() -> Path | None:
    local = (
        Path(os.environ.get("LOCALAPPDATA") or "")
        / "BAXYRuntime"
        / "assets"
        / "wake"
        / "baxy.onnx"
    )
    if local.is_file():
        return local
    return None


def _livekit_in_this_interpreter() -> bool:
    try:
        from livekit.wakeword import WakeWordModel  # noqa: F401
    except ModuleNotFoundError:
        return False
    return True


def _registered_runtime_python() -> Path | None:
    local = os.environ.get("LOCALAPPDATA") or ""
    manifest = Path(local) / "BAXYRuntime" / "mind-runtime-v1.json"
    try:
        if not manifest.is_file() or manifest.stat().st_size > 16 * 1024:
            return None
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if data.get("schema") != "baxy-mind-runtime-v1":
            return None
        candidate = Path(str(data.get("python") or ""))
        if candidate.is_file() and candidate.name.casefold() == "python.exe":
            return candidate
    except (OSError, TypeError, ValueError):
        return None
    return None


def _same_python(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return False


def _live_voice_engines_via_python(python: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env[_WAKE_RUNTIME_MARKER] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO), str(REPO / "src"), env.get("PYTHONPATH") or ""]
    )
    probe = (
        "import json;"
        "from scripts.goal095_09511c_revalidate import live_voice_engines;"
        "print('BAXY11C_VOICE=' + json.dumps(live_voice_engines(), ensure_ascii=False))"
    )
    completed = subprocess.run(
        [str(python), "-X", "utf8", "-c", probe],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip().casefold()
        if (
            "wake_word_runtime_missing" in detail
            or "no module named 'livekit'" in detail
        ):
            raise EnvironmentFailure(
                "livekit.wakeword is missing from the registered mind runtime"
            )
        if "environmentfailure" in detail:
            raise EnvironmentFailure(
                "registered mind runtime rejected the wake/STT/TTS probe"
            )
        raise EnvironmentFailure(
            "registered mind runtime failed the wake/STT/TTS probe"
        )
    payload = None
    marker = "BAXY11C_VOICE="
    for line in completed.stdout.splitlines():
        if line.startswith(marker):
            payload = json.loads(line[len(marker) :])
            break
    if not isinstance(payload, dict):
        raise EnvironmentFailure(
            "registered mind runtime returned no wake probe payload"
        )
    return payload


def _live_voice_engines_inprocess() -> dict[str, Any]:
    stt = resolve_stt_directory()
    if not _complete_stt_bundle(stt):
        raise EnvironmentFailure("Parakeet bundle is not on this machine")
    tts = resolve_neural_tts_model()
    if tts is None or not tts.is_file():
        raise EnvironmentFailure("neural TTS model is not on this machine")
    output = create_speech_output()
    neural = isinstance(output, NeuralSpeechOutput)
    if not neural:
        raise EnvironmentFailure("product TTS is not neural")
    wake_path = _wake_onnx_from_runtime()
    if wake_path is None:
        raise EnvironmentFailure("inherited baxy.onnx is not on this machine")
    import hashlib
    import shutil

    previous = os.environ.get("BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED")
    os.environ["BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED"] = "1"
    try:
        with tempfile.TemporaryDirectory(prefix="baxy11c-wake-") as raw:
            dest = Path(raw) / "baxy.onnx"
            shutil.copy2(wake_path, dest)
            digest = hashlib.sha256(dest.read_bytes()).hexdigest()
            manifest = Path(raw) / "baxy-wakeword-v1.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema": "baxy-wakeword-v1",
                        "model": "baxy.onnx",
                        "modelName": "baxy",
                        "phrase": "Baxy",
                        "sampleRate": SAMPLE_RATE,
                        "windowSamples": WINDOW_SAMPLES,
                        "hopSamples": 4000,
                        "threshold": 0.5,
                        "debounceSeconds": 2.0,
                        "sha256": digest,
                        "calibration": {"approved": False},
                    }
                ),
                encoding="utf-8",
            )
            try:
                detector = AcousticWakeDetector(load_wakeword_config(manifest))
            except WakeWordRuntimeError as error:
                if str(error) == "wake_word_runtime_missing":
                    raise EnvironmentFailure(
                        "livekit.wakeword is missing from this interpreter"
                    ) from error
                raise EnvironmentFailure(
                    f"wake runtime failed ({error})"
                ) from error
            noise = (
                np.random.default_rng(0).standard_normal(SAMPLE_RATE * 3) * 0.02
            ).astype(np.float32)
            hit = None
            for offset in range(0, noise.size, 512):
                found = detector.accept(
                    noise[offset : offset + 512], now=offset / SAMPLE_RATE
                )
                if found is not None:
                    hit = found
                    break
            noise_hit = hit is not None
    finally:
        if previous is None:
            os.environ.pop("BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED", None)
        else:
            os.environ["BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED"] = previous
    return {
        "stt_complete": True,
        "tts_present": True,
        "tts_neural": True,
        "wake_onnx_present": True,
        "noise_false_activation": noise_hit,
        "doubtful_question": _transcript_is_doubtful("?"),
        "doubtful_command": _transcript_is_doubtful("abre Spotify"),
        "holds": (
            noise_hit is False
            and _transcript_is_doubtful("?")
            and not _transcript_is_doubtful("abre Spotify")
        ),
    }


def live_voice_engines() -> dict[str, Any]:
    _require_voice_interpreter_modules()
    if _livekit_in_this_interpreter():
        return _live_voice_engines_inprocess()
    if (os.environ.get(_WAKE_RUNTIME_MARKER) or "").strip():
        raise EnvironmentFailure(
            "livekit.wakeword is missing from the registered mind runtime"
        )
    runtime = _registered_runtime_python()
    if runtime is None:
        raise EnvironmentFailure(
            "livekit.wakeword is missing and the registered mind runtime python is not on this machine"
        )
    if _same_python(Path(sys.executable), runtime):
        raise EnvironmentFailure(
            "livekit.wakeword is missing from the registered mind runtime"
        )
    return _live_voice_engines_via_python(runtime)


def live_voice_artifacts(repo: Path = REPO) -> dict[str, Any]:
    stt = load_json(repo / GOAL09_STT_REL)
    tts = load_json(repo / GOAL09_TTS_REL)
    eou = load_json(repo / GOAL09_EOU_REL)
    runtime = load_json(repo / GOAL09_RUNTIME_REL)
    kinds = {str(row.get("kind") or "") for row in stt.get("rows") or []}
    eou_rows = list(eou.get("rows") or [])
    eou_times = [float(row.get("first_signal_s") or 99) for row in eou_rows]
    eou_p50 = sorted(eou_times)[len(eou_times) // 2] if eou_times else 99.0
    return {
        "stt_kinds": sorted(kinds),
        "stt_all_hit": all(row.get("hit") is True for row in stt.get("rows") or []),
        "tts_cancelled": tts.get("cancelled_mid_utterance") is True,
        "tts_voice": tts.get("voice"),
        "eou_p50": eou_p50,
        "eou_max": max(eou_times) if eou_times else None,
        "eou_never_claims": eou.get("first_signal_never_claims_a_result") is True,
        "sidecar": runtime.get("engines_in_python_sidecar") is True,
        "not_dotnet": runtime.get("engines_in_dotnet") is False,
        "holds": (
            {"english", "spanish", "codeswitch"} <= kinds
            and all(row.get("hit") is True for row in stt.get("rows") or [])
            and tts.get("cancelled_mid_utterance") is True
            and eou_p50 <= 1.5
            and (max(eou_times) if eou_times else 99) < 3.0
            and runtime.get("engines_in_python_sidecar") is True
            and runtime.get("engines_in_dotnet") is False
        ),
    }


def _fill_voice(repo: Path) -> dict[str, Any]:
    engines = live_voice_engines()
    artifacts = live_voice_artifacts(repo)
    return {
        "engines": engines,
        "artifacts": artifacts,
        "holds": engines["holds"] and artifacts["holds"],
    }


def load_campaigns(repo: Path = REPO) -> dict[str, Any]:
    path = repo / CAMPAIGN_REL
    if not path.is_file():
        return {"runs": [], "missing": True}
    payload = load_json(path)
    return payload


def _fill_campaigns(repo: Path) -> dict[str, Any]:
    payload = load_campaigns(repo)
    runs = list(payload.get("runs") or [])
    skipped = [
        run.get("name")
        for run in runs
        if int(run.get("skipped") or 0) > 0 or int(run.get("failed") or 0) > 0
    ]
    return {
        "artifact": CAMPAIGN_REL,
        "missing": bool(payload.get("missing")),
        "runs": runs,
        "in_scope_failures_or_skips": skipped,
        "holds": (not payload.get("missing")) and not skipped and bool(runs),
    }


def campaigns_not_rerun() -> list[dict[str, str]]:
    return [
        {
            "id": "r6-execution",
            "reason": "sello reuse_for_promotion_forbidden; se revalida el sello y el planner vivo",
        },
        {
            "id": "measure_first_signal_latency",
            "reason": "runtime no trasplantado; contrato funcional reejecutado en test_first_signal",
        },
        {
            "id": "steam-physical",
            "reason": "cierre vigente fixture/sello; 11C no abre Steam ni convierte el fixture",
        },
        {
            "id": "wake-far-tv",
            "reason": "holdout FAR sellado; umbral 0,5 no se retoca",
        },
        {
            "id": "idle-listen-60s",
            "reason": "runtime de voz no trasplantado; artifacts/goal09/idle_listen.json",
        },
    ]


def _result_for(spec: dict[str, Any], holdouts: dict[str, Any]) -> str:
    kind = spec.get("scored_kind")
    if kind == "missions":
        missions = holdouts["missions"]
        r6 = missions["r6"]
        return (
            f"R6 {r6['passed']}/{r6['total']} steps={r6['verified_steps']} "
            f"orphan={r6['orphan']}; chains_hold={missions['chains']['all_hold']}"
        )
    if kind == "first_signal":
        signal = holdouts["first_signal"]
        return (
            f"live_holds={signal['live']['holds']}; "
            f"asserted_result={signal['live']['asserted_result']}; "
            f"p50={signal['records']['p50']}"
        )
    if kind == "voice":
        voice = holdouts["voice"]
        engines = voice["engines"]
        if not spec.get("holdout"):
            return spec["historical_result"]
        if not voice.get("holds"):
            detail = engines.get("environment_failure") or "voice holdout failed"
            return (
                "FALLO_DE_AMBIENTE "
                f"stt={engines.get('stt_complete')} "
                f"tts_neural={engines.get('tts_neural')} "
                f"wake={engines.get('wake_onnx_present')} "
                f"detail={detail}"
            )
        return (
            f"stt={engines['stt_complete']} "
            f"tts_neural={engines['tts_neural']} "
            f"wake={engines['wake_onnx_present']} "
            f"noise_fa={engines['noise_false_activation']}"
        )
    if kind == "provenance":
        prov = holdouts["provenance"]
        return f"transplant {prov['transplant']}; sparse_not_invented={prov['sparse_not_invented']}"
    if kind == "reproducibility":
        repro = holdouts.get("reproducibility") or {}
        return str(repro.get("result") or spec["historical_result"])
    return spec["historical_result"]


def build_report(
    repo: Path = REPO,
    *,
    closed_utc: str,
    reproducibility: dict[str, Any] | None = None,
) -> dict[str, Any]:
    holdouts = {
        "missions": _fill_missions(repo),
        "first_signal": _fill_first_signal(repo),
        "voice": _fill_voice(repo),
        "campaigns": _fill_campaigns(repo),
        "provenance": provenance_snapshot(repo),
        "reproducibility": reproducibility
        or {
            "command": ".\\scripts\\test_source_quality.ps1 -Mode Full",
            "result": "pendiente",
            "passed": False,
        },
        "not_rerun": campaigns_not_rerun(),
        "in_scope_source_skips": in_scope_source_skips(repo),
    }
    missions = holdouts["missions"]
    signal = holdouts["first_signal"]
    voice = holdouts["voice"]
    reproducibility_block = holdouts["reproducibility"]
    criteria = []
    for spec in criterion_specs():
        row = dict(spec)
        row["result"] = _result_for(spec, holdouts)
        row["status"] = "holds"
        if spec.get("scored_kind") == "voice" and spec.get("holdout") and not voice.get("holds"):
            row["status"] = "FALLO_DE_AMBIENTE"
        criteria.append(row)
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "goal": "09.5.11C",
        "closed_utc": closed_utc,
        "owner_prompt": OWNER_PROMPT,
        "next_human_prompt": NEXT_PROMPT,
        "reproducibility": {
            "command": reproducibility_block.get("command"),
            "result": reproducibility_block.get("result"),
            "passed": reproducibility_block.get("passed"),
        },
        "baseline_trace": baseline_trace(),
        "required_human_launches": 1,
        "transplant_pending": 0,
        "transplant_claimed": 0,
        "deferred_to_goal10": [],
        "live_src_changed": True,
        "src_change": {
            "owner": VOICE_TEST_REL,
            "reason": "Goal 09 tests resolved STT/wake/TTS via shipped resolvers and fail closed on missing assets instead of pytest.skip.",
        },
        "estado_del_arte_added": False,
        "corpus": corpus_profile(repo),
        "listons": {
            "r6_passed": 6,
            "r6_steps": 22,
            "r6_orphan": 0,
            "asserted_result": False,
            "eou_p50_seconds": 1.5,
            "silence_seconds": 3.0,
            "deferred_to_goal10": [],
            "in_scope_skips": 0,
        },
        "holdouts": holdouts,
        "holdout_summary": {
            "missions_hold": missions["holds"],
            "r6_orphan": missions["r6"]["orphan"],
            "first_signal_hold": signal["holds"],
            "asserted_result": signal["live"]["asserted_result"],
            "voice_hold": voice["holds"],
            "stt_complete": voice["engines"]["stt_complete"],
            "tts_neural": voice["engines"]["tts_neural"],
            "campaigns_hold": holdouts["campaigns"]["holds"],
        },
        "criteria": criteria,
    }


def validate_report(report: dict[str, Any], repo: Path = REPO) -> list[str]:
    errors: list[str] = []
    if report.get("schema") != SCHEMA:
        errors.append(f"schema {report.get('schema')!r} != {SCHEMA}")
    if not str(report.get("version") or "").strip():
        errors.append("version is empty")
    elif report.get("version") != VERSION:
        errors.append(f"version {report.get('version')!r} != {VERSION}")
    if report.get("next_human_prompt") != NEXT_PROMPT:
        errors.append(f"next_human_prompt expected {NEXT_PROMPT}")
    if report.get("owner_prompt") != OWNER_PROMPT:
        errors.append("owner_prompt must stay 09.5.11C")
    next_prompt = str(report.get("next_human_prompt") or "")
    for forbidden in FORBIDDEN_NEXT:
        if forbidden == OWNER_PROMPT and next_prompt == OWNER_PROMPT:
            errors.append("next_human_prompt remits 09.5.11C")
        elif forbidden != OWNER_PROMPT and forbidden in next_prompt:
            errors.append(f"next_human_prompt names {forbidden}")
    if "10.0" in next_prompt or "Goal 10" in next_prompt:
        errors.append("next_human_prompt names Goal 10")
    if "09.5.11B" in next_prompt or "09.5.11A" in next_prompt or "09.5.10" in next_prompt:
        errors.append("next_human_prompt names a previous 09.5 prompt")
    if report.get("deferred_to_goal10"):
        errors.append("deferred_to_goal10 is not empty")
    errors.extend(aplazados_defers_11c_to_goal10(repo))

    corpus = report.get("corpus") or {}
    live = corpus_profile(repo)
    if live["sha256"] != CORPUS_SHA256:
        errors.append(f"corpus sha {live['sha256']} != {CORPUS_SHA256}")
    if corpus.get("sha256") != CORPUS_SHA256:
        errors.append("report corpus sha is not the frozen 03C bytes")
    for language in LANGUAGES:
        if language not in live["languages"]:
            errors.append(f"corpus missing language {language}")

    rows = list(report.get("criteria") or [])
    present = [str(row.get("id") or "") for row in rows]
    expected = list(required_criterion_ids())
    if present != expected:
        missing = [item for item in expected if item not in present]
        extra = [item for item in present if item not in expected]
        if missing:
            errors.append("missing criteria: " + ", ".join(missing))
        if extra:
            errors.append("extra criteria: " + ", ".join(extra))

    for row in rows:
        for rel in row.get("evidence") or []:
            path = repo / str(rel)
            if not path.exists():
                errors.append(f"{row.get('id')}: missing evidence {rel}")
        if row.get("status") != "holds":
            errors.append(f"{row.get('id')}: status {row.get('status')!r} is not holds")
        if row.get("label") not in LABELS:
            errors.append(f"{row.get('id')}: label {row.get('label')!r} is not fisica/fixture")

    try:
        transplant = load_campaign(repo)
    except FileNotFoundError as error:
        errors.append(str(error))
        transplant = {}
    counts = transplant.get("counts") or {}
    if counts.get("pending") != 0 or counts.get("claimed") != 0:
        errors.append(f"transplant not empty: {counts}")

    skips = in_scope_source_skips(repo)
    if skips:
        errors.append("in-scope pytest.skip remains in " + ", ".join(skips))

    holdouts = report.get("holdouts") or {}
    missions = holdouts.get("missions") or _fill_missions(repo)
    if not missions.get("holds"):
        errors.append("missions holdout does not hold")
    chains = missions.get("chains") or {}
    if set(chains.get("languages") or []) < {"es", "en", "es_en"}:
        errors.append("mission chains miss ES/EN/spanglish")
    if not chains.get("all_hold"):
        errors.append("live steam+library chains do not hold")
    if not (chains.get("halt") or {}).get("holds"):
        errors.append("conservation veto does not halt a silent subset")
    r6 = missions.get("r6") or {}
    if r6.get("orphan") not in (0, None) or r6.get("orphans_recounted") not in (0, None):
        errors.append(f"R6 orphans {r6.get('orphan')}/{r6.get('orphans_recounted')}")
    if r6.get("unverified_successes"):
        errors.append("R6 success without postcondition: " + str(r6["unverified_successes"]))
    if r6.get("reuse_forbidden") is not True:
        errors.append("R6 seal no longer forbids reuse for promotion")

    signal = holdouts.get("first_signal") or _fill_first_signal(repo)
    if not signal.get("holds"):
        errors.append("first_signal holdout does not hold")
    live_signal = signal.get("live") or {}
    if live_signal.get("asserted_result") is not False:
        errors.append("early signal asserted_result is not false")
    if live_signal.get("listo_in_early"):
        errors.append("early signal contains Listo")
    if live_signal.get("recognizer_emits"):
        errors.append("fast recognizer emits an early signal")
    if not live_signal.get("model_emits"):
        errors.append("model path does not emit an early signal")

    voice = holdouts.get("voice") or _fill_voice(repo)
    if not voice.get("holds"):
        errors.append("voice holdout does not hold")
    engines = voice.get("engines") or {}
    if not engines.get("stt_complete"):
        errors.append("Parakeet bundle is not complete on this machine")
    if not engines.get("tts_neural"):
        errors.append("product TTS is not neural")
    if not engines.get("wake_onnx_present"):
        errors.append("wake onnx is not present")
    if engines.get("noise_false_activation") is not False:
        errors.append("wake fired on noise")

    campaigns = holdouts.get("campaigns") or _fill_campaigns(repo)
    if campaigns.get("missing"):
        errors.append("campaign pytest artifact is missing")
    if campaigns.get("in_scope_failures_or_skips"):
        errors.append(
            "in-scope campaign skip/fail: "
            + ", ".join(str(item) for item in campaigns["in_scope_failures_or_skips"])
        )

    provenance = holdouts.get("provenance") or provenance_snapshot(repo)
    transplant_counts = provenance.get("transplant") or {}
    if transplant_counts.get("pending") != 0 or transplant_counts.get("claimed") != 0:
        errors.append(f"transplant not empty in provenance: {transplant_counts}")

    repro = holdouts.get("reproducibility") or {}
    top_repro = report.get("reproducibility") or {}
    result_text = str(repro.get("result") or top_repro.get("result") or "")
    if not result_text.strip():
        errors.append("reproducibility.result is empty")
    if str(top_repro.get("result") or "") != str(repro.get("result") or ""):
        errors.append("top-level reproducibility.result does not match holdouts")
    if repro.get("passed"):
        if "source_quality_gate_passed: mode=Full" not in result_text:
            errors.append("reproducibility passed without Full")
        folded = result_text.casefold()
        if "xfail" in folded or "fallback" in folded:
            errors.append("reproducibility closed with xfail/fallback")
        if "skip" in folded:
            errors.append("reproducibility closed with skip")

    text = json.dumps(report, ensure_ascii=False)
    if "c:\\users\\" in text.casefold() or "d:\\perfil\\" in text.casefold():
        errors.append("report contains a machine-absolute path")
    return errors


def write_report(
    repo: Path = REPO,
    *,
    closed_utc: str,
    reproducibility: dict[str, Any],
) -> dict[str, Any]:
    report = build_report(repo, closed_utc=closed_utc, reproducibility=reproducibility)
    dump_json(report_path(repo), report)
    return report


def write_ledger(
    repo: Path,
    report: dict[str, Any],
    *,
    closed_utc: str,
    errors: list[str],
) -> dict[str, Any]:
    holdouts = report["holdouts"]
    ledger = {
        "schema": LEDGER_SCHEMA,
        "batch_id": "revalidate-09.5.11C",
        "kind": "revalidate",
        "status": "complete" if not errors else "blocked",
        "goal": "09.5.11C",
        "closed_utc": closed_utc,
        "report_ref": SYNTHESIS_REL,
        "markdown_ref": MARKDOWN_REL,
        "owner_prompt": OWNER_PROMPT,
        "next_prompt": NEXT_PROMPT,
        "next_human_prompt": report.get("next_human_prompt") or NEXT_PROMPT,
        "full_gate": {
            "command": (report.get("reproducibility") or {}).get("command")
            or (holdouts.get("reproducibility") or {}).get("command"),
            "result": (report.get("reproducibility") or {}).get("result")
            or (holdouts.get("reproducibility") or {}).get("result"),
            "passed": bool(
                (report.get("reproducibility") or {}).get("passed")
                if (report.get("reproducibility") or {}).get("passed") is not None
                else (holdouts.get("reproducibility") or {}).get("passed")
            ),
        },
        "required_human_launches": 1,
        "deferred_to_goal10": [],
        "live_src_changed": True,
        "errors": errors,
        "holdout_summary": report.get("holdout_summary"),
        "missions": {
            "holds": holdouts["missions"]["holds"],
            "r6_orphan": holdouts["missions"]["r6"]["orphan"],
        },
        "first_signal": {
            "holds": holdouts["first_signal"]["holds"],
            "asserted_result": holdouts["first_signal"]["live"]["asserted_result"],
        },
        "voice": {
            "holds": holdouts["voice"]["holds"],
            "stt_complete": holdouts["voice"]["engines"]["stt_complete"],
            "tts_neural": holdouts["voice"]["engines"]["tts_neural"],
        },
        "provenance": {
            "transplant": holdouts["provenance"]["transplant"],
        },
    }
    dump_json(ledger_path(repo), ledger)
    return ledger


def write_markdown(repo: Path, report: dict[str, Any]) -> None:
    holdouts = report["holdouts"]
    missions = holdouts["missions"]
    signal = holdouts["first_signal"]
    voice = holdouts["voice"]
    provenance = holdouts["provenance"]
    repro = holdouts["reproducibility"]
    r6 = missions["r6"]
    lines = [
        "# Goal 09.5.11C — Revalidar Goals 07–09",
        "",
        (
            f"Pausado {report['closed_utc'][:10]} en FALLO_DE_AMBIENTE. Fuente de verdad machine-readable:"
            if not voice["holds"]
            else f"Cerrado {report['closed_utc'][:10]}. Fuente de verdad machine-readable:"
        ),
        f"[`../{SYNTHESIS_REL}`](../../{SYNTHESIS_REL}).",
        f"Ledger: [`../{LEDGER_REL}`](../../{LEDGER_REL}).",
        "",
        "Siguiente prompt humano:",
        "[`../sprints/09.5.12_INTEGRAR_Y_REPLANIFICAR.md`](../sprints/09.5.12_INTEGRAR_Y_REPLANIFICAR.md).",
        "No remite a 09.5.11C, 09.5.11B, 09.5.11A, 09.5.10 ni 10.0.",
        "",
        "## Cola transplant",
        "",
        "**Vacía.** `pending=0` `claimed=0`. 09.5.10 no aportó lotes; los holdouts 07–09",
        "se corrieron igual. Hashes sparse **not invented**.",
        "",
        "## Etiquetas fisica / fixture",
        "",
        "Cada criterio de la matriz lleva `label`. Steam físico no se reabrió:",
        "el cierre vigente es fixture/sello. TTS `cancel()` a media frase es el",
        "único holdout físico reejecutado. Hardware ausente habría sido",
        "`FALLO_DE_AMBIENTE`, no `pytest.skip`.",
        "",
        "## Holdouts",
        "",
        "### Misiones (Goal 07)",
        "",
        f"R6 sello **{r6['passed']}/{r6['total']}**, pasos **{r6['verified_steps']}**,",
        f"huérfanos **{r6['orphan']}** (recount `{r6['orphans_recounted']}`), ambiguos **{r6['ambiguous_effects']}**.",
        "Reuse for promotion **forbidden**. Planner vivo ES/EN/spanglish:",
        "`app.open` + `input.visible.click` con postcondición de etiqueta.",
        "El veto de conservación corta «Abre Steam y envía un mensaje a Ana».",
        "",
        "### Primera señal (Goal 08)",
        "",
        f"asserted_result={signal['live']['asserted_result']}. Reconocedor calla, modelo avisa.",
        f"GPU p50={signal['records']['p50']} p95={signal['records']['p95']} máx={signal['records']['max']}.",
        "measure_first_signal_latency no se reabrió: runtime no trasplantado.",
        "",
        "### Voz (Goal 09)",
        "",
        (
            f"FALLO_DE_AMBIENTE. {voice['engines'].get('environment_failure')}"
            if not voice["holds"]
            else (
                f"STT complete={voice['engines']['stt_complete']}; TTS neural={voice['engines']['tts_neural']}; "
                f"wake present={voice['engines']['wake_onnx_present']}; noise FA={voice['engines']['noise_false_activation']}."
            )
        ),
        "WAV inyectado, no micrófono. Interrupción: NeuralSpeechOutput.cancel.",
        "",
        "### Campañas no reejecutadas",
        "",
    ]
    for item in holdouts["not_rerun"]:
        lines.append(f"- `{item['id']}` — {item['reason']}")
    lines.extend(
        [
            "",
            "### Procedencia y reproducibilidad",
            "",
            f"Procedencia: sparse_not_invented={provenance['sparse_not_invented']}; transplant {provenance['transplant']}.",
            f"Reproducibilidad: `{repro.get('command')}` → {repro.get('result')}.",
            "",
            "Cero aplazos al Goal 10.",
            "",
        ]
    )
    path = repo / MARKDOWN_REL
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_handoff(repo: Path, report: dict[str, Any], errors: list[str]) -> None:
    holdouts = report["holdouts"]
    missions = holdouts["missions"]
    signal = holdouts["first_signal"]
    voice = holdouts["voice"]
    repro = holdouts["reproducibility"]
    r6 = missions["r6"]
    lines = [
        "# Handoff — 09.5.11C revalidar 07–09 — "
        + str(report.get("closed_utc") or "")[:10],
        "",
        "## Objetivo",
        "Demostrar que los trasplantes conservan Goals 07–09.",
        "",
        "## Estado",
        (
            "Pausado: FALLO_DE_AMBIENTE de voz en py -3.12. next=09.5.12."
            if not voice["holds"]
            else "Hecho: matriz 07–09, holdouts misiones/primera señal/voz, next=09.5.12."
        ),
        (
            "En curso: 09.5.11C espera silero_vad y sounddevice en el intérprete de pytest. Sin empezar: 09.5.12 no se ejecuta."
            if not voice["holds"]
            else "En curso: nada. Sin empezar: 09.5.12."
        ),
        "",
        "## Decisiones tomadas",
        "- Cola transplant vacía no exime holdouts 07–09.",
        "- R6 no se reabre (reuse_for_promotion_forbidden); se revalida el sello + planner vivo.",
        "- Steam físico no se convierte desde el fixture.",
        "- test_goal09_voice_engines resuelve STT/wake/TTS por las funciones enviadas; falta de asset = fail, no skip.",
        "- Cero aplazos al Goal 10.",
        "",
        "## Archivos tocados",
        f"- `{SYNTHESIS_REL}` — matriz machine-readable",
        f"- `{LEDGER_REL}` — ledger 09.5.11C",
        f"- `{MARKDOWN_REL}` — cierre documental",
        f"- `{CAMPAIGN_REL}` — pytest in-scope 07–09",
        f"- `{VOICE_TEST_REL}` — resolvers enviados, fail cerrado",
        "- `tests/test_goal095_09511c_revalidate.py` — prueba dueña",
        "",
        "## Archivos relevantes aun sin tocar",
        "- `documentacion/sprints/09.5.12_INTEGRAR_Y_REPLANIFICAR.md` — se nombra, no se ejecuta",
        "",
        "## Hipotesis",
        f"Confirmadas: R6 {r6['passed']}/{r6['total']} orphan={r6['orphan']}; "
        f"asserted_result={signal['live']['asserted_result']}; "
        f"voice_hold={voice['holds']}.",
        "Descartadas: «cola vacía = no medir». «Skip de asset ausente = pass». «Reabrir R6».",
        "",
        "## Comandos ejecutados y resultado",
        f"- R6 orphan={r6['orphan']} unverified={r6['unverified_successes']}",
        f"- first_signal asserted_result={signal['live']['asserted_result']}",
        f"- voice stt={voice['engines']['stt_complete']} tts={voice['engines']['tts_neural']}",
        f"- `{repro.get('command')}` → {repro.get('result')}",
        f"- validate_report errors={errors}",
        "",
        "## Problemas pendientes",
        (
            "FALLO_DE_AMBIENTE: py -3.12 no importa silero_vad ni sounddevice. "
            "No declarar 09.5.11C completo. No ejecutar 09.5.12 hasta que el comando dueño sea verde."
            if errors or not voice["holds"]
            else "Ninguno de 09.5.11C. No ejecutar 09.5.12 en esta meta."
        ),
        "",
        "## Siguiente accion recomendada",
        "`documentacion/sprints/09.5.12_INTEGRAR_Y_REPLANIFICAR.md` (sesión nueva, un pegado).",
        "",
    ]
    (repo / HANDOFF_REL).write_text("\n".join(lines), encoding="utf-8", newline="\n")


def close_campaign(
    repo: Path,
    *,
    closed_utc: str,
    reproducibility: dict[str, Any],
) -> dict[str, Any]:
    report = write_report(
        repo,
        closed_utc=closed_utc,
        reproducibility=reproducibility,
    )
    errors = validate_report(report, repo=repo)
    if reproducibility.get("passed") is not True:
        errors.append("reproducibility holdout is not green")
    write_ledger(repo, report, closed_utc=closed_utc, errors=errors)
    write_markdown(repo, report)
    write_handoff(repo, report, errors)
    return {
        "errors": errors,
        "next_human_prompt": report["next_human_prompt"],
        "holdout_summary": report.get("holdout_summary"),
    }


def main() -> int:
    import argparse
    from datetime import datetime, timezone

    parser = argparse.ArgumentParser(description="Close Goal 09.5.11C revalidation")
    parser.add_argument("--reproducibility-result", required=True)
    parser.add_argument(
        "--reproducibility-command",
        default=".\\scripts\\test_source_quality.ps1 -Mode Full",
    )
    parser.add_argument("--reproducibility-passed", action="store_true")
    arguments = parser.parse_args()
    closed_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary = close_campaign(
        REPO,
        closed_utc=closed_utc,
        reproducibility={
            "command": arguments.reproducibility_command,
            "result": arguments.reproducibility_result,
            "passed": bool(arguments.reproducibility_passed),
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
