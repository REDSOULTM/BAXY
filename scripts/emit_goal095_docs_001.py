"""Emit the condensed docs-001-carter ledger. Data-only; no product code."""

from __future__ import annotations

from pathlib import Path

from scripts.goal095_docs_ledger import (
    SCHEMA,
    TOKEN_LIMIT,
    TOKEN_TARGET,
    dump_json,
    load_json,
    queue_paths,
)

REPO = Path(__file__).resolve().parents[1]
HEAD = "9cf62d236cdef08012897d3c8c680b8afef0d62e"
HW = "RTX 4060 Ti 16 GB · Windows · Carter OS AI snapshot 09.5.0"
ROOT = "Programacion/Carter OS AI"

RANGES = {
    "docs/investigaciones/La razon de carter/00_RESUMEN_EJECUTIVO.md": ["1-70"],
    "docs/investigaciones/La razon de carter/01_TESIS_DE_CARTER.md": ["1-16", "28-42"],
    "docs/investigaciones/La razon de carter/02_MAPA_DE_COMPETIDORES.md": ["1-20", "56-72"],
    "docs/investigaciones/La razon de carter/03_COMPARACION_TECNICA_PROFUNDA.md": ["1-22", "52-78"],
    "docs/investigaciones/La razon de carter/04_POR_QUE_CARTER_FUNCIONA_COMO_PRODUCTO_FINAL.md": ["1-41"],
    "docs/investigaciones/La razon de carter/05_POR_QUE_CARTER_PODRIA_FRACASAR.md": ["1-54"],
    "docs/investigaciones/La razon de carter/06_DEFENSA_COMO_TESIS.md": ["1-47"],
    "docs/investigaciones/La razon de carter/07_ARGUMENTO_CONTRA_COMPETIDORES.md": ["1-39"],
    "docs/investigaciones/La razon de carter/08_ROADMAP_PARA_HACERLO_INDISCUTIBLE.md": ["1-53"],
    "docs/investigaciones/La razon de carter/09_VEREDICTO_FINAL.md": ["1-43"],
    "docs/investigaciones/La razon de carter/GUIA_ORADOR_DEFENSA_CARTER.md": ["1-42", "139-185"],
    "docs/investigaciones/La razon de carter/README.md": ["1-68"],
    "docs/investigaciones/evidencia pruebas gemma4/Contrato.md": ["1-40"],
    "docs/investigaciones/evidencia pruebas gemma4/GEMMA4_VALIDACION_COMPLETA.md": ["1-45"],
    "docs/investigaciones/evidencia pruebas gemma4/README.md": ["1-90"],
    "docs/investigaciones/evidencia pruebas gemma4/REPORTE.md": ["1-80"],
    "legacy/Carter_v2/AUTO_MODEL_STACK_FINAL_AUDIT.md": ["1-20", "64-77"],
    "legacy/Carter_v2/AUTO_MODEL_STACK_FINAL_REPORT.md": ["1-72"],
    "legacy/Carter_v2/CARTER_MODEL_LAB_REPORT.md": ["1-73", "143-193"],
    "legacy/Carter_v2/CARTER_MODEL_RECOMMENDATION.md": ["1-55"],
    "legacy/Carter_v2/CARTER_TEXT_CORE_RC_AUDIT.md": ["1-53"],
    "legacy/Carter_v2/CARTER_TEXT_CORE_RELEASE_NOTES.md": ["1-74"],
    "legacy/Carter_v2/CODEBASE_DIET_PLAN.md": ["1-25"],
    "legacy/Carter_v2/FULL_LIVE_LLM_TEST_AUDIT.md": ["1-24"],
    "legacy/Carter_v2/LLM_AUTONOMY_BOUNDARY.md": ["1-70"],
    "legacy/Carter_v2/LLM_CONTEXT_MEMORY_AUDIT.md": ["1-50", "105-146"],
    "legacy/Carter_v2/LLM_CONTEXT_MEMORY_REPORT.md": ["1-40"],
    "legacy/Carter_v2/MODEL_CANDIDATES_BY_VRAM.md": ["1-54"],
    "legacy/Carter_v2/MODEL_COMPATIBILITY_BIAS_AUDIT.md": ["1-47", "63-117"],
    "legacy/Carter_v2/MODEL_DOWNLOAD_LOG.md": ["1-67"],
    "legacy/Carter_v2/MODEL_DOWNLOAD_PLAN.md": ["1-56"],
    "legacy/Carter_v2/MODEL_HARDWARE_PROFILES.md": ["1-100"],
    "legacy/Carter_v2/MODEL_LAB_AUDIT.md": ["1-80"],
    "legacy/Carter_v2/MODEL_LAB_WAVE2_AUDIT.md": ["1-85"],
    "legacy/Carter_v2/MODEL_RESEARCH_MATRIX.md": ["1-96"],
    "legacy/Carter_v2/MODEL_STACK_BY_VRAM.md": ["1-84"],
    "legacy/Carter_v2/MODEL_STORAGE_CLEANUP_PLAN.md": ["1-55"],
    "legacy/Carter_v2/MODEL_STT_TOURNAMENT_REPORT.md": ["1-40"],
    "legacy/Carter_v2/MODEL_TOURNAMENT_REPORT.md": ["1-84"],
    "legacy/Carter_v2/MODEL_TTS_TOURNAMENT_REPORT.md": ["1-40"],
    "legacy/Carter_v2/MODEL_VISION_TOURNAMENT_REPORT.md": ["1-40"],
    "legacy/Carter_v2/MODEL_VOICE_TOURNAMENT_REPORT.md": ["1-40"],
    "legacy/Carter_v2/PRE_LLM_LATENCY_REPORT.md": ["1-50"],
    "legacy/Carter_v2/README.md": ["1-96"],
    "legacy/Carter_v2/REAL_RUNTIME_FAILURE_AUDIT.md": ["1-90"],
    "legacy/Carter_v2/REAL_RUNTIME_LIVE_REPRO_REPORT.md": ["1-99"],
    "legacy/Carter_v2/REPO_CLEANUP_AUDIT.md": ["1-58", "140-150"],
    "legacy/Carter_v2/RESIDUAL_BACKLOG_AFTER_BLOCK.md": ["1-168"],
    "legacy/Carter_v2/RESIDUAL_BACKLOG_V2.md": ["1-109"],
    "legacy/Carter_v2/RUNTIME_TOOL_PROTOCOL_WIRING_AUDIT.md": ["1-50"],
    "legacy/Carter_v2/TEXT_CORE_ARCHITECTURE.md": ["1-90"],
    "legacy/Carter_v2/TEXT_CORE_CLEANUP_PLAN.md": ["1-59"],
    "legacy/Carter_v2/TEXT_CORE_INVARIANTS.md": ["1-27"],
    "legacy/Carter_v2/TEXT_CORE_MODEL_DECISION.md": ["1-45"],
    "legacy/Carter_v2/TEXT_CORE_PERFORMANCE_FINAL.md": ["1-77"],
    "legacy/Carter_v2/TEXT_CORE_SOAK_TEST_REPORT.md": ["1-27"],
    "legacy/Carter_v2/TOOL_CALL_COMPATIBILITY_AUDIT.md": ["1-80", "126-147"],
    "legacy/Carter_v2/ULTRA_LATENCY_AUDIT.md": ["1-40"],
    "legacy/Carter_v2/VOICE_CAMERA_HANDOFF_PLAN.md": ["1-54"],
    "legacy/Carter_v2/VOICE_MODEL_RESEARCH.md": ["1-70"],
    "legacy/Carter_v2/audit/baselines/historical/F0_prompt_template.txt": ["1-40"],
    "legacy/Carter_v2/audit/logs/historical/f8_test_summary.txt": ["1-13"],
    "legacy/Carter_v2/audit/results/CARTER_DEFAULT_SWITCH_AUDIT.md": ["1-56"],
    "legacy/Carter_v2/audit/results/CARTER_GLOBAL_RUNTIME_AUDIT.md": ["1-86"],
    "legacy/Carter_v2/audit/results/CARTER_MODEL_REBASELINE_AUDIT.md": ["1-40"],
    "legacy/Carter_v2/audit/results/CARTER_RUNTIME_STABILITY_AUDIT.md": ["1-120"],
    "legacy/Carter_v2/audit/results/CARTER_TEXT_BLOCK_LANDING_AUDIT.md": ["1-40", "91-118"],
    "legacy/Carter_v2/audit/results/CARTER_TEXT_BLOCK_LANDING_V2_AUDIT.md": ["1-38", "155-180"],
    "legacy/Carter_v2/audit/results/FULL_LIVE_LLM_VALIDATION_SUMMARY.md": ["1-40"],
    "legacy/Carter_v2/audit/results/SKIPPED_LIVE_VALIDATION_SUMMARY.md": ["1-39"],
    "legacy/Carter_v2/audit/results/model_benchmarks_fair_runtime/CONSOLIDATED.md": ["1-63"],
    "legacy/Carter_v2/audit/results/post_model_lab_gates_20260502-092159.txt": ["1-11"],
}


def _prov(path: str, date: str, model: str, ranges: list[str] | None = None) -> dict:
    return {
        "path": path,
        "ranges": ranges or RANGES[path],
        "date": date,
        "hardware": HW,
        "model": model,
        "commit": HEAD,
    }


def _card(**kwargs: object) -> dict:
    required = (
        "card_id",
        "claim_kind",
        "problem",
        "outcome",
        "solution_or_failure",
        "causal_mechanism",
        "measurement",
        "provenance",
        "limitations",
        "validity",
        "current_piece",
        "source_files",
        "repeats",
    )
    missing = [key for key in required if key not in kwargs]
    if missing:
        raise RuntimeError(missing)
    return dict(kwargs)


def cards() -> list[dict]:
    razon = [
        "docs/investigaciones/La razon de carter/00_RESUMEN_EJECUTIVO.md",
        "docs/investigaciones/La razon de carter/01_TESIS_DE_CARTER.md",
        "docs/investigaciones/La razon de carter/02_MAPA_DE_COMPETIDORES.md",
        "docs/investigaciones/La razon de carter/04_POR_QUE_CARTER_FUNCIONA_COMO_PRODUCTO_FINAL.md",
        "docs/investigaciones/La razon de carter/06_DEFENSA_COMO_TESIS.md",
        "docs/investigaciones/La razon de carter/07_ARGUMENTO_CONTRA_COMPETIDORES.md",
        "docs/investigaciones/La razon de carter/08_ROADMAP_PARA_HACERLO_INDISCUTIBLE.md",
        "docs/investigaciones/La razon de carter/09_VEREDICTO_FINAL.md",
        "docs/investigaciones/La razon de carter/GUIA_ORADOR_DEFENSA_CARTER.md",
        "docs/investigaciones/La razon de carter/README.md",
    ]
    model_lab = [
        "legacy/Carter_v2/AUTO_MODEL_STACK_FINAL_AUDIT.md",
        "legacy/Carter_v2/CARTER_MODEL_LAB_REPORT.md",
        "legacy/Carter_v2/CARTER_MODEL_RECOMMENDATION.md",
        "legacy/Carter_v2/MODEL_CANDIDATES_BY_VRAM.md",
        "legacy/Carter_v2/MODEL_DOWNLOAD_LOG.md",
        "legacy/Carter_v2/MODEL_DOWNLOAD_PLAN.md",
        "legacy/Carter_v2/MODEL_HARDWARE_PROFILES.md",
        "legacy/Carter_v2/MODEL_LAB_AUDIT.md",
        "legacy/Carter_v2/MODEL_LAB_WAVE2_AUDIT.md",
        "legacy/Carter_v2/MODEL_RESEARCH_MATRIX.md",
        "legacy/Carter_v2/MODEL_STACK_BY_VRAM.md",
        "legacy/Carter_v2/MODEL_STORAGE_CLEANUP_PLAN.md",
        "legacy/Carter_v2/MODEL_TOURNAMENT_REPORT.md",
    ]
    return [
        _card(
            card_id="tesis-nicho-windows-verificable",
            claim_kind="documental",
            problem="Carter no es AGI ni Jarvis universal; competidores ganan en GUI research, coding agents y cloud.",
            outcome="contexto",
            solution_or_failure="Nicho: asistente local Windows-first privado y verificable. Tesis academica = menos fake success, no 'construir un asistente'.",
            causal_mechanism="La ventaja declarada es verificacion post-accion + tools tipadas + privacidad local, no superioridad VLM/OSWorld.",
            measurement="55 tools cargadas; pytest Carter_v4 131 passed (2026-05-08). Hash identico a biblioteca en los 12 docs de La razon.",
            provenance=_prov(
                "docs/investigaciones/La razon de carter/00_RESUMEN_EJECUTIVO.md",
                "2026-05-08",
                "n/a (auditoria documental)",
            ),
            limitations="Auditoria de tesis, no corrida de producto. No mide BAXY actual.",
            validity="mecanismo_reutilizable",
            current_piece="documentacion/00_IDENTIDAD.md (companero local Windows) + invariante 2/3 (no afirmar sin verificar; estados terminales honestos)",
            source_files=razon,
            repeats=["biblioteca/carter/la-razon-de-carter/* es otro corpus (lecciones v1-v4), no estos 12 ficheros"],
        ),
        _card(
            card_id="matrix-540-numeros-en-conflicto",
            claim_kind="documental",
            problem="La misma matrix 540 se cita con cifras incompatibles; el auditor automatico infla PASS.",
            outcome="fracaso",
            solution_or_failure="La razon usa evidencia local 417/540 manual y 489/540 automatico, y rechaza 519/540 del prompt. GEMMA4_VALIDACION_COMPLETA cita 480/540 oficial y ~329/540 PASS REAL (~140 false passes).",
            causal_mechanism="Verifier permisivo + modelo que afirma con confianza. Automatico cuenta tool-ok; humano cuenta intencion cumplida.",
            measurement="417 vs 489 (2026-05-08); 480 oficial vs ~329 real (2026-05-09). Delta ~140 FALSE_PASS.",
            provenance=_prov(
                "docs/investigaciones/La razon de carter/00_RESUMEN_EJECUTIVO.md",
                "2026-05-08",
                "qwen3:4b (Carter v4, citado)",
                ["35-40"],
            ),
            limitations="Ninguna de estas cifras se reejecuto en 09.5.2. Goal 01 ya midio que el recorte de tools 'sin perder calidad' bajo 75.93%→62.96%.",
            validity="historica",
            current_piece="tests de comprehension (03/03B/03C) y scorer: no reutilizar 540 de Carter como gate de BAXY sin redefinir PASS",
            source_files=[
                "docs/investigaciones/La razon de carter/00_RESUMEN_EJECUTIVO.md",
                "docs/investigaciones/evidencia pruebas gemma4/GEMMA4_VALIDACION_COMPLETA.md",
            ],
            repeats=["05_POR_QUE_CARTER_PODRIA_FRACASAR.md L21-22; 08_ROADMAP L14-16"],
        ),
        _card(
            card_id="fake-success-eje-de-tesis",
            claim_kind="documental",
            problem="La peor falla no es fallar: es decir que hizo algo sin haberlo hecho.",
            outcome="fracaso",
            solution_or_failure="Carter v4 declara verify.py + verifier_orchestrator y estados COMPLETED/PARTIAL/FAILED/UNVERIFIED/NEEDS_USER. La matrix automatica aun sobreestima.",
            causal_mechanism="Verifiers superficiales (archivo existe, frame-diff, exit 0, result.ok=True) no comprueban la intencion. Abrir Steam != abrir el juego.",
            measurement="489 automatico vs 417 manual; C07-29 citado: abrio Spotify tras 'no abras nada'.",
            provenance=_prov(
                "docs/investigaciones/La razon de carter/05_POR_QUE_CARTER_PODRIA_FRACASAR.md",
                "2026-05-08",
                "n/a",
                ["39-50"],
            ),
            limitations="Documental. El mute sin read-back de v2 (otra tarjeta) es el mecanismo concreto medido despues.",
            validity="mecanismo_reutilizable",
            current_piece="Goal 04 honestidad + Baxy.Core outcome verificable; no heredar verifier que confia en result.ok",
            source_files=[
                "docs/investigaciones/La razon de carter/05_POR_QUE_CARTER_PODRIA_FRACASAR.md",
                "docs/investigaciones/La razon de carter/03_COMPARACION_TECNICA_PROFUNDA.md",
            ],
            repeats=["00_RESUMEN L21-25; 01_TESIS; GEMMA4 contrato 1.2"],
        ),
        _card(
            card_id="gui-universal-amenaza-tesis",
            claim_kind="documental",
            problem="GUI moderna (CEF/Electron/Steam/Discord/Spotify) rompe UIA/OCR; VLM declarado no activo.",
            outcome="inconcluso",
            solution_or_failure="Cascada UIA→OCR→VLM en gui_universal.py; Agent-S gana en OSWorld/WindowsAgentArena. Carter final no necesita ganar OSWorld pero si apps comunes.",
            causal_mechanism="gui.py usa pyautogui/hotkeys/frame-diff; gui_do opera sobre la ventana enfocada cuando el target no existe.",
            measurement="Sin cifra nueva aqui; C13 GUI debil en reporte 540 citado. Vision tournament posterior es smoke de colores, no UI.",
            provenance=_prov(
                "docs/investigaciones/La razon de carter/03_COMPARACION_TECNICA_PROFUNDA.md",
                "2026-05-08",
                "n/a",
                ["69-78"],
            ),
            limitations="No se ejecuto Agent-S ni GUI de BAXY en esta sesion.",
            validity="mecanismo_reutilizable",
            current_piece="Goal 07 misiones / providers Windows (UIA) y D_ADAPTADORES_POR_APP.md; cascada aun incompleta en Goal 01",
            source_files=["docs/investigaciones/La razon de carter/03_COMPARACION_TECNICA_PROFUNDA.md"],
            repeats=["05 L14-16, L27-35; 08 riesgos"],
        ),
        _card(
            card_id="gemma4-contrato-innegociable",
            claim_kind="documental",
            problem="qwen3:4b fallaba negation, URI invention, multi-step y honestidad; se definio un contrato de 10 capacidades independiente del proveedor.",
            outcome="contexto",
            solution_or_failure="Contrato: function calling multi-tool, honestidad por construccion, negation, multi-step, ES/EN/PT/DE/FR, rule>few-shot, latencia Alexa-tier.",
            causal_mechanism="Si Gemma 4 cumple mejor con otro formato de tools, Carter se adapta (no al reves). PASS = intencion verificable, no 'llamo una tool'.",
            measurement="Targets: trivial <5s max, tool simple <8s, app open <15s. Hardware target RTX 4060 Ti 16 GB.",
            provenance=_prov(
                "docs/investigaciones/evidencia pruebas gemma4/Contrato.md",
                "2026-05-09",
                "Gemma 4 (a evaluar)",
                ["1-40"],
            ),
            limitations="El Contrato.md del snapshot difiere en hash de la copia en biblioteca (DELTA). REPORTE_EXTENDIDO.md no esta en este lote.",
            validity="mecanismo_reutilizable",
            current_piece="invariantes 2-5 y Goal 03/04/06; no copiar el contrato como respuesta fija",
            source_files=["docs/investigaciones/evidencia pruebas gemma4/Contrato.md"],
            repeats=["GEMMA4_VALIDACION_COMPLETA.md §1 duplica el contrato"],
        ),
        _card(
            card_id="gemma4-fase1-diez-tests",
            claim_kind="documental",
            problem="Hacia falta una prueba pequena antes del bench 60, con juez de intencion no de tool-call.",
            outcome="exito",
            solution_or_failure="10 tests del Contrato en llama.cpp Vulkan, 9 stubs. E4B-UD-IQ2_M 9/10; varios quants 8-9/10. Negation 100% PASS en esa tanda.",
            causal_mechanism="FAIL frecuentes: warmup ~14s (no es el modelo), finish_reason=length en cadena read-then-paste, UD-Q2 abandona multi-step.",
            measurement="E4B-IQ2_M 9/10; hola 1.1s (UD-Q2) a 7.4s (E4B-IQ2). Hardware: Vulkan, VRAM ≤6GB declarado en REPORTE.md (tensión con 16 GB del README).",
            provenance=_prov(
                "docs/investigaciones/evidencia pruebas gemma4/REPORTE.md",
                "2026-05-09",
                "Gemma 4 E4B-UD-IQ2_M y quants E2B",
            ),
            limitations="Juez = el autor del reporte (Claude), no scorer congelado. Catálogo de 9 stubs ≠ catálogo BAXY. Goal 01 re-midio E2B Q4_K_XL a 6.3-11.4 s/turno.",
            validity="historica",
            current_piece="src/baxy_mind y runtime Gemma; no tomar 9/10 de 10 stubs como techo 03C 114/124",
            source_files=["docs/investigaciones/evidencia pruebas gemma4/REPORTE.md"],
            repeats=["GEMMA4_VALIDACION L20: 9/10 E2B-Q5 y E4B-IQ2 justifica fase 2"],
        ),
        _card(
            card_id="gemma4-migrar-condicional-no-en-lote",
            claim_kind="documental",
            problem="La decision de migrar a Gemma 4 se declara en README pero el reporte definitivo no esta asignado a este lote.",
            outcome="inconcluso",
            solution_or_failure="README: ganador gemma-4-E4B-it-Q6_K (6.59 GB disco, 7.1 GB VRAM), 57/60 (95%) vs qwen3:4b 55/60 (91.6%), MIGRAR CONDICIONAL porque multi-step p99 27s viola Alexa-tier.",
            causal_mechanism="Cifras viven en REPORTE_EXTENDIDO.md (fuera de docs-001). Este lote solo conserva el puntero.",
            measurement="57/60 vs 55/60; p99 multi-step 27s. No reproducido aqui.",
            provenance=_prov(
                "docs/investigaciones/evidencia pruebas gemma4/README.md",
                "2026-05-09",
                "gemma-4-E4B-it-Q6_K",
                ["21-27"],
            ),
            limitations="Goal 01 midio Gemma-4-E2B QAT Q4_K_XL como runtime actual (6.3-11.4 s) y 'funciona y no sirve' por thinking. No presentar E4B-Q6_K como default vigente.",
            validity="requiere_remeidir",
            current_piece="runtime LLM en BAXY/legacy/models (Goal 01); 09.5.5 sintetiza modelos",
            source_files=[
                "docs/investigaciones/evidencia pruebas gemma4/README.md",
                "docs/investigaciones/evidencia pruebas gemma4/GEMMA4_VALIDACION_COMPLETA.md",
            ],
            repeats=["REPORTE.md es fase 1, no el 57/60"],
        ),
        _card(
            card_id="harness-openai-tools-sesgado",
            claim_kind="documental",
            problem="El torneo M11 marco phi4/gemma3/phi3.5/deepseek-r1 como tool_pass=0.00. No era el modelo: Ollama devolvia HTTP 400 antes de ejecutar.",
            outcome="fracaso",
            solution_or_failure="Re-bench multi-protocolo: json_direct/fenced_json. phi4 10/10 json_direct; gemma3:12b 9/10 fenced_json. Veredicto HARNESS_WAS_BIASED.",
            causal_mechanism="El harness solo enviaba tools=[] nativo y leia message.tool_calls. Modelfile sin bloque {{- if .Tools }} → 400 'does not support tools'. El modelo nunca veia el prompt.",
            measurement="4 modelos recuperados; hermes3:8b openai_tools 0.90 / json_direct tool 1.00. Fair composite hermes3 0.763.",
            provenance=_prov(
                "legacy/Carter_v2/TOOL_CALL_COMPATIBILITY_AUDIT.md",
                "2026-05-02",
                "Ollama OpenAI-compat :11434",
            ),
            limitations="Medicion 2026-05-02 sobre Ollama. BAXY usa llama.cpp + contratos .NET; el mecanismo (un solo canal de tools) sigue siendo una trampa de eval.",
            validity="mecanismo_reutilizable",
            current_piece="eval de FunctionGemma / router y cualquier gate que asuma un unico protocolo de tool-calls",
            source_files=[
                "legacy/Carter_v2/TOOL_CALL_COMPATIBILITY_AUDIT.md",
                "legacy/Carter_v2/MODEL_COMPATIBILITY_BIAS_AUDIT.md",
                "legacy/Carter_v2/RUNTIME_TOOL_PROTOCOL_WIRING_AUDIT.md",
            ],
            repeats=["AUTO_MODEL_STACK_FINAL_REPORT §2-3; CONSOLIDATED.md"],
        ),
        _card(
            card_id="hermes3-fair-no-era-default",
            claim_kind="documental",
            problem="Un leaderboard 'instalado-only' y un harness sesgado hacian ganar a qwen por construccion.",
            outcome="exito",
            solution_or_failure="Selector por 7 perfiles VRAM con leaderboard fair. hermes3:8b gana 8-16 GB (0.763, p95 1597 ms, 4857 MiB) via json_direct. Default real se dejo en qwen3:8b por regla de no cambiar config sin confirmacion.",
            causal_mechanism="qwen3:8b tool_pass fair 1.00 pero p95 31389 ms por thinking; cae a #14 (0.605). llama3.2:3b p95 915 ms. 24 GB: gpt-oss:20b.",
            measurement="16 modelos × 7 protocolos × 5 casos. Disco Ollama ~165 GB. Perfil operador: 16gb RTX 4060 Ti.",
            provenance=_prov(
                "legacy/Carter_v2/AUTO_MODEL_STACK_FINAL_REPORT.md",
                "2026-05-02",
                "hermes3:8b vs qwen3:8b",
            ),
            limitations="hermes3 no se valido live-safe como default. Perfiles 6-24 GB contradicen el techo de producto de 4 GB VRAM (ley 4 / Identidad). Caducado como default de BAXY.",
            validity="caducada",
            current_piece="ley 4 (4 GB techo) y Goal 01 (Gemma E2B actual); no heredar selector de 7 perfiles como arquitectura",
            source_files=model_lab
            + [
                "legacy/Carter_v2/AUTO_MODEL_STACK_FINAL_REPORT.md",
                "legacy/Carter_v2/TEXT_CORE_MODEL_DECISION.md",
                "legacy/Carter_v2/audit/results/model_benchmarks_fair_runtime/CONSOLIDATED.md",
            ],
            repeats=["CARTER_MODEL_RECOMMENDATION.md elige 16gb/qwen3:8b en otra oleada"],
        ),
        _card(
            card_id="mute-sin-readback",
            claim_kind="documental",
            problem="Usuario: 'mutea el pc' → 'El volumen ha sido muteado correctamente' y el PC no estaba muteado.",
            outcome="fracaso",
            solution_or_failure="Propuesta: _verify_mute via volume.GetMute(), analogo a _verify_volume que si hace read-back.",
            causal_mechanism="system_mute usa _verify_synchronous_ok: confirmed si result.ok=True. media.py llama SetMute y devuelve ok sin leer.",
            measurement="Caso #6 del transcript real. Volume-set (#5) eligio terminal+nircmd pese a existir pycaw.",
            provenance=_prov(
                "legacy/Carter_v2/REAL_RUNTIME_FAILURE_AUDIT.md",
                "2026-05-02",
                "qwen3:8b",
                ["9-61"],
            ),
            limitations="Transcript de un usuario + auditoria de codigo v2. No se reprodujo el mute en BAXY.",
            validity="mecanismo_reutilizable",
            current_piece="providers de audio/volumen Windows y Goal 05: verificar efecto, no result.ok",
            source_files=["legacy/Carter_v2/REAL_RUNTIME_FAILURE_AUDIT.md"],
            repeats=["05 fake success; TEXT_CORE_INVARIANTS #4"],
        ),
        _card(
            card_id="gui-do-timeout-fantasma",
            claim_kind="documental",
            problem="close/maximize/mute/frustracion disparan gui_do sobre ventana inexistente o activa; 30 s de UIA y a veces actuan sobre 'Host de ventanas emergentes'.",
            outcome="fracaso",
            solution_or_failure="Window capability no hace fallback a activa; el LLM cae a gui_do. Fix propuesto: si find_window_by_title es None, fail <100 ms. Window guard solo dispara si window_title contiene nouns del usuario.",
            causal_mechanism="gui_do no short-circuit cuando el target no existe. Catalogo enfocado no sube system_mute. Shortcuts de Steam se ejecutan antes del hint_no_tools de inputs triviales.",
            measurement="Live safe-live qwen3:8b: #6 63.8s, #7 61.2s, #8 97.2s, #13 guard correcto pero FAIL de contrato porque despacho tool.",
            provenance=_prov(
                "legacy/Carter_v2/REAL_RUNTIME_LIVE_REPRO_REPORT.md",
                "2026-05-02",
                "qwen3:8b Ollama",
                ["43-75"],
            ),
            limitations="Un harness de 13 casos. Dry-run daba 13/13 y se revoco el RC.",
            validity="mecanismo_reutilizable",
            current_piece="Baxy.Providers.Windows GUI/UIA; no despachar click ciego si no hay ventana",
            source_files=[
                "legacy/Carter_v2/REAL_RUNTIME_LIVE_REPRO_REPORT.md",
                "legacy/Carter_v2/RESIDUAL_BACKLOG_AFTER_BLOCK.md",
                "legacy/Carter_v2/RESIDUAL_BACKLOG_V2.md",
            ],
            repeats=["REAL_RUNTIME_FAILURE_AUDIT 2.5; ULTRA_LATENCY GUI 131s"],
        ),
        _card(
            card_id="dry-run-no-es-live",
            claim_kind="documental",
            problem="Gates pytest+dry-run cerraban RC; el live LLM los desmintio.",
            outcome="fracaso",
            solution_or_failure="Repro live 3/13 PASS (luego taxonomia 2/13 successful + 1 honest_degraded). Dry-run 13/13 y scripted 654/654 no cuentan como evidencia de modelo.",
            causal_mechanism="Dry-run es router estructural. Scripted usa modelo 'scripted'. Soak 200 turnos = 0.9 ms, caminos Python sincronos, no LLM.",
            measurement="Live 3/13 (qwen3:8b); pytest 481 passed; dry-run 13/13; scripted 654/654; soak 200 turns, leak 142732 B, SOAK_PASSED.",
            provenance=_prov(
                "legacy/Carter_v2/REAL_RUNTIME_LIVE_REPRO_REPORT.md",
                "2026-05-02",
                "qwen3:8b",
                ["38-41", "87-99"],
            ),
            limitations="Numeros de mayo 2026. BAXY ya exige evidencia contemporanea (invariante 2).",
            validity="mecanismo_reutilizable",
            current_piece="escalera de validacion AGENTS.md: Full no se sustituye por scaffold; Goal 10 uso diario",
            source_files=[
                "legacy/Carter_v2/REAL_RUNTIME_LIVE_REPRO_REPORT.md",
                "legacy/Carter_v2/FULL_LIVE_LLM_TEST_AUDIT.md",
                "legacy/Carter_v2/audit/results/FULL_LIVE_LLM_VALIDATION_SUMMARY.md",
                "legacy/Carter_v2/audit/results/SKIPPED_LIVE_VALIDATION_SUMMARY.md",
                "legacy/Carter_v2/TEXT_CORE_SOAK_TEST_REPORT.md",
                "legacy/Carter_v2/TEXT_CORE_PERFORMANCE_FINAL.md",
            ],
            repeats=["PERFORMANCE_FINAL admite que no re-midio LLM para el RC"],
        ),
        _card(
            card_id="contexto-inyectado-sin-gate",
            claim_kind="documental",
            problem="Carter no fallaba por el LLM: fallaba por lo que el codigo le daba. 'a' hablaba de mission.py; 140-154 s de barras; user_ref 'Como'.",
            outcome="exito",
            solution_or_failure="L1-L8: resolve_user_ref con confianza/conflicto; no inyectar active-app ni prior-turns en input trivial; detector estructural de ruido; clamp 20s; style_preference solo si confirmed.",
            causal_mechanism="active_app_line en CADA turno; facts sin confidence/scope; timeout 180s; filtro de ruido solo streaming ≥12 chars; retry require_tool=True en followup.",
            measurement="Probe 13/13 en qwen3:8b post-fix (documental). pytest 420/420 en el reporte L1-L8. Landing: caso 'a' 23317→10509 ms; 'a' post-GUI 32500→3195 ms. Sigue >8s en frio.",
            provenance=_prov(
                "legacy/Carter_v2/LLM_CONTEXT_MEMORY_AUDIT.md",
                "2026-05-01",
                "qwen3:8b",
            ),
            limitations="Fixes de v2; no auditados en codigo BAXY. Landing numbers son de qwen2.5:7b en otro audit.",
            validity="mecanismo_reutilizable",
            current_piece="mente/prompt y memoria: no inyectar ventana activa ni hechos no confirmados en turnos triviales",
            source_files=[
                "legacy/Carter_v2/LLM_CONTEXT_MEMORY_AUDIT.md",
                "legacy/Carter_v2/LLM_CONTEXT_MEMORY_REPORT.md",
                "legacy/Carter_v2/LLM_AUTONOMY_BOUNDARY.md",
                "legacy/Carter_v2/PRE_LLM_LATENCY_REPORT.md",
                "legacy/Carter_v2/audit/results/CARTER_TEXT_BLOCK_LANDING_AUDIT.md",
                "legacy/Carter_v2/audit/results/CARTER_TEXT_BLOCK_LANDING_V2_AUDIT.md",
            ],
            repeats=["ULTRA_LATENCY C1.01 70s timeout; FAILURE_AUDIT 2.1 78.4s"],
        ),
        _card(
            card_id="taxonomia-pass-honesta-y-rebaseline",
            claim_kind="documental",
            problem="Round 3 publico 10/13 incluyendo un false pass en 'quien soy yo?' y mezclando exito, degradacion honesta y fail.",
            outcome="exito",
            solution_or_failure="Taxonomia pass_successful / pass_honest_degraded / fail. Round 4: 2/13 successful, 1 honest, 10 fail. qwen3:8b NOT_SUITABLE_AS_CURRENT_DEFAULT. qwen2.5:7b-instruct mejor (best 6/1/6 semantico; Jarvis budget 4/1/8).",
            causal_mechanism="Detector de '?' demasiado amplio marcaba respuestas con pregunta de cortesia como needs_user. Harness congelado; el delta es solo de modelo.",
            measurement="qwen3:8b 3 warm runs ~2/1/10. qwen2.5:7b run07 6/1/6. Jarvis budgets: chat 5s, tool 8s — casi todos miss en qwen3.",
            provenance=_prov(
                "legacy/Carter_v2/audit/results/CARTER_GLOBAL_RUNTIME_AUDIT.md",
                "2026-05-02",
                "qwen3:8b",
            ),
            limitations="13 casos, no 540. qwen2.5:7b no es el modelo de BAXY. DEFAULT_SWITCH y STABILITY son la misma familia de auditorias.",
            validity="mecanismo_reutilizable",
            current_piece="scorer 03C: no mezclar success, honest-degraded y fail; no celebrar taxonomia laxa",
            source_files=[
                "legacy/Carter_v2/audit/results/CARTER_GLOBAL_RUNTIME_AUDIT.md",
                "legacy/Carter_v2/audit/results/CARTER_MODEL_REBASELINE_AUDIT.md",
                "legacy/Carter_v2/audit/results/CARTER_RUNTIME_STABILITY_AUDIT.md",
                "legacy/Carter_v2/audit/results/CARTER_DEFAULT_SWITCH_AUDIT.md",
            ],
            repeats=["REAL_RUNTIME_LIVE_REPRO 3/13 es oleada previa a la taxonomia"],
        ),
        _card(
            card_id="ultra-latency-stretch-miss",
            claim_kind="documental",
            problem="Contrato funcional READY 7/7 pero no cumple stretch Jarvis. Outliers 32-131 s.",
            outcome="fracaso",
            solution_or_failure="Plan L1-L12 (UIA budget, terminal timeout por comando, precheck filesystem, tunar Ollama, traces por etapa). Performance RC congela presupuestos de clasificador local (greet <5 ms) que no son latencia LLM.",
            causal_mechanism="UIA sin time-budget; terminal timeout 60s uniforme; start de archivo inexistente espera; backend timeout 180s / num_ctx 16384 fijo; 'hola' 70s por timeout de 3 intentos.",
            measurement="live_safe_postopt2: 654 casos, 452 pass / 3 fail / 199 skip. C12.13 131374 ms; C10.17 91742 ms; C1.01 70054 ms. pytest 436/436 en ese audit.",
            provenance=_prov(
                "legacy/Carter_v2/ULTRA_LATENCY_AUDIT.md",
                "2026-05-02",
                "qwen3:8b",
            ),
            limitations="Stretch targets de v2. Goal 01 midio 6.3-11.4 s de prosa E2B contemporanea — otro stack.",
            validity="historica",
            current_piece="Goal 08 primera senal y presupuesto de latencia de voz; no copiar budgets <5ms de clasificador como si fueran LLM",
            source_files=["legacy/Carter_v2/ULTRA_LATENCY_AUDIT.md"],
            repeats=["PRE_LLM 3-4s hasta primer spike GPU; TEXT_CORE_PERFORMANCE_FINAL §1"],
        ),
        _card(
            card_id="voz-vision-andamiaje-no-torneo",
            claim_kind="documental",
            problem="STT/TTS/voz no se pudieron tornear end-to-end: no habia tools de microfono ni speaker. Vision '1.00' es smoke de PNG de color, no UI.",
            outcome="inconcluso",
            solution_or_failure="Scaffolds: faster-whisper RTF ~0.24 CPU (tiny, 2s tone); Piper no en PATH; XTTS en venv. Vision: moondream 2127 MiB 1.00 smoke; qwen2.5vl:7b 13175 MiB grounding. Voz: NOT_EXECUTED_FULL_ENV_LIMITATION.",
            causal_mechanism="Sin record_audio/speak en tool_catalog no hay WER/MOS de Carter. Vision smoke no tiene screenshots ni bbox.",
            measurement="faster-whisper load 398 ms, transcribe 480 ms, RTF ~0.24. llava:7b 0.80 (fallo OCR espanol). Piper: binario ausente.",
            provenance=_prov(
                "legacy/Carter_v2/MODEL_STT_TOURNAMENT_REPORT.md",
                "2026-05-02",
                "faster-whisper CPU (sin cuBLAS 12)",
            ),
            limitations="Goal 01 re-midio Parakeet TDT 0.6b v3 int8 RTF 0.065-0.087 y wake baxy.onnx. Estos scaffolds de mayo no son el stack vigente.",
            validity="historica",
            current_piece="Goal 09 voz/oido; no heredar Piper/XTTS como decision; Parakeet ya medido",
            source_files=[
                "legacy/Carter_v2/MODEL_STT_TOURNAMENT_REPORT.md",
                "legacy/Carter_v2/MODEL_TTS_TOURNAMENT_REPORT.md",
                "legacy/Carter_v2/MODEL_VISION_TOURNAMENT_REPORT.md",
                "legacy/Carter_v2/MODEL_VOICE_TOURNAMENT_REPORT.md",
                "legacy/Carter_v2/VOICE_MODEL_RESEARCH.md",
                "legacy/Carter_v2/VOICE_CAMERA_HANDOFF_PLAN.md",
            ],
            repeats=["AUTO_MODEL_STACK_FINAL_REPORT §4-6"],
        ),
        _card(
            card_id="f0-prompt-hardcodes-rechazado",
            claim_kind="documental",
            problem="El prompt historico F0 enruta por keywords y nombres de app: IP→network_get_ip, Steam/Discord/Spotify como desktop, ACTIVE APP → gui_do.",
            outcome="fracaso",
            solution_or_failure="v2 documenta LLM_AUTONOMY_BOUNDARY: cero vocabulary lists, cero if Steam, cero regex de intencion. F0 queda como baseline de lo que no se hereda.",
            causal_mechanism="Reglas lexicales en el system prompt. Identidad BAXY y invariante 5 prohiben respuestas/ruteo fijos.",
            measurement="Plantilla 17794 bytes / 143 lineas. No es un bench.",
            provenance=_prov(
                "legacy/Carter_v2/audit/baselines/historical/F0_prompt_template.txt",
                "historico pre-2026-05-02",
                "n/a",
                ["1-40"],
            ),
            limitations="Baseline de auditoria, no runtime actual de Carter v2 RC (el RC afirma hardcode_count 0).",
            validity="caducada",
            current_piece="invariante 5 (cero respuestas visibles fijas) y catalogo tipado: la mente propone, el kernel autoriza",
            source_files=["legacy/Carter_v2/audit/baselines/historical/F0_prompt_template.txt"],
            repeats=["LLM_AUTONOMY_BOUNDARY 'must NEVER move into the code'"],
        ),
        _card(
            card_id="invariantes-rc-y-dieta",
            claim_kind="documental",
            problem="El proyecto crecia por acumulacion (probes, 1667 tests legacy, markdowns en raiz) mientras el RC afirmaba 16 invariantes.",
            outcome="contexto",
            solution_or_failure="Diet: archivar probes y suite legacy; src/carter_v2 'bien dimensionado'. Invariantes: no fake success, no hardcode de modelo, greet sin LLM, soak 200, pytest 481, voz fuera del text core.",
            causal_mechanism="Gates JSON del RC (hardcode 0, fake_success 0, 24/25 protocol). pytest historico f8: 1454 passed; post-lab M13: 435 passed; RC: 481. Los conteos no son comparables sin el filtro -k not live.",
            measurement="f8: 1454 passed in 114.81s. M13: 435 passed. RC: 481. Soak leak 142732 B < 5 MB.",
            provenance=_prov(
                "legacy/Carter_v2/TEXT_CORE_INVARIANTS.md",
                "2026-05-02",
                "qwen3:8b (default RC)",
            ),
            limitations="Invariantes de Carter v2 text-core. pytest counts son de distintos cortes. No son tests de BAXY Definitivo.",
            validity="historica",
            current_piece="ley 2 (retirar la capa que sustituyes) y ley 5 (una responsabilidad); tests/Baxy.*.Tests",
            source_files=[
                "legacy/Carter_v2/TEXT_CORE_INVARIANTS.md",
                "legacy/Carter_v2/TEXT_CORE_ARCHITECTURE.md",
                "legacy/Carter_v2/TEXT_CORE_CLEANUP_PLAN.md",
                "legacy/Carter_v2/CARTER_TEXT_CORE_RC_AUDIT.md",
                "legacy/Carter_v2/CARTER_TEXT_CORE_RELEASE_NOTES.md",
                "legacy/Carter_v2/CODEBASE_DIET_PLAN.md",
                "legacy/Carter_v2/REPO_CLEANUP_AUDIT.md",
                "legacy/Carter_v2/README.md",
                "legacy/Carter_v2/audit/logs/historical/f8_test_summary.txt",
                "legacy/Carter_v2/audit/results/post_model_lab_gates_20260502-092159.txt",
            ],
            repeats=["TEXT_CORE_PERFORMANCE_FINAL"],
        ),
    ]


def build() -> dict:
    batches_path, queue_ledger_path, _ = queue_paths(REPO)
    batch = next(
        item
        for item in load_json(batches_path)
        if item["batch_id"] == "docs-001-carter"
    )
    queue_ledger = load_json(queue_ledger_path)
    claimed = next(
        item
        for item in queue_ledger["batches"]
        if item["batch_id"] == "docs-001-carter"
    )
    card_list = cards()
    covered: set[str] = set()
    for card in card_list:
        covered.update(card["source_files"])
    files = []
    for row in batch["files"]:
        path = row["path"]
        if path not in RANGES:
            raise RuntimeError(f"missing ranges {path}")
        if path not in covered:
            raise RuntimeError(f"uncovered {path}")
        files.append(
            {
                "path": path,
                "sha256": row["sha256"],
                "source_id": row["source_id"],
                "terminal": "leido",
                "ranges": RANGES[path],
                "biblioteca_same_hash": path.startswith(
                    "docs/investigaciones/La razon de carter/"
                )
                or path
                in {
                    "docs/investigaciones/evidencia pruebas gemma4/GEMMA4_VALIDACION_COMPLETA.md",
                    "docs/investigaciones/evidencia pruebas gemma4/README.md",
                    "docs/investigaciones/evidencia pruebas gemma4/REPORTE.md",
                },
            }
        )
    nxt = next(
        item
        for item in queue_ledger["batches"]
        if item.get("kind") == "docs"
        and item["batch_id"] != "docs-001-carter"
        and item.get("status") == "pending"
    )
    return {
        "schema": SCHEMA,
        "batch_id": "docs-001-carter",
        "kind": "docs",
        "status": "complete",
        "claimed_utc": claimed.get("claimed_utc", "2026-08-30T20:05:00Z"),
        "closed_utc": "2026-08-30T21:30:00Z",
        "estimated_tokens": batch["estimated_tokens"],
        "token_limit": batch.get("token_limit", TOKEN_LIMIT),
        "token_target": batch.get("token_target", TOKEN_TARGET),
        "source_id": "carter",
        "source_head": HEAD,
        "source_root": ROOT,
        "file_count": batch["file_count"],
        "files": files,
        "cards": card_list,
        "missing": 0,
        "overlaps": 0,
        "biblioteca_same_hash_count": 15,
        "biblioteca_delta_count": 57,
        "notes": (
            "Afirmaciones de benches/transcripts son documentales. "
            "Reproducido en esta sesion: HEAD Carter OS AI, hashes SHA-256 de 72/72, "
            "15/72 identicos a biblioteca/carter. Cero archivos fuera del lote."
        ),
        "next_docs_batch_id": nxt["batch_id"],
        "next_prompt": "documentacion/sprints/09.5.2_LEER_DOCUMENTACION_LOTE.md",
    }


def main() -> int:
    ledger = build()
    dump_json(REPO / "artifacts" / "goal095" / "ledger" / "docs-001-carter.json", ledger)
    print(ledger["batch_id"], len(ledger["files"]), "files", len(ledger["cards"]), "cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
