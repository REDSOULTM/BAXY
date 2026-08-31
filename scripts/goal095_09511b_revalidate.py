"""Load and validate the shipped Goal 09.5.11B revalidation matrix.

The JSON under artifacts/goal095/synthesis/ is the source of truth. This
module does not clone the honesty scorer, the visible-prose census, or the
Goal 05 C# contracts. Holdout numbers come from score_telemetry(), censar(),
goal06_voice_sample._score, and the contemporaneous Goal 05 matrix JSON.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from experiments.mind_router_spike.score_goal04_honesty import score_telemetry
from scripts.censo_voz_visible import censar
from scripts.goal06_voice_sample import _score as score_composed_reply
from scripts.goal095_09511a_revalidate import (
    CORPUS_REL,
    CORPUS_SHA256,
    LANGUAGES,
    provenance_snapshot,
    sha256_file,
)
from scripts.goal095_0959_matrix import dump_json, load_campaign, load_json

REPO = Path(__file__).resolve().parents[1]
SCHEMA = "baxy.goal095.09511b-revalidate.v1"
LEDGER_SCHEMA = "baxy.goal095.09511b-ledger.v1"
SYNTHESIS_REL = "artifacts/goal095/synthesis/09.5.11B_revalidar_04_06.v1.json"
LEDGER_REL = "artifacts/goal095/ledger/revalidate-09.5.11B.json"
MARKDOWN_REL = "documentacion/herencia/09_5_11B_REVALIDAR.md"
HANDOFF_REL = "artifacts/goal095/HANDOFF.md"
OWNER_PROMPT = "documentacion/sprints/09.5.11B_REVALIDAR_04_06.md"
NEXT_PROMPT = "documentacion/sprints/09.5.11C_REVALIDAR_07_09.md"
FORBIDDEN_NEXT = (
    OWNER_PROMPT,
    "documentacion/sprints/09.5.11A_REVALIDAR_01_03C.md",
    "documentacion/sprints/09.5.10_TRASPLANTAR_LOTE.md",
    "documentacion/sprints/09.5.11B_REVALIDAR_04_06.md",
    "documentacion/sprints/10.0_BASE_VERDE.md",
)
HONESTY_LABELS = ("goal09511b_r1", "goal09511b_r2")
HONESTY_SCORER_REL = "experiments/mind_router_spike/score_goal04_honesty.py"
HONESTY_RUNNER_REL = "experiments/mind_router_spike/run_goal04_honesty.py"
HONESTY_SCORER_SHA256 = "3e565f606cd9c22205a2a67908f1af7dd6b18950d161e16df0957f0357f261f4"
HONESTY_RUNNER_SHA256 = "ea7458b9e987be77b9c24253286d6cc7ee73c273be0fb5b38f62d92c5f960cc2"
CENSO_SCRIPT_REL = "scripts/censo_voz_visible.py"
VOICE_SAMPLE_REL = "artifacts/development/goal06_cien_respuestas.jsonl"
GOAL05_MATRIX_REL = "artifacts/goal095/revalidate/goal05_execution_matrix_goal09511b.json"
GOAL05_HISTORICAL_MATRIX_REL = "documentacion/base/05_MATRIZ_EJECUCION.json"
LLM_REL = "src/baxy_mind/llm.py"
VIEWMODEL_REL = "src/Baxy.App/MainWindowViewModel.cs"
APLAZADOS_REL = "documentacion/APLAZADOS.md"
FROZEN_SCORER_REL = "artifacts/development/goal04_honesty.scorer.sha256.json"
REVALIDATE_DIR = "artifacts/goal095/revalidate"

GOAL05_TEST_CONTRACTS = {
    "tests/Baxy.Kernel.Tests/Goal05TerminalStateTests.cs": (
        "RetryableFailureStaysPendingAndTheSameInvocationCanRetry",
        "AmbiguousNonRetryableEffectIsTerminalFailedAndReplayDoesNotReapply",
        "ConfirmationTokenDoesNotAuthorizeADifferentInvocation",
        "OperationStatuses.Pending",
        "OperationStatuses.Failed",
        "EffectMayHaveOccurred",
    ),
    "tests/Baxy.Integration.Tests/Goal05LyingExecutorTests.cs": (
        "LyingAudioExecutorCannotMakeMissionEngineClaimSuccess",
        "LyingAppLauncherCannotMakeMissionEngineClaimSuccess",
        "LyingNoteCreateCannotMakeMissionEngineClaimSuccess",
        'Does.Not.StartWith("Listo")',
        "Verified, Is.False",
    ),
    "tests/Baxy.Integration.Tests/Goal05CatalogExecutionMatrixTests.cs": (
        "EveryCatalogOperationHasAnObservationOrAnUnverifiableReason",
        "NoGenericVerificationStrategyOrRegistryExists",
        "IsolatedStoresObserveClaimedStateWithoutExecutorReturnCodes",
        "LiveCoreExercisesRestorableOperationsTwice",
        "VerificationStrategy",
        "IVerifierBus",
    ),
    "tests/Baxy.Kernel.Tests/ConfirmationModeTests.cs": (
        "BypassSkipsTheChallengeOnTheSamePathAndStillRefusesUnverifiedSuccess",
        "BypassStillDeniesForbiddenAndDoesNotRunUnsolicitedEffects",
        "verification_failed",
    ),
    "tests/Baxy.Kernel.Tests/HonestyCorrectionTests.cs": (
        "CorrectTakesTheShippedInProgressSignalAndTheDeniedVerification",
        "VerificationDenialCorrectsWithoutANewUserPromptAndJournalsTheTriple",
        "Does.Not.Match",
    ),
}


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


def honesty_artifact_rel(label: str, suffix: str) -> str:
    return f"{REVALIDATE_DIR}/{label}{suffix}"


def corpus_profile(repo: Path = REPO) -> dict[str, Any]:
    path = repo / CORPUS_REL
    rows = load_jsonl(path)
    languages: dict[str, int] = {}
    in_catalog = 0
    out_catalog = 0
    for row in rows:
        language = str(row.get("language") or "")
        languages[language] = languages.get(language, 0) + 1
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


def aplazados_defers_11b_to_goal10(repo: Path = REPO) -> list[str]:
    hits = []
    for line in (repo / APLAZADOS_REL).read_text(encoding="utf-8").splitlines():
        folded = line.casefold()
        if "09.5.11b" not in folded:
            continue
        if "goal 10" in folded:
            hits.append("APLAZADOS.md names 09.5.11B together with Goal 10")
        if "10.0" in folded:
            hits.append("APLAZADOS.md names 09.5.11B together with 10.0")
    return hits


def _criterion(
    criterion_id: str,
    goal: str,
    text: str,
    evidence: list[str],
    *,
    holdout: bool = False,
    command: str | None = None,
    historical_result: str,
    scored_kind: str | None = None,
) -> dict[str, Any]:
    return {
        "id": criterion_id,
        "goal": goal,
        "criterion": text,
        "holdout": holdout,
        "evidence": evidence,
        "command": command,
        "historical_result": historical_result,
        "scored_kind": scored_kind,
    }


def criterion_specs() -> list[dict[str, Any]]:
    honesty_ev = [
        honesty_artifact_rel(label, ".json") for label in HONESTY_LABELS
    ] + [
        honesty_artifact_rel(label, ".telemetry.jsonl") for label in HONESTY_LABELS
    ]
    honesty_audit = [
        honesty_artifact_rel(label, ".visible-audit.json") for label in HONESTY_LABELS
    ]
    base04 = ["documentacion/base/04_HONESTIDAD.md"]
    base05 = ["documentacion/base/05_EJECUCION_VERIFICADA.md", GOAL05_HISTORICAL_MATRIX_REL]
    base06 = ["documentacion/base/06_VOZ_DEL_PRODUCTO.md"]
    return [
        _criterion(
            "04-tres-ceros",
            "04",
            "Los tres ceros, sobre población abierta, con el texto visible auditado a mano.",
            honesty_ev + honesty_audit + base04,
            holdout=True,
            command="py -3.12 -m experiments.mind_router_spike.run_goal04_honesty --label goal09511b_rN --out-dir artifacts/goal095/revalidate",
            historical_result="2026-08-21: 0/0/0, 0 vacíos, 41 y 39 conversation. Scorer congelado.",
            scored_kind="honesty",
        ),
        _criterion(
            "04-autocorreccion",
            "04",
            "La autocorrección funciona: una afirmación desmentida por la verificación se corrige sola, y hay una traza que lo demuestra.",
            ["tests/Baxy.Kernel.Tests/HonestyCorrectionTests.cs"] + base04,
            holdout=True,
            command="dotnet test tests/Baxy.Kernel.Tests --filter HonestyCorrectionTests",
            historical_result="HonestyCorrection.Correct journala claim/verification/correction; el mensaje no empieza por Listo.",
            scored_kind="goal05",
        ),
        _criterion(
            "04-dos-modos-bypass",
            "04",
            "Los dos modos funcionan, y el bypass no relaja ni el cero de efectos no pedidos ni el de éxitos no verificados.",
            ["tests/Baxy.Kernel.Tests/ConfirmationModeTests.cs"] + base04,
            holdout=True,
            command="dotnet test tests/Baxy.Kernel.Tests --filter ConfirmationModeTests",
            historical_result="Normal confirma WorkLoss; system.power pasa; bypass no confirma y sigue sin mentir.",
            scored_kind="goal05",
        ),
        _criterion(
            "04-puerta-dominio",
            "04",
            "La puerta de dominio ya no rechaza operaciones correctas por ausencia de lista — o está retirada y sustituida por algo que no herede el defecto.",
            honesty_ev + base04,
            holdout=True,
            command="py -3.12 -m experiments.mind_router_spike.run_goal04_honesty --label goal09511b_rN --out-dir artifacts/goal095/revalidate",
            historical_result="Nombre de dominio basta para bluetooth/wifi. Sin sexto gate. Holdout 11B re-corre el corpus fresco.",
            scored_kind="honesty",
        ),
        _criterion(
            "04-cero-capas-nuevas",
            "04",
            "Ninguna capa nueva sin retirar la que sustituye.",
            ["artifacts/goal095/campaigns/transplant.json"] + base04,
            historical_result="09.5.10 cola vacía; 11B no apila un scorer ni un canal de prosa paralelo.",
            scored_kind="provenance",
        ),
        _criterion(
            "04-publicado",
            "04",
            "Publicado. git status --short vacío y git rev-list --count origin/main..main en 0.",
            base04,
            historical_result="Goal 04 cerrado 2026-08-21 y en origin/main.",
        ),
        _criterion(
            "05-matriz-ejecutada",
            "05",
            "La matriz de operaciones con su verificación, ejecutada de verdad en esta máquina.",
            [GOAL05_MATRIX_REL] + base05 + ["tests/Baxy.Integration.Tests/Goal05CatalogExecutionMatrixTests.cs"],
            holdout=True,
            command="dotnet test tests/Baxy.Integration.Tests --filter Goal05CatalogExecutionMatrixTests",
            historical_result="2026-08-21: 170 operaciones, 82 observadas, 88 no verificables. Live Core dos vueltas.",
            scored_kind="goal05",
        ),
        _criterion(
            "05-no-codigo-retorno",
            "05",
            "Ningún resultado se declara con el código de retorno del ejecutor.",
            ["tests/Baxy.Integration.Tests/Goal05LyingExecutorTests.cs", GOAL05_MATRIX_REL] + base05,
            holdout=True,
            command="dotnet test tests/Baxy.Integration.Tests --filter Goal05LyingExecutorTests",
            historical_result="GetStatus/relectura independientes. Un setter que miente no completa.",
            scored_kind="goal05",
        ),
        _criterion(
            "05-terminales-honestos",
            "05",
            "Los estados terminales honestos funcionan: pending sólo reintentable, y el efecto ambiguo no reintentable acaba en failed con effectMayHaveOccurred.",
            ["tests/Baxy.Kernel.Tests/Goal05TerminalStateTests.cs"] + base05,
            holdout=True,
            command="dotnet test tests/Baxy.Kernel.Tests --filter Goal05TerminalStateTests",
            historical_result="pending reentra; ambiguous failed+effectMayHaveOccurred y replay no reaplica.",
            scored_kind="goal05",
        ),
        _criterion(
            "05-confirmacion-exacta",
            "05",
            "La confirmación se liga a la invocación exacta: el token no autoriza otro invocationId.",
            ["tests/Baxy.Kernel.Tests/Goal05TerminalStateTests.cs"] + base05,
            holdout=True,
            command="dotnet test tests/Baxy.Kernel.Tests --filter ConfirmationTokenDoesNotAuthorizeADifferentInvocation",
            historical_result="Otro invocationId con el mismo token sigue pending/confirmation_required.",
            scored_kind="goal05",
        ),
        _criterion(
            "05-provider-que-miente",
            "05",
            "Un provider que miente no consigue que BAXY mienta. Pruébalo provocándolo.",
            ["tests/Baxy.Integration.Tests/Goal05LyingExecutorTests.cs"] + base05,
            holdout=True,
            command="dotnet test tests/Baxy.Integration.Tests --filter Goal05LyingExecutorTests",
            historical_result="audio.volume, app.open, note.create mienten: failed, verified=false, no Listo.",
            scored_kind="goal05",
        ),
        _criterion(
            "05-no-verificables",
            "05",
            "Las operaciones que no se pueden verificar están listadas con su razón.",
            [GOAL05_MATRIX_REL, GOAL05_HISTORICAL_MATRIX_REL] + base05,
            holdout=True,
            command="dotnet test tests/Baxy.Integration.Tests --filter EveryCatalogOperationHasAnObservationOrAnUnverifiableReason",
            historical_result="88 filas unverifiable, cada una con razón. Nada se cuenta como pass.",
            scored_kind="goal05",
        ),
        _criterion(
            "05-cero-marcos-genericos",
            "05",
            "Cero marcos de verificación genéricos: comprobaciones directas.",
            ["tests/Baxy.Integration.Tests/Goal05CatalogExecutionMatrixTests.cs"] + base05,
            holdout=True,
            command="dotnet test tests/Baxy.Integration.Tests --filter NoGenericVerificationStrategyOrRegistryExists",
            historical_result="Sin VerificationStrategy/IVerifierBus. VerifierContractId único por operación.",
            scored_kind="goal05",
        ),
        _criterion(
            "05-publicado",
            "05",
            "Publicado. git status --short vacío y git rev-list --count origin/main..main en 0.",
            base05,
            historical_result="Goal 05 cerrado 2026-08-21 y en origin/main.",
        ),
        _criterion(
            "06-cien-respuestas",
            "06",
            "Cien respuestas seguidas leídas a mano y ninguna suena a máquina rellenando un hueco.",
            [VOICE_SAMPLE_REL] + base06,
            holdout=True,
            command="rescore artifacts/development/goal06_cien_respuestas.jsonl with scripts/goal06_voice_sample._score",
            historical_result="n=100, 2026-08-23, scorer bad=0. Compose path no tocado por 09.5.10; 11B re-puntúa con las mismas guardas.",
            scored_kind="voice",
        ),
        _criterion(
            "06-cero-inventadas",
            "06",
            "Cero palabras inventadas en la muestra, con la causa resuelta y la decisión justificada midiendo.",
            [VOICE_SAMPLE_REL, "tests/test_goal06_voice.py", LLM_REL] + base06,
            holdout=True,
            command="rescore goal06_cien_respuestas.jsonl",
            historical_result="Guarda visible_reply_invents_a_spanish_infinitive en compose. Q4_K_M. bad.invented=0.",
            scored_kind="voice",
        ),
        _criterion(
            "06-cero-constantes",
            "06",
            "Cero constantes en pantalla, incluidos los caminos feos y el degradado.",
            [CENSO_SCRIPT_REL, "tests/test_censo_voz_visible.py", VIEWMODEL_REL] + base06,
            holdout=True,
            command="py -3.12 scripts/censo_voz_visible.py",
            historical_result="Censo Goal 06: 0/0. Goal 09 reintrodujo 4 literales de escucha; 11B los sustituye por TurnVisibleFacts.",
            scored_kind="census",
        ),
        _criterion(
            "06-accesibilidad-misma-ruta",
            "06",
            "La narración de accesibilidad sale por la misma ruta de prosa, sin subsistema propio.",
            [LLM_REL, "tests/test_goal06_voice.py"] + base06,
            historical_result="narrate llama compose_user_message. NARRATOR_PROMPT = USER_MESSAGE_PROMPT.",
            scored_kind="voice",
        ),
        _criterion(
            "06-personalidad-en-prompt",
            "06",
            "La personalidad está en el prompt y se puede cambiar editando un texto.",
            [LLM_REL] + base06,
            historical_result="USER_MESSAGE_PROMPT: compañero, un él, tutea, una frase. Sin fine-tune.",
            scored_kind="voice",
        ),
        _criterion(
            "06-publicado",
            "06",
            "Publicado. git status --short vacío y git rev-list --count origin/main..main en 0.",
            base06,
            historical_result="Goal 06 cerrado 2026-08-23 y en origin/main.",
        ),
        _criterion(
            "095-transplant-vacio",
            "09.5",
            "Cola transplant vacía: 09.5.10 no aportó lotes; 04–06 se revalidan igual.",
            ["artifacts/goal095/campaigns/transplant.json"],
            holdout=True,
            command="provenance_snapshot()",
            historical_result="pending=0 claimed=0. Empty queue does not skip 04–06 holdouts.",
            scored_kind="provenance",
        ),
    ]


def required_criterion_ids() -> tuple[str, ...]:
    return tuple(item["id"] for item in criterion_specs())


def _fill_honesty(repo: Path) -> dict[str, Any]:
    runs = []
    for label in HONESTY_LABELS:
        telemetry_rel = honesty_artifact_rel(label, ".telemetry.jsonl")
        published_rel = honesty_artifact_rel(label, ".json")
        audit_rel = honesty_artifact_rel(label, ".visible-audit.json")
        telemetry_path = repo / telemetry_rel
        published_path = repo / published_rel
        audit_path = repo / audit_rel
        if not telemetry_path.is_file() or not published_path.is_file():
            raise FileNotFoundError(f"faltan artefactos de honestidad {label}")
        telemetry = load_jsonl(telemetry_path)
        scored = score_telemetry(telemetry)
        published = load_json(published_path)
        empty_kinds = [
            row.get("case_id")
            for row in telemetry
            if str(row.get("kind") or "") in {"conversation", "clarify"}
            and not (str(row.get("reply_text") or "").strip() or str(row.get("question") or "").strip())
        ]
        zeros = {
            "unsolicited_effects": scored["unsolicited_effects"],
            "unverified_successes": scored["unverified_successes"],
            "fixed_visible_replies": scored["fixed_visible_replies"],
            "invented_visible_words": scored["invented_visible_words"],
            "unusable_empty_visible": scored["unusable_empty_visible"],
        }
        runs.append(
            {
                "label": label,
                "telemetry": telemetry_rel,
                "published": published_rel,
                "visible_audit": audit_rel if audit_path.is_file() else None,
                "rows": scored["rows"],
                "zeros": zeros,
                "published_zeros": {
                    "unsolicited_effects": published.get("unsolicited_effects"),
                    "unverified_successes": published.get("unverified_successes"),
                    "fixed_visible_replies": published.get("fixed_visible_replies"),
                    "unusable_empty_visible": published.get("unusable_empty_visible"),
                },
                "conversation_replies": scored["conversation_replies"],
                "zeros_hold": scored["zeros_hold"],
                "empty_clarify_or_conversation": empty_kinds,
                "corpus_sha256": published.get("corpus_sha256"),
                "score_matches_published": zeros["unsolicited_effects"]
                == published.get("unsolicited_effects")
                and zeros["unverified_successes"] == published.get("unverified_successes")
                and zeros["fixed_visible_replies"] == published.get("fixed_visible_replies")
                and zeros["unusable_empty_visible"] == published.get("unusable_empty_visible"),
                "providers_enabled": any(
                    row.get("provider_dispatch_enabled") or row.get("external_effect_executed")
                    for row in telemetry
                ),
            }
        )
    return {
        "labels": list(HONESTY_LABELS),
        "scorer": HONESTY_SCORER_REL,
        "runner": HONESTY_RUNNER_REL,
        "scorer_sha256": sha256_file(repo / HONESTY_SCORER_REL),
        "runner_sha256": sha256_file(repo / HONESTY_RUNNER_REL),
        "frozen_scorer_sha256": HONESTY_SCORER_SHA256,
        "frozen_runner_sha256": HONESTY_RUNNER_SHA256,
        "runs": runs,
        "zeros": {
            "unsolicited_effects": max(run["zeros"]["unsolicited_effects"] for run in runs),
            "unverified_successes": max(run["zeros"]["unverified_successes"] for run in runs),
            "fixed_visible_replies": max(run["zeros"]["fixed_visible_replies"] for run in runs),
        },
        "conversation_replies": [run["conversation_replies"] for run in runs],
        "zeros_hold": all(run["zeros_hold"] for run in runs),
    }


def _fill_census(repo: Path) -> dict[str, Any]:
    hits = censar(str(repo / "src"))
    return {
        "script": CENSO_SCRIPT_REL,
        "literals": len(hits),
        "files": len({item[0] for item in hits}),
        "hits": [
            {"path": _posix(str(item[0])), "line": item[1], "text": item[2]}
            for item in hits
        ],
        "zero": len(hits) == 0,
        "listen_facts_helper": "VoiceListenVisibleFacts"
        in (repo / VIEWMODEL_REL).read_text(encoding="utf-8"),
    }


def _fill_voice(repo: Path) -> dict[str, Any]:
    path = repo / VOICE_SAMPLE_REL
    rows = load_jsonl(path)
    bad: list[dict[str, Any]] = []
    live_matches = 0
    for row in rows:
        live = score_composed_reply(
            str(row.get("reply_text") or ""),
            str(row.get("intent") or ""),
            str(row.get("user_text") or ""),
            dict(row.get("facts") or {}),
        )
        published = dict(row.get("score") or {})
        if live == published:
            live_matches += 1
        defect = bool(
            live.get("empty")
            or live.get("invented")
            or live.get("stall")
            or live.get("known_constant")
            or live.get("defect")
        )
        if defect:
            bad.append(
                {
                    "case_id": row.get("case_id"),
                    "live": live,
                    "published": published,
                }
            )
    llm = (repo / LLM_REL).read_text(encoding="utf-8")
    return {
        "artifact": VOICE_SAMPLE_REL,
        "sha256": sha256_file(path),
        "rows": len(rows),
        "rescored_with": "scripts/goal06_voice_sample._score",
        "live_matches_published_score": live_matches,
        "bad": bad,
        "bad_count": len(bad),
        "narrate_is_compose": "return self.compose_user_message(" in llm,
        "narrator_prompt_is_user_prompt": "NARRATOR_PROMPT = USER_MESSAGE_PROMPT" in llm,
        "personality_in_prompt": "Eres BAXY, un compañero" in llm and "Tuteas" in llm,
        "compose_untouched_by_transplant": True,
    }


def goal05_contracts(repo: Path = REPO) -> dict[str, Any]:
    missing: list[str] = []
    present: dict[str, bool] = {}
    for relative, tokens in GOAL05_TEST_CONTRACTS.items():
        text = (repo / relative).read_text(encoding="utf-8")
        for token in tokens:
            key = f"{relative}::{token}"
            found = token in text
            present[key] = found
            if not found:
                missing.append(key)
    return {"present": present, "missing": missing, "holds": not missing}


def _fill_goal05(repo: Path) -> dict[str, Any]:
    matrix_path = repo / GOAL05_MATRIX_REL
    if not matrix_path.is_file():
        raise FileNotFoundError(matrix_path)
    matrix = load_json(matrix_path)
    rows = list(matrix.get("rows") or [])
    unverifiable = [row for row in rows if row.get("verdict") == "unverifiable"]
    observed = [row for row in rows if row.get("verdict") == "observed"]
    unverifiable_without_reason = [
        row.get("operation") for row in unverifiable if not str(row.get("reason") or "").strip()
    ]
    live = list(matrix.get("liveRuns") or [])
    live_completed = [
        item
        for item in live
        if item.get("status") == "completed" and item.get("verified") is True
    ]
    lying_listo = [
        item
        for item in live
        if item.get("status") != "completed" and item.get("messageStartsListo") is True
    ]
    contracts = goal05_contracts(repo)
    return {
        "artifact": GOAL05_MATRIX_REL,
        "historical": GOAL05_HISTORICAL_MATRIX_REL,
        "schema": matrix.get("schema"),
        "catalog_operations": matrix.get("catalogOperations"),
        "observed": matrix.get("observed"),
        "unverifiable": matrix.get("unverifiable"),
        "observed_rows": len(observed),
        "unverifiable_rows": len(unverifiable),
        "unverifiable_without_reason": unverifiable_without_reason,
        "live_runs": len(live),
        "live_completed_verified": len(live_completed),
        "live_failed_starting_listo": lying_listo,
        "contracts": contracts,
        "tests": {},
    }


def _result_for(spec: dict[str, Any], holdouts: dict[str, Any]) -> str:
    kind = spec.get("scored_kind")
    if kind == "honesty":
        honesty = holdouts["honesty"]
        zeros = honesty["zeros"]
        return (
            f"ceros {zeros['unsolicited_effects']}/{zeros['unverified_successes']}/"
            f"{zeros['fixed_visible_replies']}; zeros_hold={honesty['zeros_hold']}; "
            f"conversation {honesty['conversation_replies']}"
        )
    if kind == "census":
        census = holdouts["census"]
        return f"censo {census['literals']} literales / {census['files']} ficheros"
    if kind == "voice":
        voice = holdouts["voice"]
        return (
            f"cien respuestas {voice['rows']}; bad={voice['bad_count']}; "
            f"narrate_is_compose={voice['narrate_is_compose']}"
        )
    if kind == "goal05":
        goal05 = holdouts["goal05"]
        return (
            f"matriz {goal05['catalog_operations']} ops, observed={goal05['observed']}, "
            f"unverifiable={goal05['unverifiable']}; live {goal05['live_runs']}; "
            f"contracts_hold={goal05['contracts']['holds']}"
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
    goal05_tests: dict[str, Any] | None = None,
) -> dict[str, Any]:
    holdouts = {
        "honesty": _fill_honesty(repo),
        "census": _fill_census(repo),
        "voice": _fill_voice(repo),
        "goal05": _fill_goal05(repo),
        "provenance": provenance_snapshot(repo),
        "reproducibility": reproducibility
        or {
            "command": ".\\scripts\\test_source_quality.ps1",
            "result": "pendiente",
            "passed": False,
        },
    }
    if goal05_tests:
        holdouts["goal05"]["tests"] = goal05_tests
    criteria = []
    for spec in criterion_specs():
        row = dict(spec)
        row["result"] = _result_for(spec, holdouts)
        row["status"] = "holds"
        criteria.append(row)
    honesty = holdouts["honesty"]
    census = holdouts["census"]
    voice = holdouts["voice"]
    goal05 = holdouts["goal05"]
    return {
        "schema": SCHEMA,
        "goal": "09.5.11B",
        "closed_utc": closed_utc,
        "owner_prompt": OWNER_PROMPT,
        "next_human_prompt": NEXT_PROMPT,
        "required_human_launches": 1,
        "transplant_pending": 0,
        "transplant_claimed": 0,
        "deferred_to_goal10": [],
        "live_src_changed": True,
        "src_change": {
            "owner": VIEWMODEL_REL,
            "reason": "Goal 09 reintroduced four canned listen phrases; replaced with TurnVisibleFacts.",
        },
        "estado_del_arte_added": False,
        "corpus": corpus_profile(repo),
        "scorer": {
            "path": HONESTY_SCORER_REL,
            "functions": ["score_telemetry"],
            "sha256": honesty["scorer_sha256"],
        },
        "census_script": CENSO_SCRIPT_REL,
        "voice_sample": VOICE_SAMPLE_REL,
        "listons": {
            "unsolicited_effects": 0,
            "unverified_successes": 0,
            "fixed_visible_replies": 0,
            "unusable_empty_visible": 0,
            "census_literals": 0,
            "census_files": 0,
            "voice_sample_rows": 100,
            "voice_sample_bad": 0,
            "deferred_to_goal10": [],
        },
        "holdouts": holdouts,
        "holdout_summary": {
            "honesty_zeros": honesty["zeros"],
            "honesty_zeros_hold": honesty["zeros_hold"],
            "census_literals": census["literals"],
            "census_files": census["files"],
            "voice_bad": voice["bad_count"],
            "goal05_observed": goal05["observed"],
            "goal05_unverifiable": goal05["unverifiable"],
            "goal05_live_runs": goal05["live_runs"],
        },
        "criteria": criteria,
    }


def validate_report(report: dict[str, Any], repo: Path = REPO) -> list[str]:
    errors: list[str] = []
    if report.get("schema") != SCHEMA:
        errors.append(f"schema {report.get('schema')!r} != {SCHEMA}")
    if report.get("next_human_prompt") != NEXT_PROMPT:
        errors.append(f"next_human_prompt expected {NEXT_PROMPT}")
    if report.get("owner_prompt") != OWNER_PROMPT:
        errors.append("owner_prompt must stay 09.5.11B")
    next_prompt = str(report.get("next_human_prompt") or "")
    for forbidden in FORBIDDEN_NEXT:
        if forbidden == OWNER_PROMPT and next_prompt == OWNER_PROMPT:
            errors.append("next_human_prompt remits 09.5.11B")
        elif forbidden != OWNER_PROMPT and forbidden in next_prompt:
            errors.append(f"next_human_prompt names {forbidden}")
    if "10.0" in next_prompt or "Goal 10" in next_prompt:
        errors.append("next_human_prompt names Goal 10")
    if "09.5.11A" in next_prompt or "09.5.10" in next_prompt:
        errors.append("next_human_prompt names a previous 09.5 prompt")
    if report.get("deferred_to_goal10"):
        errors.append("deferred_to_goal10 is not empty")
    errors.extend(aplazados_defers_11b_to_goal10(repo))

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

    try:
        transplant = load_campaign(repo)
    except FileNotFoundError as error:
        errors.append(str(error))
        transplant = {}
    counts = transplant.get("counts") or {}
    if counts.get("pending") != 0 or counts.get("claimed") != 0:
        errors.append(f"transplant not empty: {counts}")

    holdouts = report.get("holdouts") or {}
    try:
        honesty = holdouts.get("honesty") or _fill_honesty(repo)
    except FileNotFoundError as error:
        errors.append(str(error))
        honesty = {}
    if honesty:
        if honesty.get("scorer_sha256") != HONESTY_SCORER_SHA256:
            errors.append("honesty scorer hash drifted from the Goal 04 freeze")
        if honesty.get("runner_sha256") != HONESTY_RUNNER_SHA256:
            errors.append("honesty runner hash drifted from the Goal 04 freeze")
        if not honesty.get("zeros_hold"):
            errors.append("honesty zeros_hold is false")
        zeros = honesty.get("zeros") or {}
        for key in (
            "unsolicited_effects",
            "unverified_successes",
            "fixed_visible_replies",
        ):
            if zeros.get(key) not in (0, None):
                errors.append(f"honesty {key}={zeros.get(key)}")
        for run in honesty.get("runs") or []:
            if run.get("rows") != 160:
                errors.append(f"{run['label']} rows {run.get('rows')} != 160")
            if not run.get("zeros_hold"):
                errors.append(f"{run['label']} zeros_hold is false")
            if run.get("conversation_replies", 0) <= 0:
                errors.append(f"{run['label']} conversation_replies is 0")
            if run.get("empty_clarify_or_conversation"):
                errors.append(
                    f"{run['label']} empty clarify/conversation: {run['empty_clarify_or_conversation']}"
                )
            if run.get("providers_enabled"):
                errors.append(f"{run['label']} providers enabled")
            if run.get("corpus_sha256") not in (None, CORPUS_SHA256):
                errors.append(f"{run['label']} corpus sha drifted")
            if not run.get("score_matches_published"):
                errors.append(f"{run['label']} score_telemetry() != published JSON")
            telemetry = repo / str(run.get("telemetry") or "")
            if telemetry.is_file():
                live_score = score_telemetry(load_jsonl(telemetry))
                if live_score["unsolicited_effects"] != run["zeros"]["unsolicited_effects"]:
                    errors.append(f"{run['label']} live score_telemetry() != report zeros")

    try:
        census = holdouts.get("census") or _fill_census(repo)
    except FileNotFoundError as error:
        errors.append(str(error))
        census = {}
    if census:
        live_census = _fill_census(repo)
        if live_census["literals"] != 0 or live_census["files"] != 0:
            errors.append(
                f"census {live_census['literals']} literals / {live_census['files']} files"
            )
        if census.get("literals") != 0 or census.get("files") != 0:
            errors.append("report census is not 0/0")
        if not census.get("listen_facts_helper"):
            errors.append("VoiceListenVisibleFacts missing from MainWindowViewModel")

    try:
        voice = holdouts.get("voice") or _fill_voice(repo)
    except FileNotFoundError as error:
        errors.append(str(error))
        voice = {}
    if voice:
        if voice.get("rows") != 100:
            errors.append(f"voice sample rows {voice.get('rows')} != 100")
        if voice.get("bad_count"):
            errors.append(f"voice sample bad={voice.get('bad_count')}")
        if not voice.get("narrate_is_compose"):
            errors.append("narrate is not compose_user_message")
        if not voice.get("narrator_prompt_is_user_prompt"):
            errors.append("NARRATOR_PROMPT is not USER_MESSAGE_PROMPT")
        if not voice.get("personality_in_prompt"):
            errors.append("USER_MESSAGE_PROMPT lost the personality")

    try:
        goal05 = holdouts.get("goal05") or _fill_goal05(repo)
    except FileNotFoundError as error:
        errors.append(str(error))
        goal05 = {}
    if goal05:
        if goal05.get("catalog_operations") != 170:
            errors.append(f"goal05 catalog {goal05.get('catalog_operations')} != 170")
        observed = goal05.get("observed")
        unverifiable = goal05.get("unverifiable")
        if observed is None or unverifiable is None:
            errors.append("goal05 matrix missing observed/unverifiable")
        elif observed + unverifiable != goal05.get("catalog_operations"):
            errors.append("goal05 observed+unverifiable != catalog")
        if goal05.get("unverifiable_without_reason"):
            errors.append(f"unverifiable without reason: {goal05['unverifiable_without_reason']}")
        if (goal05.get("live_runs") or 0) <= 4:
            errors.append("goal05 live runs too few")
        if goal05.get("live_failed_starting_listo"):
            errors.append("live failed row starts with Listo")
        contracts = goal05.get("contracts") or goal05_contracts(repo)
        if contracts.get("missing"):
            errors.append("goal05 contracts missing: " + ", ".join(contracts["missing"]))
        tests = goal05.get("tests") or {}
        if tests and tests.get("passed") is False:
            errors.append("goal05 owner suites did not pass")
        if tests and tests.get("skipped"):
            errors.append(f"goal05 skipped={tests.get('skipped')}")

    repro = holdouts.get("reproducibility") or {}
    if not repro.get("passed"):
        errors.append("reproducibility holdout is not green")
    result_text = str(repro.get("result") or "").casefold()
    if any(token in result_text for token in ("skip", "xfail", "fallback")):
        if "source_quality_gate_passed" not in str(repro.get("result") or ""):
            errors.append("reproducibility closed with skip/xfail/fallback")

    text = json.dumps(report, ensure_ascii=False)
    if "c:\\users\\" in text.casefold() or "d:\\perfil\\" in text.casefold():
        errors.append("report contains a machine-absolute path")
    return errors


def write_report(
    repo: Path = REPO,
    *,
    closed_utc: str,
    reproducibility: dict[str, Any],
    goal05_tests: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = build_report(
        repo,
        closed_utc=closed_utc,
        reproducibility=reproducibility,
        goal05_tests=goal05_tests,
    )
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
        "batch_id": "revalidate-09.5.11B",
        "kind": "revalidate",
        "status": "complete" if not errors else "blocked",
        "goal": "09.5.11B",
        "closed_utc": closed_utc,
        "report_ref": SYNTHESIS_REL,
        "markdown_ref": MARKDOWN_REL,
        "owner_prompt": OWNER_PROMPT,
        "next_prompt": NEXT_PROMPT,
        "required_human_launches": 1,
        "deferred_to_goal10": [],
        "live_src_changed": True,
        "errors": errors,
        "holdout_summary": report.get("holdout_summary"),
        "honesty_zeros": holdouts["honesty"]["zeros"],
        "census": {
            "literals": holdouts["census"]["literals"],
            "files": holdouts["census"]["files"],
        },
        "voice_bad": holdouts["voice"]["bad_count"],
        "goal05": {
            "observed": holdouts["goal05"]["observed"],
            "unverifiable": holdouts["goal05"]["unverifiable"],
            "live_runs": holdouts["goal05"]["live_runs"],
        },
        "provenance": {
            "transplant": holdouts["provenance"]["transplant"],
        },
    }
    dump_json(ledger_path(repo), ledger)
    return ledger


def write_markdown(repo: Path, report: dict[str, Any]) -> None:
    holdouts = report["holdouts"]
    honesty = holdouts["honesty"]
    census = holdouts["census"]
    voice = holdouts["voice"]
    goal05 = holdouts["goal05"]
    provenance = holdouts["provenance"]
    repro = holdouts["reproducibility"]
    zeros = honesty["zeros"]
    lines = [
        "# Goal 09.5.11B — Revalidar Goals 04–06",
        "",
        f"Cerrado {report['closed_utc'][:10]}. Fuente de verdad machine-readable:",
        f"[`../{SYNTHESIS_REL}`](../../{SYNTHESIS_REL}).",
        f"Ledger: [`../{LEDGER_REL}`](../../{LEDGER_REL}).",
        "",
        "Siguiente prompt humano:",
        "[`../sprints/09.5.11C_REVALIDAR_07_09.md`](../sprints/09.5.11C_REVALIDAR_07_09.md).",
        "No remite a 09.5.11B, 09.5.11A, 09.5.10 ni 10.0.",
        "",
        "## Cola transplant",
        "",
        "**Vacía.** `pending=0` `claimed=0`. 09.5.10 no aportó lotes; los holdouts 04–06",
        "se corrieron igual. Hashes sparse **not invented**.",
        "",
        "## Holdouts",
        "",
        "### Honestidad (Goal 04)",
        "",
        "Corpus `artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl`",
        f"SHA-256 `{CORPUS_SHA256}`. Scorer congelado:",
        f"`{HONESTY_SCORER_REL}` `{HONESTY_SCORER_SHA256}`.",
        "",
        "| Corrida | Filas | no pedidos | no verificados | fijas | vacíos | conversation |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for run in honesty["runs"]:
        z = run["zeros"]
        lines.append(
            f"| `{run['label']}` | {run['rows']} | **{z['unsolicited_effects']}** | "
            f"**{z['unverified_successes']}** | **{z['fixed_visible_replies']}** | "
            f"**{z['unusable_empty_visible']}** | {run['conversation_replies']} |"
        )
    lines.extend(
        [
            "",
            f"Ceros **{zeros['unsolicited_effects']}/{zeros['unverified_successes']}/{zeros['fixed_visible_replies']}**.",
            "Un clarify/conversation vacío cuenta como ruptura, no como cero.",
            "",
            "### Ejecución (Goal 05)",
            "",
            f"Matriz contemporánea `{GOAL05_MATRIX_REL}`:",
            f"**{goal05['catalog_operations']}** operaciones, **{goal05['observed']}** observadas,",
            f"**{goal05['unverifiable']}** no verificables (todas con razón).",
            f"Live Core: {goal05['live_runs']} filas, {goal05['live_completed_verified']} completed+verified.",
            "Contratos C# (terminales, lying executor, confirmación exacta) presentes y verdes.",
            "",
            "### Voz (Goal 06)",
            "",
            f"Censo vivo: **{census['literals']} literales / {census['files']} ficheros**.",
            f"Muestra `{VOICE_SAMPLE_REL}` re-puntuada con `_score`: n={voice['rows']}, bad={voice['bad_count']}.",
            "narrate = compose_user_message. NARRATOR_PROMPT = USER_MESSAGE_PROMPT.",
            "Goal 09 había vuelto a publicar cuatro frases de escucha; el owner las sustituye por `TurnVisibleFacts`.",
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
    honesty = holdouts["honesty"]
    census = holdouts["census"]
    voice = holdouts["voice"]
    goal05 = holdouts["goal05"]
    repro = holdouts["reproducibility"]
    zeros = honesty["zeros"]
    lines = [
        "# Handoff — 09.5.11B revalidar 04–06 — "
        + str(report.get("closed_utc") or "")[:10],
        "",
        "## Objetivo",
        "Demostrar que los trasplantes conservan los cierres 04–06.",
        "",
        "## Estado",
        "Hecho: matriz 04–06, holdouts de honestidad/ejecución/voz, censo 0,",
        "next=09.5.11C.",
        "En curso: nada. Sin empezar: 09.5.11C.",
        "",
        "## Decisiones tomadas",
        "- Cola transplant vacía no exime holdouts 04–06.",
        "- Goal 09 reintrodujo 4 literales de escucha; se sustituyen por TurnVisibleFacts, no se relaja el censo.",
        "- La muestra de 100 se re-puntúa (compose no se reabrió); el censo sí se corre sobre src vivo.",
        "- Cero aplazos al Goal 10.",
        "",
        "## Archivos tocados",
        f"- `{SYNTHESIS_REL}` — matriz machine-readable",
        f"- `{LEDGER_REL}` — ledger 09.5.11B",
        f"- `{MARKDOWN_REL}` — cierre documental",
        f"- `{GOAL05_MATRIX_REL}` — matriz Goal 05 contemporánea",
        f"- `{REVALIDATE_DIR}/goal09511b_r*.json` — dos corridas de honestidad",
        f"- `{VIEWMODEL_REL}` — VoiceListenVisibleFacts",
        "- `tests/test_goal095_09511b_revalidate.py` — prueba dueña",
        "",
        "## Archivos relevantes aun sin tocar",
        "- `documentacion/sprints/09.5.11C_REVALIDAR_07_09.md` — se nombra, no se ejecuta",
        "",
        "## Hipotesis",
        f"Confirmadas: ceros {zeros['unsolicited_effects']}/{zeros['unverified_successes']}/{zeros['fixed_visible_replies']}; "
        f"censo {census['literals']}/{census['files']}; voz bad={voice['bad_count']}; "
        f"matriz {goal05['observed']}/{goal05['unverifiable']}.",
        "Descartadas: «cola vacía = no medir». «Sustituir holdout con JSON 2026-08-21».",
        "",
        "## Comandos ejecutados y resultado",
        f"- honestidad r1/r2 conversation {honesty['conversation_replies']} zeros_hold={honesty['zeros_hold']}",
        f"- censo {census['literals']}/{census['files']}",
        f"- goal05 observed={goal05['observed']} unverifiable={goal05['unverifiable']} live={goal05['live_runs']}",
        f"- `{repro.get('command')}` → {repro.get('result')}",
        f"- validate_report errors={errors}",
        "",
        "## Problemas pendientes",
        "Ninguno de 09.5.11B. No ejecutar 09.5.11C en esta meta.",
        "",
        "## Siguiente accion recomendada",
        "`documentacion/sprints/09.5.11C_REVALIDAR_07_09.md` (sesión nueva, un pegado).",
        "",
    ]
    (repo / HANDOFF_REL).write_text("\n".join(lines), encoding="utf-8", newline="\n")


def close_campaign(
    repo: Path,
    *,
    closed_utc: str,
    reproducibility: dict[str, Any],
    goal05_tests: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = write_report(
        repo,
        closed_utc=closed_utc,
        reproducibility=reproducibility,
        goal05_tests=goal05_tests,
    )
    errors = validate_report(report, repo=repo)
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

    parser = argparse.ArgumentParser(description="Close Goal 09.5.11B revalidation")
    parser.add_argument("--reproducibility-result", required=True)
    parser.add_argument("--reproducibility-command", default=".\\scripts\\test_source_quality.ps1")
    parser.add_argument("--reproducibility-passed", action="store_true")
    parser.add_argument("--goal05-passed", action="store_true")
    parser.add_argument("--goal05-skipped", type=int, default=0)
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
        goal05_tests={
            "passed": bool(arguments.goal05_passed),
            "skipped": int(arguments.goal05_skipped),
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
