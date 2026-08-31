"""Emit the condensed code_tests-002 ledger. Data-only; no product code."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.goal095_code_ledger import (
    SCHEMA,
    TOKEN_LIMIT,
    TOKEN_TARGET,
    dump_json,
    load_json,
    mark_queue_complete,
    next_pending_code_tests,
    queue_paths,
    unit_next_prompt,
)

HEAD = "9cf62d236cdef08012897d3c8c680b8afef0d62e"
HW = "RTX 4060 Ti 16 GB · Windows · Carter OS AI snapshot 09.5.0"
ROOT = "Programacion/Carter OS AI"
BATCH_ID = "code_tests-002-carter-carter_legacy_Carter_v2"
V2 = "legacy/Carter_v2"
AUDIT = f"{V2}/audit"
RES = f"{AUDIT}/results"
HIST = f"{AUDIT}/baselines/historical"


def _shm() -> dict:
    return {
        "terminal": "excluido_razonado",
        "ranges": ["sidecar"],
        "exclusion_rule": "sqlite_runtime_shm",
    }


def _wal() -> dict:
    return {
        "terminal": "binario_inventariado",
        "ranges": ["sqlite-wal"],
        "binary_format": "sqlite-wal",
        "parse_note": "padre .db no esta en este lote ni en disco",
    }


def _json_parse(note: str) -> dict:
    return {
        "terminal": "parseado_completo",
        "ranges": ["json:schema+aggregates+muestras"],
        "parse_note": note,
    }


FILE_META: dict[str, dict] = {
    f"{V2}/.matrix_live_safe_ultra_final_skills.db-wal": _wal(),
    f"{V2}/.matrix_skipped_all_web_live_skills.db-shm": _shm(),
    f"{V2}/.matrix_skipped_all_web_live_skills.db-wal": _wal(),
    f"{V2}/.matrix_skipped_web_live_skills.db-shm": _shm(),
    f"{V2}/.matrix_skipped_web_live_skills.db-wal": _wal(),
    f"{V2}/.matrix_web_full_skills.db-shm": _shm(),
    f"{V2}/.matrix_web_full_skills.db-wal": _wal(),
    f"{V2}/.matrix_web_rerun2_skills.db-shm": _shm(),
    f"{V2}/.matrix_web_rerun2_skills.db-wal": _wal(),
    f"{V2}/.matrix_web_rerun_skills.db-shm": _shm(),
    f"{V2}/.matrix_web_rerun_skills.db-wal": _wal(),
    f"{V2}/.matrix_web_smoke3_skills.db-shm": _shm(),
    f"{V2}/.matrix_web_smoke3_skills.db-wal": _wal(),
    f"{V2}/.matrix_web_v3_skills.db-shm": _shm(),
    f"{V2}/.matrix_web_v3_skills.db-wal": _wal(),
    f"{AUDIT}/COMPOUND_SMOKE.json": _json_parse("10 casos; passed=5 failed=5; version M8.2-M4-M7"),
    f"{AUDIT}/HARDCODE_GUARD.json": _json_parse("scanned_root src/carter_v2; 0 findings"),
    f"{HIST}/C-SMOKE_smoke.json": _json_parse("label F-SMOKE; qwen3:8b; prompts_n=18"),
    f"{HIST}/C-final_metrics.json": _json_parse("label C-SMOKE-final; branch radical/text-closure"),
    f"{HIST}/C0_baseline.json": _json_parse("label C0_baseline; head 8f67917"),
    f"{HIST}/F0_MEMORY.snapshot": {
        "terminal": "leido",
        "ranges": ["1-13"],
        "parse_note": "markdown sanitizado 2026-04-30; 2 facts user_stated; valores no copiados",
    },
    f"{HIST}/F0_baseline_tests.json": _json_parse("1481/1481 BASELINE_GREEN 162.48s"),
    f"{HIST}/F0_smoke.json": _json_parse("label F0; qwen3:8b; prompts_n=6"),
    f"{AUDIT}/baselines/pre_cleanup_snapshot.json": _json_parse(
        "pre_cleanup_20260501-020549"
    ),
    f"{AUDIT}/compound_smoke_runner.py": {
        "terminal": "leido",
        "ranges": ["1-40", "89-265", "284-330", "367-406"],
    },
    f"{AUDIT}/hardcode_guard.py": {
        "terminal": "leido",
        "ranges": ["1-80", "102-176", "186-220", "408-453"],
    },
    f"{RES}/ACTION_FAILED_ELIMINATION_FINAL_GATE.json": _json_parse(
        "ready_for_close=true; GREEN action_failed=0"
    ),
    f"{RES}/AUTO_MODEL_STACK_FINAL_GATE.json": _json_parse(
        "AUTO_MODEL_STACK_READY_WITH_ENV_LIMITATIONS; 18 gates"
    ),
    f"{RES}/CARTER_DEFAULT_SWITCH_GATE.json": _json_parse(
        "full_default_switch_completed=false; qwen3:8b -> ollama qwen2.5:7b-instruct"
    ),
    f"{RES}/CARTER_GLOBAL_RUNTIME_GATE.json": _json_parse(
        "PARTIAL_WITH_NEXT_STEP; round 4; pytest 481/481"
    ),
    f"{RES}/CARTER_MODEL_REBASELINE_GATE.json": _json_parse(
        "ADOPT_AS_NEW_DEFAULT_WITH_RESIDUAL_BACKLOG; qwen2.5:7b-instruct"
    ),
    f"{RES}/CARTER_RUNTIME_STABILITY_GATE.json": _json_parse(
        "qwen3:8b NOT_SUITABLE_AS_CURRENT_DEFAULT; 12/13 STABLE"
    ),
    f"{RES}/CARTER_TEXT_BLOCK_LANDING_GATE.json": _json_parse(
        "BLOCK_LANDED_LIVE_VERIFIED"
    ),
    f"{RES}/CARTER_TEXT_BLOCK_LANDING_V2_GATE.json": _json_parse(
        "JARVIS_BLOCK_PARTIAL; latency 8s y language directive 3/3"
    ),
    f"{RES}/CARTER_TEXT_CORE_RC_FINAL_GATE.json": _json_parse(
        "CARTER_TEXT_CORE_RELEASE_CANDIDATE; default qwen3:8b; hermes3:8b 16gb"
    ),
    f"{RES}/CARTER_TEXT_FINAL_CLOSURE_GATE.json": _json_parse(
        "GREEN CARTER_TEXT_FINAL_READY"
    ),
    f"{RES}/FULL_LIVE_LLM_FINAL_GATE.json": _json_parse(
        "overall_gate_pass=true; counters de fakes/hardcode/latency"
    ),
    f"{RES}/LLM_CONTEXT_MEMORY_PROBE.json": _json_parse(
        "scripted 13/13 failed=0"
    ),
    f"{RES}/LLM_CONTEXT_MEMORY_PROBE_REAL.json": _json_parse(
        "real qwen3:8b 13/13 failed=0"
    ),
    f"{RES}/MODEL_COMPATIBILITY_FINAL_GATE.json": _json_parse(
        "HARNESS_BIAS_CONFIRMED_AND_FIXED; OpenAI tools= favorece Qwen"
    ),
    f"{RES}/MODEL_LAB_FINAL_GATE.json": _json_parse(
        "MODEL_STACK_READY_WITH_LIMITATIONS"
    ),
    f"{RES}/MODEL_RECOMMENDATION.json": _json_parse(
        "selection text/stt/tts/vision + fallback_chains; 2026-05-02"
    ),
    f"{RES}/PERFORMANCE_AND_HARDCODE_FINAL_GATE.json": _json_parse(
        "READY; hardcode 0/0; needs_user=6 needs_environment=4 honest_fast=2"
    ),
}


def _prov(path: str, ranges: list[str], *, date: str, model: str) -> dict:
    return {
        "path": path,
        "ranges": ranges,
        "date": date,
        "hardware": HW,
        "model": model,
        "commit": HEAD,
    }


def cards() -> list[dict]:
    wal_files = [
        path
        for path, meta in FILE_META.items()
        if meta.get("terminal") == "binario_inventariado"
    ]
    return [
        {
            "card_id": "carter-v2-matrix-skills-sidecars",
            "disposition": "evidence_only",
            "component": "Sidecars SQLite WAL/SHM de corridas matrix web/live_safe sin padre .db",
            "contract": "7 shm de 32768 B (exclusiones sqlite_runtime_shm) y 8 WAL de 20632 B con magic SQLite-WAL. Padre .db no esta en el lote ni en disco. ultra_final WAL continua el shm ya cubierto en code_tests-001.",
            "dependencies": "skills.db de cada etiqueta matrix (siguientes lotes o ausente). memory.py v2.",
            "historical_test": "Estado residual de benches web/live_safe, no una suite. skills=0 en el padre LIVE_SAFE del lote 001.",
            "limitations": "No se abrio SQLite sobre WAL huerfano. Hash disco=cola 15/15. 001 ya inventario el shm de ultra_final.",
            "current_owner": "src/Baxy.Providers.Windows/Memory/LocalMemoryStore.cs",
            "source_files": wal_files,
            "failure_mechanism": "Artefactos de bench versionados como codigo. El clasificador 09.5.1 no marca .db-wal de dotfile como binary. WAL sin padre no es memoria de producto.",
            "readme_vs_real": "Los sidecars existen y coinciden con la cola. No hay tabla skills que leer aqui.",
            "invariant_risk": "No copiar blobs. No reabrir SQLite al lado de LocalMemoryStore.",
            "duplicate_layers": "v2 sqlite vs v4 memory.db vs LocalMemoryStore; mismo mecanismo que lote 001.",
            "provisional": True,
            "provenance": _prov(
                f"{V2}/.matrix_live_safe_ultra_final_skills.db-wal",
                ["sqlite-wal"],
                date="2026-04",
                model="n/a (sidecar)",
            ),
        },
        {
            "card_id": "carter-v2-compound-smoke",
            "disposition": "adapt_candidate",
            "component": "Smoke de misiones compuestas con backend scripted (M8.2-M4-M7)",
            "contract": "Entrada: 10 CompoundCase (user_text + AgentResponse scripted + expected_tools + expected_mission_status). Sale audit/COMPOUND_SMOKE.json. Valida la maquina de estados, no el SO. expected_mission_status acepta partial|complete cuando UIA falta. steam_open_client es tool por marca. Exit != 0 si falla un caso.",
            "dependencies": "carter_v2.turn.agent.AgentEngine, CapabilityRegistry, adapters.tools.ToolCall. No llama al LLM.",
            "historical_test": "COMPOUND_SMOKE.json: 5/10. Fallan open_then_close_notepad, open_steam_then_close, step_two_fails, gui_step_observed, uia_unavailable: mission_status=trivial y 0 pasos aunque tool_calls_made coincide. Pasan open_write_close_notepad, three_step_pipeline, triviales y open_opera_search_batman (trivial esperado).",
            "limitations": "El runner inyecta las tools; no mide si el modelo las elegiria. 'y' dejo de marcar compuesto (comentario en open_opera_search_batman). HEAD del JSON drita vs cola (se audita hash 09.5.1).",
            "current_owner": "src/Baxy.Kernel/Mission/MissionEngine.cs",
            "source_files": [
                f"{AUDIT}/compound_smoke_runner.py",
                f"{AUDIT}/COMPOUND_SMOKE.json",
            ],
            "failure_mechanism": "El detector de mision no dispara en 'abre X y luego cieralo': despacha tools y marca trivial. Quitar conectores multilingual (hardcode_guard) dejo el SM ciego. steam_open_client + Notepad/Steam/Opera en prompts son catalogo por app. Reply 'Listo. Notepad abierto y cerrado.' con status trivial es falso exito de prosa.",
            "readme_vs_real": "El docstring promete validar expected_steps/tools/status. La corrida demuestra que el SM no extrae pasos en 5/10 aunque el backend scripted cumple la secuencia.",
            "invariant_risk": "Adaptar casos compuestos al MissionEngine con operaciones tipadas no rompe invariantes. Traer steam_open_client o gui_do como tools del LLM si.",
            "duplicate_layers": "mission.py v2 vs MissionEngine; compound smoke vs matrix 540 vs scorer 03C.",
            "provisional": True,
            "provenance": _prov(
                f"{AUDIT}/compound_smoke_runner.py",
                ["1-40", "113-265"],
                date="2026-05",
                model="n/a (scripted)",
            ),
        },
        {
            "card_id": "carter-v2-hardcode-guard",
            "disposition": "adapt_candidate",
            "component": "Scanner regex anti-marca y anti-listas multilingual en src/carter_v2",
            "contract": "Falla si BRAND_RE (steam/spotify/discord/notepad/batman/...) o MULTILANG_LITERAL_RE (y luego/and then/que hora es/abre steam) aparecen fuera de BRAND_ALLOWED_FILES. VOCAB_CONTAINER_RE caza _TOKENS/_PHRASES. Lineas con H-XYZ-NN se perdonan. Exit 0 si critical=0.",
            "dependencies": "Solo lee .py bajo src/carter_v2. No ejecuta el agente.",
            "historical_test": "HARDCODE_GUARD.json: total_findings=0, critical=0. El propio compound_smoke usa Steam/Notepad/Opera y steam_open_client; vive en audit/ y no se escanea.",
            "limitations": "Allowlist de ~20 modulos de capabilities/interfaces. El scanner ES la lista de marcas. Whitelist por comentario de auditoria es un agujero. No cubre BAXY .NET.",
            "current_owner": "tests/ (compuerta estatica) + src/Baxy.Kernel/Operations/ProductCatalog.cs",
            "source_files": [
                f"{AUDIT}/hardcode_guard.py",
                f"{AUDIT}/HARDCODE_GUARD.json",
            ],
            "failure_mechanism": "El guard 'pasa' porque las marcas se movieron a capabilities/steam.py (allowlist) y el detector de mision perdio conectores. Cero findings no prueba ausencia de hardcode: prueba que el denylist y la allowlist coinciden.",
            "readme_vs_real": "0 findings es real sobre el arbol escaneado. El catalogo por app sigue en adapters/tools.py (allowlist explicita).",
            "invariant_risk": "Una guarda estructural en tests de BAXY (forma, no marcas) es adaptable. Copiar BRAND_RE al runtime viola invariante 5 y universalidad.",
            "duplicate_layers": "hardcode_guard vs reply_checks GENERIC_REPLIES vs judge.py vs ProductCatalog.",
            "provisional": True,
            "provenance": _prov(
                f"{AUDIT}/hardcode_guard.py",
                ["47-73", "102-126"],
                date="2026-05",
                model="n/a (regex)",
            ),
        },
        {
            "card_id": "carter-v2-historical-baselines",
            "disposition": "evidence_only",
            "component": "Baselines F0/C0/C-SMOKE y snapshot pre-cleanup (2026-04-30 a 2026-05-01)",
            "contract": "F0_baseline_tests: 1481 passed / 0 failed / BASELINE_GREEN. C-SMOKE y F0 smoke contra qwen3:8b (18 y 6 prompts). C0_baseline y C-final_metrics en branch radical/text-closure. F0_MEMORY.snapshot: markdown sanitizado (probe ids quitados). pre_cleanup_snapshot cuenta backups y git.",
            "dependencies": "pytest historico; ollama qwen3:8b. No se reejecuta.",
            "historical_test": "Los JSON SON el resultado. 1481/1481 es pytest, no el smoke LLM. C-SMOKE label interno 'F-SMOKE' (nombre de fichero vs label).",
            "limitations": "qwen3:8b caducado por Goal 01 y por gates posteriores de este mismo lote. El snapshot de memoria contiene facts de usuario; no se copian valores.",
            "current_owner": "tests/ (pytest) y artifacts/development/; no ProductCatalog",
            "source_files": [
                f"{HIST}/C-SMOKE_smoke.json",
                f"{HIST}/C-final_metrics.json",
                f"{HIST}/C0_baseline.json",
                f"{HIST}/F0_MEMORY.snapshot",
                f"{HIST}/F0_baseline_tests.json",
                f"{HIST}/F0_smoke.json",
                f"{AUDIT}/baselines/pre_cleanup_snapshot.json",
            ],
            "failure_mechanism": "Verde de pytest (1481) se cita como salud del producto mientras el smoke LLM es otro banco. Label C-SMOKE vs F-SMOKE en el mismo fichero.",
            "readme_vs_real": "Los agregados existen. No hay prueba en este lote de que C-SMOKE 18/18 pasara.",
            "invariant_risk": "No rehidratar facts del snapshot. No tomar 1481 pytest como gate de misiones.",
            "duplicate_layers": "pytest F0 vs compound smoke vs matrix 540 vs harness 60.",
            "provisional": True,
            "provenance": _prov(
                f"{HIST}/F0_baseline_tests.json",
                ["json:schema+aggregates+muestras"],
                date="2026-04-30",
                model="qwen3:8b (smoke); n/a (pytest)",
            ),
        },
        {
            "card_id": "carter-v2-inflated-closure-gates",
            "disposition": "evidence_only",
            "component": "Gates que declaran GREEN/READY de action_failed, text-final y live-LLM",
            "contract": "ACTION_FAILED: ready_for_close=true, controllable [action_failed]=0. TEXT_FINAL: GREEN CARTER_TEXT_FINAL_READY. FULL_LIVE_LLM: overall_gate_pass=true con counters (fake_success, hardcode_critical, unverified_completed, ...).",
            "dependencies": "Mismo runtime qwen3:8b / ollama. Gates posteriores del lote contradicen el cierre.",
            "historical_test": "Los tres JSON. No reejecutado. FULL_LIVE_LLM no expone totales de counters en el digest, solo claves.",
            "limitations": "Cierre 'final' el 2026-05 mientras GLOBAL_RUNTIME es PARTIAL y TEXT_BLOCK_V2 es JARVIS_BLOCK_PARTIAL. El score plano 10/13 de round 3 mezclaba successful + honest_degraded + false_pass.",
            "current_owner": "src/Baxy.Core/Operations/ (outcomes) + Goal 04 honestidad",
            "source_files": [
                f"{RES}/ACTION_FAILED_ELIMINATION_FINAL_GATE.json",
                f"{RES}/CARTER_TEXT_FINAL_CLOSURE_GATE.json",
                f"{RES}/FULL_LIVE_LLM_FINAL_GATE.json",
            ],
            "failure_mechanism": "Declarar GREEN cuando quedan agujeros medidos en el mismo directorio. action_failed se 'elimina' del scoreboard controlable; needs_user/needs_environment se aparcan. Texto [action_failed] tools=... en compound step_two_fails sigue siendo prosa de fallo, no outcome de Core.",
            "readme_vs_real": "Los veredictos GREEN estan en el JSON. El resto del lote prueba que no eran terminales.",
            "invariant_risk": "No importar 'action_failed' como string de reply. El outcome Failure de Core ya existe.",
            "duplicate_layers": "Z1-Z9 action_failed vs Core OperationOutcome.Failure vs reply_checks.",
            "provisional": True,
            "provenance": _prov(
                f"{RES}/ACTION_FAILED_ELIMINATION_FINAL_GATE.json",
                ["json:schema+aggregates+muestras"],
                date="2026-05",
                model="qwen3:8b",
            ),
        },
        {
            "card_id": "carter-v2-model-lab-gates",
            "disposition": "reject_candidate",
            "component": "Lab de modelos, rebase, switch incompleto y sesgo del harness OpenAI-tools",
            "contract": "MODEL_LAB: MODEL_STACK_READY_WITH_LIMITATIONS. MODEL_RECOMMENDATION: selection text/stt/tts/vision + fallback por perfil VRAM. COMPATIBILITY: HARNESS_BIAS_CONFIRMED_AND_FIXED (tools= OpenAI premia Qwen; CARTER_TOOL_PROTOCOL=auto). DEFAULT_SWITCH: ollama default qwen2.5:7b-instruct, llamacpp sigue qwen3-8b GGUF, full_default_switch_completed=false. REBASELINE: ADOPT qwen2.5 con backlog; 5 fallos qwen3 resueltos bajo qwen25.",
            "dependencies": "ollama + llama-server; audit/runners/real_runtime_transcript_repro.py (otro lote).",
            "historical_test": "Los seis JSON. pytest 481/481 citado en DEFAULT_SWITCH. 4 runs rebase (3 warm qwen25 + 1 cold).",
            "limitations": "Goal 01 midio Gemma E2B y rechazo FunctionGemma como conversador. Estos defaults qwen/hermes3/llama3.2/gpt-oss no son el stack BAXY. Switch 'default' quedo a medias entre dos backends.",
            "current_owner": "src/baxy_mind/llm_transport.py y mind-runtime-v1.json",
            "source_files": [
                f"{RES}/AUTO_MODEL_STACK_FINAL_GATE.json",
                f"{RES}/MODEL_LAB_FINAL_GATE.json",
                f"{RES}/MODEL_RECOMMENDATION.json",
                f"{RES}/MODEL_COMPATIBILITY_FINAL_GATE.json",
                f"{RES}/CARTER_DEFAULT_SWITCH_GATE.json",
                f"{RES}/CARTER_MODEL_REBASELINE_GATE.json",
            ],
            "failure_mechanism": "Dos runtimes con defaults distintos. El protocolo de tools se trata como palanca de modelo. md de auditoria con labels que no coincidian con el transcript (round 8). Recomendar modelo por 13 casos volatiles.",
            "readme_vs_real": "El sesgo OpenAI-tools esta medido. El switch completo no se hizo. Goal 01 ya sustituye estas recomendaciones.",
            "invariant_risk": "Reabrir un lab de modelos o un segundo protocolo tools= rompe catalogo tipado y modularidad. No cloud.",
            "duplicate_layers": "v2 model lab vs v4 Gemma E4B vs Goal 01 E2B vs FunctionGemma 270M.",
            "provisional": True,
            "provenance": _prov(
                f"{RES}/MODEL_COMPATIBILITY_FINAL_GATE.json",
                ["json:schema+aggregates+muestras"],
                date="2026-05-02",
                model="qwen3:8b vs qwen2.5:7b-instruct",
            ),
        },
        {
            "card_id": "carter-v2-runtime-stability-performance",
            "disposition": "evidence_only",
            "component": "Estabilidad live 13 casos, runtime global y gate de latencia/hardcode",
            "contract": "GLOBAL_RUNTIME: PARTIAL_WITH_NEXT_STEP; detector estructural de aclaracion (glifo ?/¿ tras oracion declarativa). STABILITY: qwen3 NOT_SUITABLE; case 12 oscila honest_degraded vs fail por latencia. PERFORMANCE: READY, p50/p95 por perfil, needs_user=6, needs_environment=4, honest_fast_failures=2, hardcode 0, 1 instancia LLM, backend_reused=true.",
            "dependencies": "real_runtime_transcript_repro.py; qwen3:8b y qwen2.5:7b-instruct en :11434.",
            "historical_test": "5 runs stability (1 cold + 4 warm). PERFORMANCE closure_conditions 7/7. No reejecutado.",
            "limitations": "Taxonomia pass_successful / pass_honest_degraded / fail. Round 3 aplanaba esas cubetas. Preload y concurrencia de tools quedan como NEEDS_ENVIRONMENT.",
            "current_owner": "src/Baxy.Core/ + tests de latencia/honestidad Goals 03-04",
            "source_files": [
                f"{RES}/CARTER_GLOBAL_RUNTIME_GATE.json",
                f"{RES}/CARTER_RUNTIME_STABILITY_GATE.json",
                f"{RES}/PERFORMANCE_AND_HARDCODE_FINAL_GATE.json",
            ],
            "failure_mechanism": "Latencia de primer call y volatilidad se tratan con preload/flags en vez de retirar capas. Detector de aclaracion por glifo es heuristica de prosa, no kernel. needs_user/environment sacan casos del denominador 'controlable'.",
            "readme_vs_real": "PARTIAL y NOT_SUITABLE son honestos. PERFORMANCE READY convive con 6+4+2 fallos aparcados.",
            "invariant_risk": "No portar el detector de '?' al mind. Core ya separa Failure de exito verificado.",
            "duplicate_layers": "clarification detector vs reply_checks vs Goal 04 vs MissionEngine.",
            "provisional": True,
            "provenance": _prov(
                f"{RES}/CARTER_RUNTIME_STABILITY_GATE.json",
                ["json:schema+aggregates+muestras"],
                date="2026-05-02",
                model="qwen3:8b / qwen2.5:7b-instruct",
            ),
        },
        {
            "card_id": "carter-v2-text-block-landing",
            "disposition": "evidence_only",
            "component": "Aterrizaje del bloque texto (v1 live-verified, v2 partial, RC text-only)",
            "contract": "v1: BLOCK_LANDED_LIVE_VERIFIED; reescribe closure_checklist con live_status. v2: JARVIS_BLOCK_PARTIAL — item 3 latencia <8s e item 4 language directive 3/3; item 1 action-route residual. RC: TEXT_MODE only; default qwen3:8b, recommended 16gb hermes3:8b, fast llama3.2:3b, quality gpt-oss:20b.",
            "dependencies": "Mismo harness live. Voice/camera/mic fuera de alcance del RC.",
            "historical_test": "Tres JSON. Residuals en RESIDUAL_BACKLOG_V2.md (docs, otro lote).",
            "limitations": "RC recomienda modelos que Goal 01 no eligio. Language directive estructural choca con invariante 5 si se congela prosa. v1 'live verified' no impide v2 partial.",
            "current_owner": "src/baxy_mind/ (prosa) + MissionEngine (rutas)",
            "source_files": [
                f"{RES}/CARTER_TEXT_BLOCK_LANDING_GATE.json",
                f"{RES}/CARTER_TEXT_BLOCK_LANDING_V2_GATE.json",
                f"{RES}/CARTER_TEXT_CORE_RC_FINAL_GATE.json",
            ],
            "failure_mechanism": "Cerrar un 'bloque' con evidencia live y reabrir el siguiente con residuals. Directivas de idioma y action-route como capas encima del loop. Presupuesto 8s es el techo Alexa, no una medida BAXY actual.",
            "readme_vs_real": "v2 admite partial. RC es text-only de verdad (voz fuera).",
            "invariant_risk": "No heredar hermes3/gpt-oss ni language directive. MissionEngine no debe ramificar por marca.",
            "duplicate_layers": "text block v1/v2/RC vs CORE_PROMPT v4 vs baxy_mind actual.",
            "provisional": True,
            "provenance": _prov(
                f"{RES}/CARTER_TEXT_BLOCK_LANDING_V2_GATE.json",
                ["json:schema+aggregates+muestras"],
                date="2026-05",
                model="qwen3:8b",
            ),
        },
        {
            "card_id": "carter-v2-llm-context-memory-probe",
            "disposition": "evidence_only",
            "component": "Probe de memoria en contexto LLM (13 casos scripted y real)",
            "contract": "Entrada: 13 casos. Salida: cases_failed/total. Scripted: model=scripted, 0 fallos. Real: qwen3:8b, 13/13, 0 fallos. Mide si el modelo retuvo hechos en el prompt, no LocalMemoryStore.",
            "dependencies": "LLM context window. Distinto de .matrix_* sqlite del lote 001.",
            "historical_test": "Los dos JSON (opus47 / opus47_real). No reejecutado.",
            "limitations": "13/13 scripted es tautologico si las respuestas van inyectadas. Real 13/13 no demuestra persistencia entre sesiones. Facts de usuario no se copian.",
            "current_owner": "src/Baxy.Providers.Windows/Memory/LocalMemoryStore.cs",
            "source_files": [
                f"{RES}/LLM_CONTEXT_MEMORY_PROBE.json",
                f"{RES}/LLM_CONTEXT_MEMORY_PROBE_REAL.json",
            ],
            "failure_mechanism": "Memoria como texto en el prompt vs store cifrado con tope. Un probe verde no sustituye recall verificado.",
            "readme_vs_real": "Los contadores 0 failed estan en el JSON. No hay esquema de persistencia en estos ficheros.",
            "invariant_risk": "No meter facts de corrida en el system prompt. Store actual ya redacta.",
            "duplicate_layers": "probe contexto vs sqlite v2 vs LocalMemoryStore vs F0_MEMORY.snapshot.",
            "provisional": True,
            "provenance": _prov(
                f"{RES}/LLM_CONTEXT_MEMORY_PROBE_REAL.json",
                ["json:schema+aggregates+muestras"],
                date="2026-05",
                model="qwen3:8b",
            ),
        },
    ]


def main() -> int:
    batches_path, ledger_path, _summary = queue_paths(REPO)
    batches = load_json(batches_path)
    batch = next(item for item in batches if item["batch_id"] == BATCH_ID)
    queue_ledger = load_json(ledger_path)
    nxt = next_pending_code_tests(queue_ledger, BATCH_ID)
    next_id = None if nxt is None else nxt["batch_id"]
    claim = load_json(REPO / "artifacts" / "goal095" / "claims" / f"{BATCH_ID}.json")
    files = []
    for row in batch["files"]:
        meta = FILE_META[row["path"]]
        entry = {
            "path": row["path"],
            "sha256": row["sha256"],
            "source_id": row["source_id"],
            "terminal": meta["terminal"],
            "ranges": meta["ranges"],
        }
        for key in ("exclusion_rule", "binary_format", "parse_note"):
            if key in meta:
                entry[key] = meta[key]
        files.append(entry)
    missing_meta = {row["path"] for row in batch["files"]} - set(FILE_META)
    if missing_meta:
        raise SystemExit(f"missing FILE_META: {sorted(missing_meta)}")
    extra_meta = set(FILE_META) - {row["path"] for row in batch["files"]}
    if extra_meta:
        raise SystemExit(f"extra FILE_META: {sorted(extra_meta)}")
    ledger = {
        "schema": SCHEMA,
        "batch_id": BATCH_ID,
        "kind": "code_tests",
        "status": "complete",
        "claimed_utc": claim["claimed_utc"],
        "closed_utc": "2026-08-31T02:40:00Z",
        "estimated_tokens": batch["estimated_tokens"],
        "token_limit": TOKEN_LIMIT,
        "token_target": TOKEN_TARGET,
        "source_id": "carter",
        "source_head": HEAD,
        "source_root": ROOT,
        "file_count": batch["file_count"],
        "subsystem": batch.get("subsystem"),
        "subsystems": batch.get("subsystems"),
        "files": files,
        "cards": cards(),
        "missing": 0,
        "overlaps": 0,
        "hash_check": "43/43 disco=cola; head_match=16 head_drift=27; se audita hash 09.5.1",
        "next_code_tests_batch_id": next_id,
        "next_prompt": unit_next_prompt(queue_ledger, next_id),
    }
    out = REPO / batch["output"]
    dump_json(out, ledger)
    mark_queue_complete(REPO, BATCH_ID, next_id)
    print(out)
    print("cards", len(ledger["cards"]))
    print("next", next_id)
    print("next_prompt", ledger["next_prompt"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
