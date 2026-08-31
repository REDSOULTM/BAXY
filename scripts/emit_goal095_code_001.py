"""Emit the condensed code_tests-001-carter ledger. Data-only; no product code."""

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
)
HEAD = "9cf62d236cdef08012897d3c8c680b8afef0d62e"
HW = "RTX 4060 Ti 16 GB · Windows · Carter OS AI snapshot 09.5.0"
ROOT = "Programacion/Carter OS AI"
BATCH_ID = "code_tests-001-carter"

HARNESS = "docs/investigaciones/evidencia pruebas gemma4/harness"
CODE = "docs/investigaciones/investigacionnecesaria_v1/codigo_carter"
INV = "docs/investigaciones/investigacionnecesaria_v1"
V2 = "legacy/Carter_v2"

FILE_META: dict[str, dict] = {
    f"{HARNESS}/audio_full.py": {"terminal": "leido", "ranges": ["1-112"]},
    f"{HARNESS}/audio_probes.py": {"terminal": "leido", "ranges": ["1-100"]},
    f"{HARNESS}/bench_all.ps1": {"terminal": "leido", "ranges": ["1-98"]},
    f"{HARNESS}/judge.py": {
        "terminal": "leido",
        "ranges": ["1-80", "76-150", "158-252", "255-297"],
    },
    f"{HARNESS}/probe_ollama_audio.py": {"terminal": "leido", "ranges": ["1-97"]},
    f"{HARNESS}/run_baseline_qwen.py": {"terminal": "leido", "ranges": ["1-131"]},
    f"{HARNESS}/run_bench.py": {"terminal": "leido", "ranges": ["1-121"]},
    f"{HARNESS}/run_bench_extended.py": {"terminal": "leido", "ranges": ["1-125"]},
    f"{HARNESS}/tests.py": {"terminal": "leido", "ranges": ["1-79"]},
    f"{HARNESS}/tests_extended.py": {"terminal": "leido", "ranges": ["1-192"]},
    f"{HARNESS}/tools.py": {"terminal": "leido", "ranges": ["1-115"]},
    f"{HARNESS}/tools_extended.py": {"terminal": "leido", "ranges": ["1-187"]},
    "docs/investigaciones/evidencia pruebas gemma4/samples/generate_audio.ps1": {
        "terminal": "leido",
        "ranges": ["1-29"],
    },
    f"{INV}/02_full_matrix_runner.py": {
        "terminal": "leido",
        "ranges": ["1-80", "209-318", "363-441", "582-655", "767-930"],
    },
    f"{CODE}/03_models_gemma4.py": {
        "terminal": "leido",
        "ranges": ["1-92", "95-181", "188-274"],
    },
    f"{CODE}/04_agent.py": {"terminal": "leido", "ranges": ["1-120", "430-510"]},
    f"{CODE}/05_tool_retrieval.py": {"terminal": "leido", "ranges": ["1-185"]},
    f"{CODE}/06_adapter_llamacpp.py": {"terminal": "leido", "ranges": ["1-80"]},
    f"{CODE}/07_verifier_orchestrator.py": {"terminal": "leido", "ranges": ["1-80"]},
    f"{CODE}/08_reply_checks.py": {"terminal": "leido", "ranges": ["1-80"]},
    f"{CODE}/09_tools_init.py": {"terminal": "leido", "ranges": ["1-117"]},
    f"{V2}/.env.example": {"terminal": "leido", "ranges": ["1-80", "84-158"]},
    f"{V2}/.matrix_LIVE_SAFE_memory.db": {
        "terminal": "parseado_completo",
        "ranges": ["sqlite:schema+counts"],
        "parse_note": "11 tables; facts=6; conversation_turns=0; FTS vacio",
    },
    f"{V2}/.matrix_LIVE_SAFE_skills.db": {
        "terminal": "parseado_completo",
        "ranges": ["sqlite:schema+counts"],
        "parse_note": "skills=0",
    },
    f"{V2}/.matrix_LIVE_SAFE_skills.db-shm": {
        "terminal": "excluido_razonado",
        "ranges": ["sidecar"],
        "exclusion_rule": "sqlite_runtime_shm",
    },
    f"{V2}/.matrix_LIVE_SAFE_skills.db-wal": {
        "terminal": "parseado_completo",
        "ranges": ["sqlite:applied-with-parent-db"],
        "parse_note": "WAL aplicado al abrir skills.db en copia temporal",
    },
    f"{V2}/.matrix_live_safe_postopt2_memory.db": {
        "terminal": "parseado_completo",
        "ranges": ["sqlite:schema+counts"],
        "parse_note": "mismo esquema; facts=6; turns=0",
    },
    f"{V2}/.matrix_live_safe_postopt_memory.db": {
        "terminal": "parseado_completo",
        "ranges": ["sqlite:schema+counts"],
        "parse_note": "mismo esquema; facts=6; turns=0; hash disco=cola, distinto de git HEAD",
    },
    f"{V2}/.matrix_live_safe_postopt_skills.db-shm": {
        "terminal": "excluido_razonado",
        "ranges": ["sidecar"],
        "exclusion_rule": "sqlite_runtime_shm",
    },
    f"{V2}/.matrix_live_safe_postopt_skills.db-wal": {
        "terminal": "binario_inventariado",
        "ranges": ["sqlite-wal"],
        "binary_format": "sqlite-wal",
        "parse_note": "el .db padre no esta en este lote",
    },
    f"{V2}/.matrix_live_safe_ultra_final_memory.db": {
        "terminal": "parseado_completo",
        "ranges": ["sqlite:schema+counts"],
        "parse_note": "mismo esquema; facts=6; turns=0",
    },
    f"{V2}/.matrix_live_safe_ultra_final_skills.db-shm": {
        "terminal": "excluido_razonado",
        "ranges": ["sidecar"],
        "exclusion_rule": "sqlite_runtime_shm",
    },
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
    return [
        {
            "card_id": "harness-openai-tools-stubs",
            "disposition": "evidence_only",
            "component": "Banco Gemma4 OpenAI-tools con stubs deterministas (10+60 tests)",
            "contract": "Entrada: prompt + SYSTEM_PROMPT + TOOL_SCHEMAS. Salida: JSON de turnos con tool_calls y texto. execute_tool devuelve cadenas fijas (hora 2026-05-09T14:32:11, list_apps de 6 exe, titulo YouTube - Google Chrome). judge_one(tid) PASS/FAIL por if/elif sobre el id del test.",
            "dependencies": "llama-server :8080 o Ollama :11434; tools.py + tools_extended.py; tests.py + tests_extended.py. No toca el SO.",
            "historical_test": "Los 10 tests de tests.py y 60 de tests_extended.py SON el contrato. Resultados citados en docs-001 (9/10 y 55-57/60). No reejecutado aqui.",
            "limitations": "El juez K3/N2/HEAVY-2 exige que type_text contenga 'youtube' o 'chrome' porque eso es el stub, no una ventana real. steam_search es tool por app. C09-04 y C18-10 duplican el mismo prompt. temperature=0.7 en el runner vs T=1.0 del modulo Gemma4.",
            "current_owner": "tests/test_catalog_* y scorer Goals 03/04; no ProductCatalog",
            "source_files": [
                f"{HARNESS}/tools.py",
                f"{HARNESS}/tools_extended.py",
                f"{HARNESS}/tests.py",
                f"{HARNESS}/tests_extended.py",
                f"{HARNESS}/run_bench.py",
                f"{HARNESS}/run_bench_extended.py",
                f"{HARNESS}/run_baseline_qwen.py",
                f"{HARNESS}/judge.py",
                f"{HARNESS}/bench_all.ps1",
            ],
            "failure_mechanism": "Mide al modelo contra un catalogo inventado de 9+ extras, no contra providers. Un PASS no prueba efecto en Windows. Capas: este harness y el matrix 540 contra el agente vivo son dos bancos incompatibles.",
            "readme_vs_real": "El codigo existe y escribe results/*.json. Lo que promete 'honesty by construction' es un if por tid acoplado al stub. bench_all.ps1 mata llama-server y asume un arbol Probando Gemma 4 distinto de este snapshot.",
            "invariant_risk": "Transplantar schemas OpenAI o steam_search romperia el catalogo tipado. Frases fijas del SYSTEM_PROMPT ('You are Carter') rompen invariante 5 y el nombre BAXY.",
            "duplicate_layers": "Harness stubs vs matrix 540 live vs catalogo Kernel actual. Tres caminos de 'test de tools'.",
            "provisional": True,
            "provenance": _prov(
                f"{HARNESS}/judge.py",
                ["51-150", "158-252"],
                date="2026-05-09",
                model="torneo Gemma 4 E2B/E4B/26B/31B",
            ),
        },
        {
            "card_id": "harness-gemma-native-audio",
            "disposition": "reject_candidate",
            "component": "Probes de audio nativo Gemma 4 (Ollama input_audio vs llama-mtmd-cli)",
            "contract": "Entrada: 5 WAV 16 kHz. Dos prompts (transcribir / que tool). Salida: JSON con texto y latencia. audio_probes documenta llama.cpp#21868: llama-server no rutea input_audio. generate_audio.ps1 sintetiza con System.Speech, no voz humana.",
            "dependencies": "Ollama gemma4:e4b o llama-mtmd-cli + mmproj; samples WAV (fuera de este lote).",
            "historical_test": "Cinco clips (hora, negation, multistep, phonetic stim, codeswitch). Este lote no contiene los WAV ni results/audio_E4B.json.",
            "limitations": "Audio sintetico. Dos binarios distintos de mtmd-cli hardcodeados. Goal 01 ya midio Parakeet STT en CPU y rechazo Gemma nativo como oido de producto.",
            "current_owner": "src/baxy_mind/asr_fusion.py; scripts/setup_mind_voice.ps1",
            "source_files": [
                f"{HARNESS}/audio_full.py",
                f"{HARNESS}/audio_probes.py",
                f"{HARNESS}/probe_ollama_audio.py",
                "docs/investigaciones/evidencia pruebas gemma4/samples/generate_audio.ps1",
            ],
            "failure_mechanism": "El runner HTTP de Gemma no transporta audio; el workaround recarga el modelo por clip (frio). Tres caminos (Ollama, mtmd-cli, server) se apilan en vez de sustituirse.",
            "readme_vs_real": "El probe demuestra que las APIs de audio no estan listas; no demuestra STT de producto. La voz 'Sabina' no es el usuario.",
            "invariant_risk": "Ninguno si no se hereda. Un STT nativo Gemma pondria el oido en el LLM y duplicaria Parakeet.",
            "duplicate_layers": "Gemma audio nativo vs Whisper vs Parakeet (este ultimo es el activo Goal 01).",
            "provisional": True,
            "provenance": _prov(
                f"{HARNESS}/audio_probes.py",
                ["1-32", "34-54"],
                date="2026-05-09",
                model="gemma-4-E4B + mmproj",
            ),
        },
        {
            "card_id": "carter-v4-gemma4-core-prompt",
            "disposition": "reject_candidate",
            "component": "CORE_PROMPT Gemma 4 (~900 tokens) con saludos fijos y few-shots por app",
            "contract": "System prompt hibrido EN reglas / ES few-shots. Identidad 'soy Carter'. Saludo fijo. Few-shots Steam/Spotify/MercadoLibre/YouTube. Fallback vision+click si falta tool. Tablas de error enlatadas.",
            "dependencies": "carter_v4.models.gemma4; agent.from_gemma; llama-server --jinja.",
            "historical_test": "Ningun test unitario en este lote. El bench 55/60 es del harness de stubs, no de este prompt en el agente.",
            "limitations": "Copia de investigacion (prefijo 03_), no el modulo vivo de Carter_v4. Canonical vendra en lotes code_tests de carter_legacy_Carter_v4.",
            "current_owner": "src/baxy_mind/ (prosa por modelo); nunca App/FieldUi",
            "source_files": [f"{CODE}/03_models_gemma4.py"],
            "failure_mechanism": "Respuestas fijas y diccionario por app. La cadena 'si no hay tool, screenshot+vision+click' elude el catalogo cerrado. Regla 9 responde 'que necesitas?' sin pasar por el modelo de producto BAXY.",
            "readme_vs_real": "El modulo existe y documenta T=1.0 / flash-attn / KV f16 (eso va a otra tarjeta). El prompt contradice Identidad (nombre, invariante 5, sin per-app).",
            "invariant_risk": "Rompe prosa por modelo, catalogo tipado y modularidad si se pega encima del system prompt actual.",
            "duplicate_layers": "SYSTEM_PROMPT del harness (ingles, 9 reglas) vs CORE_PROMPT (~12 reglas + few-shots) vs prompt.py de v4.",
            "provisional": True,
            "provenance": _prov(
                f"{CODE}/03_models_gemma4.py",
                ["95-181"],
                date="2026-05-09",
                model="gemma-4-E4B-it-UD-IQ2_M",
            ),
        },
        {
            "card_id": "carter-v4-gemma4-sampling-flags",
            "disposition": "adapt_candidate",
            "component": "Sampling Google T=1.0 y flags llama-server (flash-attn, KV f16, no-context-shift)",
            "contract": "LLAMACPP_DEFAULTS temperature=1.0 top_p=0.95 top_k=64 repeat_penalty=1.0 num_predict=768. Flags: --jinja -ngl 99 -c 16384 --flash-attn on --cache-type-k/v f16 --no-context-shift --reasoning off. Perfiles trivial/tool/mission/destructive_strict.",
            "dependencies": "llama.cpp CUDA b9090 (historico); carter_v4.turn_profile.detect_destructive_intent (import tardio).",
            "historical_test": "Citado como 'bench externo 55/60, multi-step p99 7.58s' — no esta en este lote. Goal 01 re-midio E2B QAT en el runtime BAXY: 6.3-11.4 s/turno.",
            "limitations": "E4B IQ2_M no es el default vigente (Goal 01 eligio E2B y lo marco 'funciona y no sirve' por thinking). Flags de imagen 280-1120 tokens son vision, no texto. Perfil destructive usa T=0.6 contra la propia advertencia de no bajar T.",
            "current_owner": "src/baxy_mind/llm_transport.py y runtime llama-server del mind",
            "source_files": [f"{CODE}/03_models_gemma4.py", f"{CODE}/06_adapter_llamacpp.py"],
            "failure_mechanism": "El runner del harness manda temperature=0.7; el modulo Gemma manda 1.0. Dos calibraciones en el mismo linaje. Adapter HTTP OpenAI-compat ya existe en BAXY; no apilar otro.",
            "readme_vs_real": "Los flags estan en codigo. El 55/60 es del banco de stubs. El adapter no parsea special tokens: delega en --jinja.",
            "invariant_risk": "Adaptar flags no rompe invariantes si no se trae el CORE_PROMPT. No abrir un segundo transporte HTTP.",
            "duplicate_layers": "Ollama adapter + LlamaCppAdapter + llm_transport actual.",
            "provisional": True,
            "provenance": _prov(
                f"{CODE}/03_models_gemma4.py",
                ["31-82"],
                date="2026-05-09",
                model="gemma-4-E4B-it-UD-IQ2_M",
            ),
        },
        {
            "card_id": "carter-v4-agent-loop",
            "disposition": "reject_candidate",
            "component": "Agent loop ReAct v4 (911 lineas vs objetivo 400)",
            "contract": "Entrada user_text. Un LLM call, safety gate, dispatch, verify, loop detector, follow-up, possible _chain_more_tools, nudge anti-rendicion. Config: planner OFF (-3.52 pts), skill registry OFF, tool retrieval ON k=12, turn_budget 25s, max_history 10.",
            "dependencies": "pick_adapter, Memory sqlite, SkillStore, tools.dispatch, verify, verifier_orchestrator, safety.evaluate_tool_call, ToolRetriever.",
            "historical_test": "Ningun test_*.py en este lote. El matrix 540 importa este Agent. Esta copia de investigacion puede diferir del Carter_v4 vivo.",
            "limitations": "Snapshot numerado 04_agent.py bajo docs/investigaciones, no en src/. Git HEAD no lo tiene (untracked). Identidad SHA-256 de 09.5.1.",
            "current_owner": "src/baxy_mind/ + src/Baxy.Kernel/Mission/MissionEngine.cs",
            "source_files": [f"{CODE}/04_agent.py"],
            "failure_mechanism": "Acumulacion: flags que apagan capas en vez de retirarlas. El LLM elige tools; el kernel BAXY autoriza. Confirmacion pending_action no esta ligada a invocacion exacta del catalogo tipado.",
            "readme_vs_real": "El header promete <400 LoC y 0 classifiers. El archivo tiene 911 lineas y engancha planner, skills, retrieval, reflection, loop v2.",
            "invariant_risk": "Copiar el loop entero duplicaria mente+kernel y romperia catalogo, confirmacion exacta y modularidad.",
            "duplicate_layers": "Tres adapters, planner muerto, skill registry muerto, retrieval vivo — mismas ocho capas del autodiagnostico v5.",
            "provisional": True,
            "provenance": _prov(
                f"{CODE}/04_agent.py",
                ["1-12", "56-82", "430-510"],
                date="2026-05",
                model="qwen3:4b default; from_gemma E4B",
            ),
        },
        {
            "card_id": "carter-v4-openai-tool-registry",
            "disposition": "reject_candidate",
            "component": "Registro @tool y dispatch por nombre (catalogo OpenAI al LLM)",
            "contract": "Decorator registra handler+JSONSchema. get_catalog() emite tools=[]. dispatch(name, args) filtra kwargs por signature e invoca. Autoload de 16 modulos de tools.",
            "dependencies": "system, apps, files, memory_tool, web, gui, media, terminal, office, clipboard, registry, gui_universal, deeplink, skill, vision_tools.",
            "historical_test": "clear_registry() 'solo para tests'; los tests no estan en este lote.",
            "limitations": "Filosofia 'el LLM decide, cero classifiers' es el inverso del invariante 1 de BAXY.",
            "current_owner": "src/Baxy.Kernel/Operations/ProductCatalog.cs",
            "source_files": [f"{CODE}/09_tools_init.py"],
            "failure_mechanism": "El universo de operaciones vive en el prompt del modelo. No hay autorizacion kernel. Autoload de 16 paquetes es acumulacion.",
            "readme_vs_real": "El dispatch es un dict lookup de verdad. El catalogo no es el ProductCatalog tipado.",
            "invariant_risk": "Rompe catalogo tipado si se expone como tools OpenAI del mind.",
            "duplicate_layers": "Catalogo OpenAI v4 vs stubs del harness vs ProductCatalog .NET.",
            "provisional": True,
            "provenance": _prov(
                f"{CODE}/09_tools_init.py",
                ["1-9", "63-100", "112-117"],
                date="2026-05",
                model="n/a (registro)",
            ),
        },
        {
            "card_id": "carter-v4-tool-retrieval-e5",
            "disposition": "reject_candidate",
            "component": "Retriever top-K multilingual-e5-small + anchors (57 tools)",
            "contract": "Boot: embed descriptions. Turn: embed query, cosine, top-K=8 (docstring) / 12 (AgentConfig). Union con 23 anchors (memory, skill, gui, vision, web, terminal, app_open/close). Fallback: catalogo entero si el embedder falla.",
            "dependencies": "sentence-transformers + intfloat/multilingual-e5-small; mismo encoder que Memory.",
            "historical_test": "Ninguno en el lote. RAG-MCP citado 13.62%->43.13% es paper, no medicion Carter.",
            "limitations": "Baxy ya rechazo R209 cross-encoder 16/77. El catalogo vigente son operaciones tipadas, no 57 tools OpenAI. Anchors ~23 de 57 anulan el recorte.",
            "current_owner": "src/baxy_mind/router.py, family_classifier.py, semantic_family_arbiter.py",
            "source_files": [f"{CODE}/05_tool_retrieval.py"],
            "failure_mechanism": "Decision fatigue se 'arregla' recortando el catalogo que el LLM ve, no separando mente/kernel. Fallback silencioso a todo el catalogo. Anchors incluyen vision y deeplink — el retriever no puede excluir el camino GUI.",
            "readme_vs_real": "El cosine en Python puro existe. No hay evidencia en este lote de +5-10 pts en Carter.",
            "invariant_risk": "Un retriever que oculta operaciones al kernel rompe el catalogo como unica fuente.",
            "duplicate_layers": "Tool RAG vs family classifier vs aliases vs R209 rechazado.",
            "provisional": True,
            "provenance": _prov(
                f"{CODE}/05_tool_retrieval.py",
                ["1-18", "33-64", "134-176"],
                date="2026-05",
                model="multilingual-e5-small",
            ),
        },
        {
            "card_id": "carter-v4-verifier-orchestrator",
            "disposition": "adapt_candidate",
            "component": "Outcomes de turno COMPLETED/PARTIAL/FAILED/UNVERIFIED + TOOL_OK_VERIFIER_INCONCLUSIVE + INTENT_NOT_FULFILLED",
            "contract": "Agrega VerifierOutcome de la cadena. Separa 'deeplink despachado' (inconclusive) de 'read-only legitimo'. Heuristica _intent_not_fulfilled por keywords. Evita FALSE_PASS C09 (30/30 nominal con ~11 falsos).",
            "dependencies": "verify.py (no en este lote), planner Plan opcional.",
            "historical_test": "Mecanismo documentado contra C09 del matrix 540. No hay asercion pytest aqui.",
            "limitations": "Scoring por keywords en espanol ('despachada', 'uri '). No sustituye postlectura de provider. BAXY Core ya verifica efecto.",
            "current_owner": "src/Baxy.Core/Operations/ + postlectura en src/Baxy.Providers.Windows/",
            "source_files": [f"{CODE}/07_verifier_orchestrator.py"],
            "failure_mechanism": "verify.py 'tool ok' era el falso exito. Este orchestrator anade estados pero sigue heuristico. No medimos Windows; leemos razones de texto.",
            "readme_vs_real": "Los estados extras existen en codigo. C09 FALSE_PASS es el hallazgo reusable. No copiar como capa paralela a Core.",
            "invariant_risk": "Adaptar el estado 'inconclusive' al outcome de Core no rompe invariantes. Apilar un segundo orchestrator si.",
            "duplicate_layers": "verify.py inline + orchestrator + honesty Goal 04 + Core handlers.",
            "provisional": True,
            "provenance": _prov(
                f"{CODE}/07_verifier_orchestrator.py",
                ["1-48", "63-76"],
                date="2026-05",
                model="n/a (estructural)",
            ),
        },
        {
            "card_id": "carter-v4-reply-checks",
            "disposition": "reject_candidate",
            "component": "Anti-echo / anti-generic / anti-unverified post-LLM",
            "contract": "Jaccard >0.7 = eco. GENERIC_REPLIES frozenset (ok, listo, done, accion ejecutada, ...). Regex de afirmaciones factuales sin read tool. Cero LLM. unknown si no decide.",
            "dependencies": "Se llama desde agent o bench. Snowball mencionado en el docstring; el fragmento leido usa regex y un frozenset de frases.",
            "historical_test": "Casos canonicos citados C15-29, C13-04, C14-26. Tests no en este lote.",
            "limitations": "GENERIC_REPLIES es tabla de respuestas fijas — exactamente lo que invariante 5 prohibe en producto. Jaccard de eco es estructural y reusable como idea, no como modulo extra.",
            "current_owner": "Goal 04 cerrado (honestidad); no anadir guard de prosa en App",
            "source_files": [f"{CODE}/08_reply_checks.py"],
            "failure_mechanism": "Post-filtros de texto para tapar un loop que ya mintio. Goal 04 exige cero frases fijas y cero exitos no verificados en el nucleo, no un regex despues.",
            "readme_vs_real": "El docstring promete 'cero hardcoded keywords por idioma'. GENERIC_REPLIES es una lista ES/EN de acuses.",
            "invariant_risk": "Si se activa en runtime, viola invariante 5. El eco Jaccard podria vivir solo en el scorer de tests.",
            "duplicate_layers": "reply_checks + SYSTEM_PROMPT reglas 1-2 + judge.py + matrix _is_canned_greeting.",
            "provisional": True,
            "provenance": _prov(
                f"{CODE}/08_reply_checks.py",
                ["1-31", "43-57"],
                date="2026-05",
                model="n/a (regex)",
            ),
        },
        {
            "card_id": "carter-v4-matrix-540",
            "disposition": "evidence_only",
            "component": "full_matrix_runner 18x30=540 contra el Agent vivo",
            "contract": "Parsea la guia markdown 18 categorias. Corre Agent. audit_case: latency budgets, reply vacio, fake denial, vocativo Carter, canned greeting, tool requerida, fake success. Fuerza CARTER_V4_BLOCK_SHUTDOWN=1.",
            "dependencies": "carter_v4.agent (arbol src/, no esta copia 04_). Guia Extras/Carter_v3_tests/...md (otro lote).",
            "historical_test": "540 casos oficiales. Este archivo es el runner, no los resultados JSON (van a evidence_assets).",
            "limitations": "Copia bajo investigacionnecesaria_v1; import path asume src/carter_v4. El propio auditor usa listas de saludos canned. No es el scorer congelado de BAXY 03C/04.",
            "current_owner": "tests/Baxy.Integration.Tests y artifacts/development/goal03*",
            "source_files": [f"{INV}/02_full_matrix_runner.py"],
            "failure_mechanism": "Banco live vs banco stub: el mismo linaje declara dos verdades. El runner puede ejecutar tools reales (por eso el hard-lock de shutdown).",
            "readme_vs_real": "El parser de 540 y los budgets existen. 'sin keyword hardcodes' queda desmentido por valid_short_replies y _is_canned_greeting.",
            "invariant_risk": "No ejecutar este runner contra el PC de trabajo. No sustituir el scorer 03C.",
            "duplicate_layers": "harness 60 vs matrix 540 vs corpus BAXY 124.",
            "provisional": True,
            "provenance": _prov(
                f"{INV}/02_full_matrix_runner.py",
                ["1-35", "582-635"],
                date="2026-05",
                model="Carter v4 Agent (qwen3 o Gemma)",
            ),
        },
        {
            "card_id": "carter-v2-runtime-env",
            "disposition": "reject_candidate",
            "component": "Carter v2 .env.example (backends ollama/llamacpp/openai + knobs GUI/policy)",
            "contract": "CARTER_BACKEND=ollama|llamacpp|openai. Compact tools, ctx margin, UIA min elements, auto-approve high/critical, POLICY_ALLOW_DANGEROUS, preload, model profile, TEXT/VISION/GROUNDING/STT/TTS.",
            "dependencies": "run_carter_gpu.ps1, config.py v2 (siguientes lotes).",
            "historical_test": "Ninguno. Es plantilla.",
            "limitations": "Default TEXT_MODEL qwen2.5:7b y llava:7b caducados por Goal 01. openai + API_KEY es cloud. AUTO_APPROVE contradice confirmacion exacta.",
            "current_owner": "src/Baxy.Setup/ y scripts de mind runtime",
            "source_files": [f"{V2}/.env.example"],
            "failure_mechanism": "Tres backends conviviendo (ollama, in-process llamacpp, OpenAI HTTP). Vision/grounding como modelos aparte. Flags de peligro para 'que el bench pase'.",
            "readme_vs_real": "El archivo es real y no trae secretos (API_KEY=ollama local). Los defaults no son el stack BAXY.",
            "invariant_risk": "openai backend rompe privacidad (invariante 6). auto-approve rompe confirmacion (invariante 4).",
            "duplicate_layers": "v2 env vs v4 AgentConfig vs mind-runtime-v1.json actual.",
            "provisional": True,
            "provenance": _prov(
                f"{V2}/.env.example",
                ["9-22", "70-80", "137-153"],
                date="2026-04",
                model="qwen2.5:7b-instruct (default escrito)",
            ),
        },
        {
            "card_id": "carter-v2-matrix-sqlite-state",
            "disposition": "evidence_only",
            "component": "SQLite memory/skills de corridas matrix LIVE_SAFE / postopt / ultra_final",
            "contract": "memory.db: conversation_turns(user_text, reply_text), entities, facts(entity,attribute,value,source), memory_candidates, memory_recalls, FTS5 turns_fts. skills.db: tabla skills vacia. Cuatro memory.db con facts=6 y turns=0. Sidecars shm/wal.",
            "dependencies": "memory.py v2 (lote posterior). Packer 09.5.1: suffix_of('') en dotfiles => .db no marcado binary y entro en code_tests.",
            "historical_test": "Estado residual de benches, no una suite. skills=0 implica que enable_skill_store no persistio recetas en estas corridas, o se uso otro path.",
            "limitations": "No se vuelcan valores de facts (posible PII de corrida). Tres memory.db coinciden con la cola en disco y no con git HEAD (worktree sucio; se audita el hash 09.5.1). postopt/ultra skills.db padre no esta en este lote.",
            "current_owner": "src/Baxy.Providers.Windows/Memory/LocalMemoryStore.cs (current.bin cifrado, no SQLite)",
            "source_files": [
                f"{V2}/.matrix_LIVE_SAFE_memory.db",
                f"{V2}/.matrix_LIVE_SAFE_skills.db",
                f"{V2}/.matrix_LIVE_SAFE_skills.db-wal",
                f"{V2}/.matrix_live_safe_postopt2_memory.db",
                f"{V2}/.matrix_live_safe_postopt_memory.db",
                f"{V2}/.matrix_live_safe_postopt_skills.db-wal",
                f"{V2}/.matrix_live_safe_ultra_final_memory.db",
            ],
            "failure_mechanism": "Memoria de producto mezclada con artefactos de bench (.matrix_*). WAL/SHM versionados. El clasificador de 09.5.1 no ve .db si el filename empieza por punto.",
            "readme_vs_real": "El esquema SQLite existe y esta casi vacio de turnos. BAXY ya sustituyo esto por un store binario con tope y redactado.",
            "invariant_risk": "No copiar blobs de memoria. No reabrir SQLite al lado de LocalMemoryStore.",
            "duplicate_layers": "v2 sqlite vs v4 data/carter_v4_memory.db vs LocalMemoryStore.",
            "provisional": True,
            "provenance": _prov(
                f"{V2}/.matrix_LIVE_SAFE_memory.db",
                ["sqlite:schema+counts"],
                date="2026-04",
                model="n/a (estado)",
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
        "claimed_utc": "2026-08-31T00:40:00Z",
        "closed_utc": "2026-08-31T01:20:00Z",
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
        "hash_check": "32/32 disco=cola 09.5.1; 0 en biblioteca por hash; docs/investigaciones untracked en git",
        "next_code_tests_batch_id": next_id,
        "next_prompt": (
            "documentacion/sprints/09.5.3_AUDITAR_CODIGO_LOTE.md"
            if next_id
            else "documentacion/sprints/09.5.4_AUDITAR_EVIDENCIA_LOTE.md"
        ),
    }
    out = REPO / batch["output"]
    dump_json(out, ledger)
    mark_queue_complete(REPO, BATCH_ID, next_id)
    print(out)
    print("cards", len(ledger["cards"]))
    print("next", next_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
