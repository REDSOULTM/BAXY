"""Emit the shipped 09.5.9 matrix, card assignment and transplant campaign.

Decisions are declared here and written to JSON. Tests load the JSON, not this
module. Does not walk historical source trees or biblioteca bodies.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.goal095_0959_matrix import (
    ASSIGNMENT_REL,
    AUDIT_KINDS,
    CAMPAIGN_REL,
    LEDGER_REL,
    PROTECTED_REJECTS,
    REPO,
    SCHEMA,
    SYNTHESIS_0955,
    SYNTHESIS_0956,
    SYNTHESIS_0957,
    SYNTHESIS_0958,
    SYNTHESIS_REL,
    TRANSPLANT_PROMPT,
    TRANSPLANT_TERMINALS,
    campaign_counts,
    dump_json,
    index_synthesis_responsibility_ids,
    load_json,
    lots_from_matrix,
)

CLOSED_UTC = "2026-08-31T20:00:00Z"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def keep(
    rid: str,
    refs: list[str],
    *,
    conducta: str,
    pruebas: str,
    recursos: str,
    arquitectura: str,
    live_owner: str,
    owning_test: str,
    valor_10_11: str,
    order: int = 100,
) -> dict[str, Any]:
    return {
        "id": rid,
        "decision": "conservar_actual",
        "synthesis_refs": refs,
        "conducta": conducta,
        "pruebas": pruebas,
        "recursos": recursos,
        "arquitectura": arquitectura,
        "live_owner": live_owner,
        "owning_test": owning_test,
        "valor_10_11": valor_10_11,
        "order": order,
        "pieza_que_se_retira": "ninguna — lo vivo iguala o supera la herencia",
        "second_live_path": False,
    }


def reject(
    rid: str,
    refs: list[str],
    *,
    conducta: str,
    pruebas: str,
    recursos: str,
    arquitectura: str,
    mecanismo_de_fracaso: str,
    coste: str,
    invariante: str,
    live_owner: str = "n/a",
    owning_test: str = "n/a",
    valor_10_11: str = "protege 10–11 de repetir un mecanismo medido",
    order: int = 900,
    protected: bool = False,
) -> dict[str, Any]:
    row = {
        "id": rid,
        "decision": "rechazar",
        "synthesis_refs": refs,
        "conducta": conducta,
        "pruebas": pruebas,
        "recursos": recursos,
        "arquitectura": arquitectura,
        "mecanismo_de_fracaso": mecanismo_de_fracaso,
        "coste": coste,
        "invariante": invariante,
        "live_owner": live_owner,
        "owning_test": owning_test,
        "valor_10_11": valor_10_11,
        "order": order,
        "pieza_que_se_retira": "ninguna — no entra al árbol vivo",
        "second_live_path": False,
        "protected": protected,
    }
    return row


def responsibilities() -> list[dict[str, Any]]:
    qwen = "Qwen3-4B-Q4_K_M SHA 7485fe6f… / llama.cpp b9980 / corpus fresco 761c1bc3…"
    return [
        keep(
            "llm_decisor",
            ["09.5.5:llm_decisor", "09.5.5:qwen3-4b-q4_k_m"],
            conducta="Decisor vivo: 82/124 cruda, 56/124 e2e, 33/36 OOD, p90 idle 3,02 s. Gemma E2B pierde 63/124 y 3,59 s p90 en la misma población.",
            pruebas="Goal 03 fresco + MVP vs Qwen3.5-4B/Phi-4/Instruct-2507 en esta máquina. Umbral: no bajar 82/124 ni 33/36 ni empeorar p90 idle.",
            recursos="Pico ~3066/3072 MiB en techo 4 GiB. Gemma thinking 6,3–11,4 s/turno no es más ligero.",
            arquitectura="Catálogo tipado; mente propone, kernel autoriza. No nombres en pesos.",
            live_owner="src/baxy_mind/llm.py",
            owning_test="tests/test_registered_runtime_expectation_r281.py",
            valor_10_11="10.0/10.7 comprensión y prosa",
            order=10,
        ),
        keep(
            "cuantizacion",
            ["09.5.5:cuantizacion"],
            conducta="Q4_K_M del mismo Qwen. Q2 Gemma degenera prosa; no hay Q3 de Qwen en disco.",
            pruebas="Goal 01 A/B Q2 vs Q4 Gemma. No se hereda Q2. Recambio exige GGUF más ligero del mismo modelo + A/B prosa ES.",
            recursos="Q4_K_M cabe en 4 GiB. Q2 ahorra 0,43 GB y empeora prosa/latencia.",
            arquitectura="Cuantización atada al decisor vigente, no a Gemma.",
            live_owner="manifiesto baxy-mind-runtime-v1 (GGUF Qwen3-4B-Q4_K_M)",
            owning_test="tests/test_registered_runtime_expectation_r281.py",
            valor_10_11="10.2 techo VRAM",
            order=11,
        ),
        keep(
            "runtime_inferencia",
            ["09.5.5:runtime_inferencia", "09.5.5:llama-cpp-b9980"],
            conducta="llama.cpp b9980 CUDA 12.4 ngl=99 ctx=4096. --reasoning-budget 0 publica thinking EN.",
            pruebas="Goal 03 p50 2,18 s n=122 mismo GGUF. Recambio de runtime exige mismas cuatro columnas.",
            recursos="Sidecar loopback; no Ollama ni cloud.",
            arquitectura="llama-server subproceso Job Object (ADR-0005).",
            live_owner="src/baxy_mind/llm.py",
            owning_test="tests/test_registered_runtime_expectation_r281.py",
            valor_10_11="10.0 runtime",
            order=12,
        ),
        keep(
            "encoder_recuperador",
            ["09.5.5:encoder_recuperador", "09.5.5:e5-small"],
            conducta="e5-small passage:/query: rankea operaciones, no familias. Shortlist ≥103/124. Score no abstiene (sep. 0,026).",
            pruebas="674/675; LOO 37 peligrosos registrados. MiniLM 0,9521 es granularidad 31, no comparable.",
            recursos="CPU; carga ~11 s histórica ya reparada. EmbeddingGemma más pesado sin dato 169 ops.",
            arquitectura="Encoder de producción sin autoridad de ruteo.",
            live_owner="src/baxy_mind/retrieval.py",
            owning_test="tests/test_mind_router_oracles.py",
            valor_10_11="10.7/03 revalidación shortlist",
            order=13,
        ),
        keep(
            "puerta_abstencion",
            ["09.5.5:puerta_abstencion", "09.5.5:lexical-domain-gate"],
            conducta="Puerta léxica de dominio + Qwen. 33/36 OOD. No fail-closed por verbo extra en bluetooth/wifi.",
            pruebas="Cinco mecanismos OOD ya medidos; supervisado 0,58 AUC. FunctionGemma primer split 0/3 no es evidencia contra esta puerta.",
            recursos="Cero VRAM extra. KVA sería sexta capa.",
            arquitectura="No se apila cabeza KVA ni MiniLM hard-gate.",
            live_owner="src/baxy_mind/turn_policy.py",
            owning_test="tests/test_direct_abstain_classifier_r250.py",
            valor_10_11="10.7 abstención honesta",
            order=14,
        ),
        keep(
            "catalogo_tipado",
            ["09.5.5:forma_catalogo", "09.5.7:catalogos_67_31_16_158"],
            conducta="170 descriptores / 169 públicos / 158 alcanzables, sello dc0a7893…. 67/31/16/158 son linaje, no recorte vivo.",
            pruebas="ProductCatalogTests Length=170. Consolidar a 16 midió 75,93%→62,96% (matrix-540).",
            recursos="Catálogo = datos. FT de nombres o tool_schemas.py en el prompt cuestan reentrenar o inventar.",
            arquitectura="Invariante 1: mente propone, kernel autoriza, provider ejecuta.",
            live_owner="src/Baxy.Kernel/Catalog/",
            owning_test="tests/Baxy.Kernel.Tests/ProductCatalogTests.cs",
            valor_10_11="10.1 corpus / 11 contratos",
            order=15,
        ),
        keep(
            "verificador_identidad",
            ["09.5.5:verificador_identidad"],
            conducta="OPERATION_IDENTITY_PROMPT sobre el mismo Qwen, 24 tokens, p50 0,15 s. Conserva ≥46/48 correctas y rechaza ≥21/84.",
            pruebas="FunctionGemma selector 90 casos desarrollo ≠ corpus fresco 160. FG selector prohibido mientras cueza nombres.",
            recursos="Mismo GGUF; 24 tokens extra, no un segundo modelo.",
            arquitectura="Verifica la propuesta; no elige la operación.",
            live_owner="src/baxy_mind/identity_prompt.py",
            owning_test="tests/test_active_decision_path_r280.py",
            valor_10_11="10.7 no inventar operaciones",
            order=16,
        ),
        reject(
            "functiongemma-270m-ft",
            ["09.5.5:functiongemma-270m-ft", "09.5.5:q8-0-functiongemma"],
            conducta="No conversa (0/3 conocimiento, 0/4 smalltalk). Inventa set_volume/no_query_query. Holdout 88,3% es el catálogo FT, no 169 ops.",
            pruebas="Goal 01 esta máquina n=8/3/4; R-007 abstención primer split 0/3; 03B Tools-Reduce 19/124 y 30 nombres inventados.",
            recursos="278 MB Q8_0 cabe; el fallo no es VRAM. 13 GGUF iter no se heredan.",
            arquitectura="Catálogo cocido en pesos: cambiar una operación exige reentrenar.",
            mecanismo_de_fracaso="Nombres de tools en los pesos + no es hablante + abstención rota en el primer split.",
            coste="Reentrenar el catálogo por cada alta/baja; segundo modelo de habla.",
            invariante="invariante 1 (catálogo tipado) + 5 (no es prosa de producto)",
            live_owner="rechazado — no sustituye a Qwen3-4B",
            owning_test="tests/test_goal095_0955_synthesis.py",
            protected=True,
            order=1,
        ),
        reject(
            "gemma4-e2b-qat",
            ["09.5.5:gemma4-e2b-qat", "09.5.5:q4-k-xl-qat-gemma"],
            conducta="Goal 03: 63/124 cruda vs Qwen 82; e2e 49 vs 56; p90 3,59 s; thinking EN 200–400 tok. «Funciona y no sirve».",
            pruebas="Comparable en corpus 761c1bc3…. ADR 21-tool no sustituye Goal 03. --reasoning-budget 0 publica el borrador EN.",
            recursos="GGUF 2499 MiB; ADR 1540 MiB delta no es presupuesto MVP 45/45.",
            arquitectura="Thinking EN antes de cada respuesta; no persona BAXY sin system prompt largo.",
            mecanismo_de_fracaso="Thinking residual + peor comprensión equivalente + latencia.",
            coste="6,3–11,4 s/turno en Goal 01; 34 turnos >3 s vs 13 de Qwen.",
            invariante="ley 4 (más lento sin ganar) + invariante 5 si se corta reasoning",
            order=20,
        ),
        reject(
            "gemma4-e4b",
            ["09.5.5:gemma4-e4b"],
            conducta="Nunca corrió corpus fresco contra Qwen3-4B. Audio nativo ya rechazado. Blob pg4-gguf-models ausente.",
            pruebas="Cifras Carter/harness ≠ Goal 03. Hashes individuales not invented.",
            recursos="Ley 4: E4B sin medición VRAM en techo 4 GiB. IQ2_M citado.",
            arquitectura="Mismo thinking que E2B. No se inventa el GGUF para medir.",
            mecanismo_de_fracaso="Sin comparabilidad y sin blob; medir exigiría FALLO_DE_AMBIENTE del asset exacto.",
            coste="~E4B no cabe como recambio ligero; 17 GiB de models/ omitidos a propósito.",
            invariante="ley 4 + fuente dispersa (no inventar hash)",
            order=21,
        ),
        reject(
            "gemma4-26b",
            ["09.5.5:gemma4-26b"],
            conducta="Fuera de techo 4 GiB. Sin corrida Goal 03.",
            pruebas="No comparable. Blob ausente; hashes not invented.",
            recursos="26B viola ley 4 de entrada.",
            arquitectura="No es el decisor de producto.",
            mecanismo_de_fracaso="Tamaño / VRAM / ausencia de GGUF hasheado.",
            coste="No cabe en el presupuesto de producto.",
            invariante="ley 4",
            order=22,
        ),
        reject(
            "gemma4-31b",
            ["09.5.5:gemma4-31b"],
            conducta="Fuera de techo 4 GiB. Sin corrida Goal 03.",
            pruebas="No comparable. Blob ausente; hashes not invented.",
            recursos="31B viola ley 4 de entrada.",
            arquitectura="No es el decisor de producto.",
            mecanismo_de_fracaso="Tamaño / VRAM / ausencia de GGUF hasheado.",
            coste="No cabe en el presupuesto de producto.",
            invariante="ley 4",
            order=23,
        ),
        reject(
            "qwen3.5-4b",
            ["09.5.5:qwen3.5-4b"],
            conducta="ADR tools 84,8%; EN→ES 6/30. MVP esta máquina: 11 errores GPU, más VRAM/RAM/latencia que Qwen3-4B.",
            pruebas="ADR 362+30 ≠ corpus 160. Rechazado sin cambiar el manifest.",
            recursos="VRAM 3028 MiB vs Gemma 1540; peor que Qwen3-4B vigente en MVP.",
            arquitectura="Fallback documentado en ADR-0005, no un recambio.",
            mecanismo_de_fracaso="Idioma invertido + más VRAM sin ganar Goal 03.",
            coste="11 errores semánticos GPU / 12 CPU en MVP.",
            invariante="ley 4 + cobertura ES/EN/spanglish",
            order=24,
        ),
        reject(
            "qwen3.5-0.8b",
            ["09.5.5:qwen3.5-0.8b"],
            conducta="Pequeño; abstención hard-gate ADR. No Goal 03.",
            pruebas="No comparable al fresco 160.",
            recursos="Ligero, insuficiente como hablante/decisor.",
            arquitectura="No sustituye Qwen3-4B ni e5.",
            mecanismo_de_fracaso="Hard-gate de abstención / sin cuatro columnas.",
            coste="Un segundo LLM no retira el vigente.",
            invariante="ley 2 (no apilar) + 4",
            order=25,
        ),
        reject(
            "qwen3-4b-instruct-2507",
            ["09.5.5:qwen3-4b-instruct-2507"],
            conducta="Más rápido en lab; ABBA 178/180, arguments-06 GPU x2. No Goal 03 fresco.",
            pruebas="MVP 180 ≠ 160 fresco.",
            recursos="No medido como techo 4 GiB de producto Goal 03.",
            arquitectura="Misma familia, no evidencia nueva comparable que gane.",
            mecanismo_de_fracaso="Instrumento distinto; errores GPU duplicados en args.",
            coste="Corrida Goal 03 completa para reabrir — no autorizada aquí.",
            invariante="09.5.5: no torneo ahora",
            order=26,
        ),
        reject(
            "qwen3-8b",
            ["09.5.5:qwen3-8b"],
            conducta="Lab Carter; thinking 31 s; perfiles 6–24 GB.",
            pruebas="No Goal 03. Cifras 16 GB host ≠ techo producto.",
            recursos="Viola ley 4.",
            arquitectura="Switch a medias en Carter.",
            mecanismo_de_fracaso="VRAM y latencia de thinking.",
            coste="Perfiles 6–24 GB.",
            invariante="ley 4",
            order=27,
        ),
        reject(
            "qwen2.5-7b-instruct",
            ["09.5.5:qwen2.5-7b-instruct"],
            conducta="Default Ollama de Carter v2. No Goal 03 fresco.",
            pruebas="No comparable.",
            recursos="7B en Ollama; tres backends.",
            arquitectura="Atado a Ollama, rechazado aparte.",
            mecanismo_de_fracaso="Runtime Ollama + tamaño.",
            coste="Servicio Windows / cloud sesgo tools=.",
            invariante="invariante 6 + ley 4",
            order=28,
        ),
        reject(
            "hermes3-8b",
            ["09.5.5:hermes3-8b"],
            conducta="4857 MiB en perfil 16 GB. No era default justo.",
            pruebas="hermes3-fair-no-era-default. No Goal 03.",
            recursos="Fuera de 4 GiB.",
            arquitectura="Lab Carter, no producto.",
            mecanismo_de_fracaso="VRAM 4857 MiB.",
            coste="Perfil 16 GB.",
            invariante="ley 4",
            order=29,
        ),
        reject(
            "phi-4-mini",
            ["09.5.5:phi-4-mini"],
            conducta="ADR: no emite tools --jinja; MVP 3+4 fallos.",
            pruebas="No Goal 03.",
            recursos="VRAM holgada no compensa tools rotos.",
            arquitectura="Plantilla jinja incompatible con catálogo.",
            mecanismo_de_fracaso="No emite tool-calls válidos.",
            coste="Fallos MVP GPU/CPU.",
            invariante="invariante 1 (tools del catálogo)",
            order=30,
        ),
        reject(
            "lfm2.5-1.2b",
            ["09.5.5:lfm2.5-1.2b"],
            conducta="Pequeño; abstención hard-gate ADR. No Goal 03.",
            pruebas="No comparable.",
            recursos="Ligero e insuficiente.",
            arquitectura="No sustituye al decisor.",
            mecanismo_de_fracaso="Hard-gate / sin cuatro columnas.",
            coste="Capa extra.",
            invariante="ley 2",
            order=31,
        ),
        reject(
            "embeddinggemma-300m",
            ["09.5.5:embeddinggemma-300m"],
            conducta="21 peligrosos LOO; más pesado; sin dato 169 ops.",
            pruebas="ADR only, no shortlist 103/124 vivo.",
            recursos="Más pesado que e5-small.",
            arquitectura="No rankea el catálogo actual.",
            mecanismo_de_fracaso="Sin evidencia en catálogo 169.",
            coste="VRAM/RAM extra sin win.",
            invariante="ley 4",
            order=32,
        ),
        reject(
            "minilm-l12-tool2vec",
            ["09.5.5:minilm-l12-tool2vec"],
            conducta="0,9521 @31 tools, 2,1 ms. Granularidad familia. ADR MiniLM hard-gate.",
            pruebas="No comparable a e5 en 169 ops.",
            recursos="Barato y de granularidad incorrecta.",
            arquitectura="Tool2Vec no es el recuperador vivo.",
            mecanismo_de_fracaso="Rankea familias, no operaciones.",
            coste="Capa extra sobre e5.",
            invariante="ley 2 + catálogo de operaciones",
            order=33,
        ),
        reject(
            "qwen3-embedding-0.6b",
            ["09.5.5:qwen3-embedding-0.6b"],
            conducta="LOO 88,3%; hard-gate cobertura. No dato 169.",
            pruebas="No comparable al shortlist vivo.",
            recursos="Más pesado que e5.",
            arquitectura="No autoridad de ruteo.",
            mecanismo_de_fracaso="Hard-gate / sin evidencia equivalente.",
            coste="Segundo encoder.",
            invariante="ley 2",
            order=34,
        ),
        reject(
            "bge-m3",
            ["09.5.5:bge-m3"],
            conducta="Experimentos R186–R244. R209 16/77 rechazado.",
            pruebas="No es el encoder de producto. No Goal 03 shortlist.",
            recursos="Capa extra.",
            arquitectura="Cascade BGE no sustituye e5.",
            mecanismo_de_fracaso="Capa extra sin win de abstención.",
            coste="RAM/latencia de cascade.",
            invariante="ley 2",
            order=35,
        ),
        reject(
            "cross-encoder-reranker",
            ["09.5.5:cross-encoder-reranker"],
            conducta="R208–R244; no promovido como ruteo.",
            pruebas="No comparable a e5+puerta.",
            recursos="Segundo pase.",
            arquitectura="Reranker no autoriza operaciones.",
            mecanismo_de_fracaso="Capa extra; score no abstiene.",
            coste="Latencia de cross-encoder.",
            invariante="ley 2",
            order=36,
        ),
        reject(
            "ollama-runtime",
            ["09.5.5:ollama-runtime"],
            conducta="Carter: Ollama default + openai API_KEY + servicio Windows. Tres backends; sesgo tools=.",
            pruebas="carter-v2-runtime-env. Live es llama-server sidecar, no Ollama.",
            recursos="Servicio persistente vs Job Object kill-on-close.",
            arquitectura="Cloud/API_KEY viola dirección de red; servicio Windows no es el sidecar.",
            mecanismo_de_fracaso="Runtime no atestado + salida a cloud + AUTO_APPROVE en el mismo .env.",
            coste="Segundo servidor de inferencia; invariante 6.",
            invariante="invariante 6 (local) + ADR-0005",
            live_owner="rechazado — sidecar vivo en src/baxy_mind/llm.py",
            owning_test="tests/test_registered_runtime_expectation_r281.py",
            protected=True,
            order=2,
        ),
        reject(
            "agent-function-schema",
            ["09.5.5:agent-function-schema"],
            conducta="tool_schemas.py / listas OpenAI en el prompt. Tests «no inventar» del linaje Schema Agent.",
            pruebas="Rechazo 09.5.5: catálogo = datos tipados. Schema Agent se leyó desde blobs git, no HEAD.",
            recursos="Prompt hinchado; 10/16 s eran sobrecarga propia en PG4.",
            arquitectura="Universo en el prompt vs OperationRegistry.",
            mecanismo_de_fracaso="El LLM elige nombres que el kernel no tiene.",
            coste="Inventar tools; consolidar el prompt en vez del catálogo.",
            invariante="invariante 1",
            order=37,
        ),
        reject(
            "q2-quant-gemma",
            ["09.5.5:q2-quant-gemma"],
            conducta="−0,43 GB y degenera prosa; más lento. No es Qwen.",
            pruebas="Goal 01 A/B Q2 vs Q4 Gemma.",
            recursos="Ahorro que rompe habla.",
            arquitectura="Quant del modelo que Goal 03 perdió.",
            mecanismo_de_fracaso="Prosa degenerada / repetición / palabras inventadas.",
            coste="Latencia peor pese a menos pesos.",
            invariante="ley 4 se detiene donde deja de entender",
            order=38,
        ),
        reject(
            "kva-abstain-head",
            ["09.5.5:kva-abstain-head"],
            conducta="Respuesta al 0/3 de FG. Sexta capa. Probe pt/fr/de/it fuera de alcance.",
            pruebas="No se añade encima de la puerta léxica. 0,58 AUC del supervisado ya medido.",
            recursos="MiniLM + cabeza extra.",
            arquitectura="Capa sobre capa.",
            mecanismo_de_fracaso="Apilar abstención no retira la puerta viva.",
            coste="Sexta capa; idiomas fuera de ES/EN/spanglish.",
            invariante="ley 2 + alcance de idioma",
            order=39,
        ),
        reject(
            "qwen-vl",
            ["09.5.5:qwen-vl", "09.5.7:qwen_vl", "09.5.8:qwen_vl"],
            conducta="R-023: inventó juegos ambiguos; visual-diff podía dar falso éxito. No se silencia.",
            pruebas="REG-023 corpus ambiguo/negativo. Escalón vivo: WindowsVisibleVisionLocator (endpoint ausente; Steam no lo necesitó).",
            recursos="Segundo motor de visión + VRAM.",
            arquitectura="Visión de Click X es UIA→OCR WinRT→visión último, no Qwen-VL.",
            mecanismo_de_fracaso="Falso éxito visual + nombres inventados de juegos.",
            coste="Capa VL + riesgo de estados falsos.",
            invariante="invariante 2/3 (no afirmar sin verificar) + R-023",
            live_owner="src/Baxy.Providers.Windows (cascada visible; no Qwen-VL)",
            owning_test="tests/Baxy.Providers.Windows.Tests/VisibleClickCascadeTests.cs",
            protected=True,
            order=3,
        ),
        reject(
            "qwen-asr",
            ["09.5.5:qwen-asr", "09.5.6:qwen_asr"],
            conducta="Qwen3-ASR-0.6B int8: recall anclas 0,889, p95 5,61 s, 0 rescate único vs Nemotron. candidatePromoted=false.",
            pruebas="Arena n=12 WER 0,081; minds14 n=84. Goal 09: Parakeet es el oído.",
            recursos="+2,71 GiB RSS; otro runtime sherpa.",
            arquitectura="Competiría con Parakeet CPU; no se apila un segundo STT.",
            mecanismo_de_fracaso="Recall<0,99, p95>2 s, cero rescate único, RAM.",
            coste="Segundo runtime STT + 2,71 GiB.",
            invariante="ley 2/4; Goal 09 no se reabre",
            live_owner="src/baxy_mind/voice.py (Parakeet)",
            owning_test="tests/test_goal09_voice_launch.py",
            order=40,
        ),
        reject(
            "gemma-native-audio",
            ["09.5.6:gemma_native_audio"],
            conducta="llama-server no rutea input_audio (#21868); recarga por clip; ES rioplatense 2/5 en 5 WAV sintéticos.",
            pruebas="Harness audio_probes; WAV no en lote. Goal 01 midió Parakeet CPU como oído.",
            recursos="Recarga de modelo por clip (frío).",
            arquitectura="Tres caminos apilados (Ollama input_audio vs llama-mtmd-cli + mmproj).",
            mecanismo_de_fracaso="API no lista; no es oído de producto.",
            coste="Segundo pipeline audio nativo sobre Gemma E4B.",
            invariante="Goal 09 oído = Parakeet; no se silencia el rechazo",
            live_owner="src/baxy_mind/voice.py (Parakeet)",
            owning_test="tests/test_goal09_voice_launch.py",
            protected=True,
            order=4,
        ),
        keep(
            "wake_word",
            ["09.5.6:wake_word"],
            conducta="baxy.onnx SHA 9b1ae5db… umbral 0,5; holdout 12/12 FRR 0. Goal 01 0,916/0,225.",
            pruebas="Goal 09 holdout SAPI aislado. HyperSpotter FA 14–32/96 rechazado. Umbral 0,5 no se toca.",
            recursos="CPU RTF 0,026. FAR 2,50/h registrado en APLAZADOS, no promoción.",
            arquitectura="KWS en manifiesto sidecar; no nombres en pesos.",
            live_owner="src/baxy_mind/wakeword.py",
            owning_test="tests/test_measure_goal09_far.py",
            valor_10_11="10.11 audio / 10.2 presencia",
            order=50,
        ),
        keep(
            "falsos_disparos",
            ["09.5.6:falsos_disparos"],
            conducta="FAR 2,00 h TV, 5 disparos, 2,50/h, upper 5,26/h. calibration.approved false. Umbral locked.",
            pruebas="Goal 09 FAR Poisson. Listón 0,1/h abierto en APLAZADOS; no se reabre 09.",
            recursos="n/a — política de umbral, no VRAM.",
            arquitectura="Identidad exige escucha; VoiceListenCommand es el interruptor.",
            live_owner="src/baxy_mind/wakeword.py",
            owning_test="tests/test_measure_goal09_far.py",
            valor_10_11="10.2 presencia (no retocar 0,5)",
            order=51,
        ),
        keep(
            "ruido",
            ["09.5.6:ruido"],
            conducta="Launch 2/2 noise_did_not_wake. SNR STT no reejecutado; no swap.",
            pruebas="stt_noise_robustness + FAR series. No recambio de cabeza.",
            recursos="Mismo KWS/STT.",
            arquitectura="No segundo denoiser de producto.",
            live_owner="src/baxy_mind/voice.py",
            owning_test="tests/test_measure_goal09_voice.py",
            valor_10_11="10.11",
            order=52,
        ),
        keep(
            "vad",
            ["09.5.6:vad"],
            conducta="Silero ONNX CPU, EOU 700 ms, p50 0,21 s máx 0,31 s. Cumple.",
            pruebas="Goal 09 launch EOU. No segundo VAD.",
            recursos="CPU.",
            arquitectura="Ya en voice.py.",
            live_owner="src/baxy_mind/voice.py",
            owning_test="tests/test_measure_goal09_voice.py",
            valor_10_11="10.11 primera señal oído",
            order=53,
        ),
        keep(
            "stt",
            ["09.5.6:stt"],
            conducta="Parakeet TDT 0.6b v3 int8 SHA 5a70e086… holdout 3/3 p50 0,20 s. WER 0,044 vs Whisper 0,075.",
            pruebas="Goal 01 RTF 0,065–0,087. Whisper fallback eliminado. Qwen-ASR no promovido.",
            recursos="CPU; no toca 4 GiB del decisor.",
            arquitectura="Oído de producto único.",
            live_owner="src/baxy_mind/voice.py",
            owning_test="tests/test_measure_goal09_voice.py",
            valor_10_11="10.11",
            order=54,
        ),
        keep(
            "nombres_propios",
            ["09.5.6:nombres_propios"],
            conducta="Corrector ES 64%→81% ya en producto. BAXY/Spotify fallan; locución dudosa pregunta, no ejecuta. Hotwords 5/18 rechazadas.",
            pruebas="Goal 09 entidad. Hueco de nombre propio no es el motor STT.",
            recursos="Corrector léxico, no segundo ASR.",
            arquitectura="Dudo ≠ ejecuto.",
            live_owner="src/baxy_mind/voice.py",
            owning_test="tests/test_measure_goal09_voice.py",
            valor_10_11="10.11 (aplazado, no bloquea)",
            order=55,
        ),
        keep(
            "bilingue_spanglish",
            ["09.5.6:bilingue_spanglish"],
            conducta="Holdout 3/3 es/en/«abre notepad please». App names frágiles. 13 lenguas no crean trabajo.",
            pruebas="ServiceNow n=59 WER 0,094. english_app_names_in_spanish = spanglish.",
            recursos="Mismo Parakeet.",
            arquitectura="Alcance ES/EN/spanglish solamente.",
            live_owner="src/baxy_mind/voice.py",
            owning_test="tests/test_measure_goal09_voice.py",
            valor_10_11="10.7 / 10.11",
            order=56,
        ),
        keep(
            "tts",
            ["09.5.6:tts"],
            conducta="Piper es_MX-claude-high ONNX + eSpeak SHA 3ef40a71… first 0,02 s; cancel mid. SAPI/GPL piper.exe/Sherpa OfflineTts fuera.",
            pruebas="Goal 09 TTS. OfflineTts rechaza el ONNX sin sample_rate — se infiere con onnxruntime.",
            recursos="CPU. No bundle sherpa duplicado.",
            arquitectura="Voz de producto = Piper, no SAPI.",
            live_owner="src/baxy_mind/voice_output.py",
            owning_test="tests/test_measure_goal09_voice.py",
            valor_10_11="10.11",
            order=57,
        ),
        keep(
            "primera_senal_oido",
            ["09.5.6:primera_senal"],
            conducta="EOU p50 0,21 s; launch 0,13–0,20 s; TTS 0,02 s caliente. No es el p50 2,18 s del LLM.",
            pruebas="Goal 08/09 first-signal oído. FirstSignalTests cubre el camino Core.",
            recursos="Oído CPU vs inferencia GPU: denominadores distintos.",
            arquitectura="turn.signal antes de la decisión por modelo (Goal 08).",
            live_owner="src/baxy_mind/voice.py + Baxy.Kernel FirstSignal",
            owning_test="tests/Baxy.Kernel.Tests/FirstSignalTests.cs",
            valor_10_11="10.2 / 08",
            order=58,
        ),
        keep(
            "barge_in",
            ["09.5.6:barge_in"],
            conducta="cancel() a media frase. Launch 2/2 cancelled. Diseño PG4 500 ms no es 2º controlador.",
            pruebas="Goal 09 barge-in.",
            recursos="Mismo output pipeline.",
            arquitectura="Ya en voice_output.py.",
            live_owner="src/baxy_mind/voice_output.py",
            owning_test="tests/test_measure_goal09_voice.py",
            valor_10_11="10.11",
            order=59,
        ),
        keep(
            "audio_ducking",
            ["09.5.6:audio_ducking"],
            conducta="Restore-exact + AEC NLMS WASAPI en voice_aec.py. AEC=false si no hay loopback. Falta dB físico, no otro ducker.",
            pruebas="Goal 09 ducking. Hueco dB = APLAZADOS, no recambio.",
            recursos="WASAPI loopback opcional.",
            arquitectura="Un ducker, no dos.",
            live_owner="src/baxy_mind/voice_aec.py",
            owning_test="tests/test_measure_goal09_voice.py",
            valor_10_11="10.11",
            order=60,
        ),
        keep(
            "dispositivos_audio",
            ["09.5.6:dispositivos"],
            conducta="WASAPI honesto. Sidecar Python; launch 2/2. Carter NOT_EXECUTED no es works.",
            pruebas="Goal 09 dispositivos de esta máquina.",
            recursos="n/a.",
            arquitectura="Estados terminales honestos si falta mic.",
            live_owner="src/baxy_mind/voice.py",
            owning_test="tests/test_measure_goal09_voice.py",
            valor_10_11="10.2 preflight",
            order=61,
        ),
        keep(
            "modelos_assets_voz",
            ["09.5.6:modelos_assets"],
            conducta="Manifiesto SHA wake/STT/TTS vigentes. pg4 blobs: hashes not invented. Sustituir = fichero+SHA.",
            pruebas="R281 runtime expectation. Ningún candidato de trasplante exige el GGUF disperso.",
            recursos="Assets vivos fuera del git; sparse 17/39 GiB omitidos a propósito.",
            arquitectura="Sidecar manifiesto, no pesos en repo.",
            live_owner="scripts/mind_runtime_manifest.ps1",
            owning_test="tests/test_registered_runtime_expectation_r281.py",
            valor_10_11="10.0 / 10.11",
            order=62,
        ),
        keep(
            "voz_latencia",
            ["09.5.6:latencia"],
            conducta="Parakeet 71 ms / RTF 0,065–0,087; STT 0,20 s; EOU 0,21 s; wake 0,12 s. Qwen-ASR p95 5,6 s rechazado.",
            pruebas="Goal 09. No se compara con p50 LLM 2,18 s.",
            recursos="CPU oído vs GPU decisor.",
            arquitectura="Denominador propio (primera señal de oído).",
            live_owner="src/baxy_mind/voice.py",
            owning_test="tests/test_measure_goal09_voice.py",
            valor_10_11="10.2 / 10.11",
            order=63,
        ),
        keep(
            "voz_recursos",
            ["09.5.6:recursos"],
            conducta="Idle 60 s RSS 1088 MB, GPU 510/16380, llama-server off. Qwen-ASR +2,71 GiB RSS rechazado.",
            pruebas="Goal 09 idle_listen.json. No toca 4 GiB del decisor.",
            recursos="STT/TTS CPU.",
            arquitectura="Oído independiente del GGUF caliente.",
            live_owner="src/baxy_mind/voice.py",
            owning_test="tests/test_measure_goal09_voice.py",
            valor_10_11="10.2",
            order=64,
        ),
        keep(
            "presencia",
            ["09.5.6:presencia"],
            conducta="Always-on por identidad. BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED; VoiceListenCommand apaga. No promocionar FAR para «cerrar» presencia.",
            pruebas="Goal 09 costura explícita, no listón 0,1/h.",
            recursos="Idle oído ~1 GB RSS.",
            arquitectura="Escucha permanente ≠ umbral relajado.",
            live_owner="src/Baxy.App VoiceListenCommand + sidecar",
            owning_test="tests/test_measure_goal09_far.py",
            valor_10_11="10.2 presencia diaria",
            order=65,
        ),
        keep(
            "tools",
            ["09.5.7:tools"],
            conducta="ProductCatalog.ToolDescriptors → OperationRegistry. Mente propone, kernel autoriza, provider ejecuta.",
            pruebas="ProductCatalogTests + MissionEngineTests. carter-v4-openai-tool-registry reject.",
            recursos="Cero segundo registro @tool.",
            arquitectura="Invariante 1. Cambiar una operación es editar el catálogo.",
            live_owner="src/Baxy.Kernel/Catalog/ + MissionEngine",
            owning_test="tests/Baxy.Kernel.Tests/ProductCatalogTests.cs",
            valor_10_11="10.1 / 10.16",
            order=70,
        ),
        keep(
            "skills",
            ["09.5.7:skills"],
            conducta="skill_registry no opera. 16 SKILL.md cerradas al catálogo público.",
            pruebas="test_skill_registry.py. Una skill no sustituye al kernel.",
            recursos="Cero runtime extra.",
            arquitectura="Skill ≠ ejecutor.",
            live_owner="src/baxy_mind/skill_registry.py",
            owning_test="tests/test_skill_registry.py",
            valor_10_11="10.16 no es un segundo motor",
            order=71,
        ),
        reject(
            "microagentes",
            ["09.5.7:microagentes"],
            conducta="Ningún microagente vivo. Loader Carter/PG4 rechazado. MissionEngine basta.",
            pruebas="MissionEngineTests. Hueco: no hace falta un segundo ejecutor.",
            recursos="agent.py 1.397 líneas vs objetivo 400 — acumulación.",
            arquitectura="Un ejecutor (kernel+providers).",
            mecanismo_de_fracaso="Segundo ejecutor / loader de microagentes duplica el kernel.",
            coste="Routers en serie y 10/16 s de sobrecarga propia.",
            invariante="ley 2 + skill_does_not_replace_kernel",
            live_owner="src/Baxy.Kernel MissionEngine (único ejecutor)",
            owning_test="tests/Baxy.Kernel.Tests/MissionEngineTests.cs",
            order=72,
        ),
        keep(
            "uia_ocr_vision",
            ["09.5.7:uia_ocr_vision"],
            conducta="input.visible.click + ocr.read + vision.describe. UIA→OCR WinRT→visión último. Qwen-VL R-023 rechazado aparte.",
            pruebas="VisibleClickCascade. Steam Click X 2026-08-23. Tesseract spa falta: APLAZADOS; Click X no depende de Tesseract.",
            recursos="Visión de pantalla, no cámara.",
            arquitectura="Cascada genérica sin nombre de app.",
            live_owner="src/Baxy.Providers.Windows",
            owning_test="tests/Baxy.Providers.Windows.Tests/VisibleClickCascadeTests.cs",
            valor_10_11="10.10 apps/ventanas/visión",
            order=73,
        ),
        keep(
            "adapters_providers",
            ["09.5.7:adapters_providers"],
            conducta="Baxy.Providers.Windows vivo. No se apilan Steam/Spotify históricos. Retiro de adapters por app es Goal 10, no un segundo provider ahora.",
            pruebas="ExternalAdaptersTests. Goal 01: 2.454 líneas que sirven a 4 apps.",
            recursos="Providers actuales; no transplant de allowlists.",
            arquitectura="Cubrir el PC, no las apps.",
            live_owner="src/Baxy.Providers.Windows",
            owning_test="tests/Baxy.Providers.Windows.Tests/ExternalAdaptersTests.cs",
            valor_10_11="10.10 / 10.12 (no hereda allowlist)",
            order=74,
        ),
        keep(
            "planes",
            ["09.5.7:planes"],
            conducta="planner.py DAG de pasos de catálogo. Sin motor de workflows.",
            pruebas="test_compound_missions.py. FunctionGemma planner.py no standalone.",
            recursos="Mismo sidecar.",
            arquitectura="Plan = operaciones del catálogo, no workflows Carter.",
            live_owner="src/baxy_mind/planner.py",
            owning_test="tests/test_compound_missions.py",
            valor_10_11="10.16 misiones",
            order=75,
        ),
        keep(
            "confirmacion",
            ["09.5.7:confirmacion"],
            conducta="ConfirmationAuthority. Token ↛ otro invocationId.",
            pruebas="ConfirmationAuthorityTests. AUTO_APPROVE rechazado aparte.",
            recursos="Ida y vuelta de confirmación, no p50 LLM.",
            arquitectura="Invariante 4.",
            live_owner="src/Baxy.Kernel ConfirmationAuthority",
            owning_test="tests/Baxy.Kernel.Tests/ConfirmationAuthorityTests.cs",
            valor_10_11="10.17 identidad",
            order=76,
        ),
        keep(
            "verificacion",
            ["09.5.7:verificacion"],
            conducta="VerifierContractId. 82 observadas, 88 unverifiable con razón. Postcondición independiente.",
            pruebas="Goal05CatalogExecutionMatrixTests. fake-success / mute-sin-readback rechazados.",
            recursos="n/a.",
            arquitectura="Invariante 2/3. El recibo del ejecutor no es la postcondición.",
            live_owner="src/Baxy.Core + Kernel VerifierContractId",
            owning_test="tests/Baxy.Kernel.Tests/Goal05CatalogExecutionMatrixTests.cs",
            valor_10_11="10.0 / 11 verificación",
            order=77,
        ),
        keep(
            "steam_media",
            ["09.5.7:steam_media"],
            conducta="app.open + Click X; SMTC; game.*. Sesión Steam/SMTC hueco de Goal 10, no transplant.",
            pruebas="test_compound_missions.py; Click Steam 2026-08-23.",
            recursos="Cascada UIA/OCR, no SteamLocalAdapter histórico apilado.",
            arquitectura="PC genérico > allowlist Steam.",
            live_owner="src/Baxy.Providers.Windows",
            owning_test="tests/test_compound_missions.py",
            valor_10_11="10.12 / 10.16",
            order=78,
        ),
        keep(
            "archivos",
            ["09.5.7:archivos"],
            conducta="filesystem.* note.* backup.*. SHA/CAS; no creer a Create.",
            pruebas="CoreNotesEndToEndTests.",
            recursos="n/a.",
            arquitectura="Postcondición de fichero, no éxito de API.",
            live_owner="src/Baxy.Providers.Windows + Core notes",
            owning_test="tests/Baxy.Integration.Tests/CoreNotesEndToEndTests.cs",
            valor_10_11="10.14",
            order=79,
        ),
        keep(
            "apps",
            ["09.5.7:apps"],
            conducta="app.open/close window.*. Identidad de proceso, no título parecido.",
            pruebas="AppOpenHandlerTests.",
            recursos="n/a.",
            arquitectura="Providers Windows, no GUI ciega Carter.",
            live_owner="src/Baxy.Providers.Windows",
            owning_test="tests/Baxy.Providers.Windows.Tests/AppOpenHandlerTests.cs",
            valor_10_11="10.10",
            order=80,
        ),
        keep(
            "navegador",
            ["09.5.7:navegador"],
            conducta="browser.* web.search. Sin Playwright segundo. CDP hueco de Goal 10.",
            pruebas="ExternalCapabilityHandlerTests.",
            recursos="Inbound web; cero contenido de usuario outbound.",
            arquitectura="Invariante 6.",
            live_owner="src/Baxy.Providers.Windows",
            owning_test="tests/Baxy.Providers.Windows.Tests/ExternalCapabilityHandlerTests.cs",
            valor_10_11="10.9 / 10.15",
            order=81,
        ),
        keep(
            "office",
            ["09.5.7:office"],
            conducta="office.document.*. Skill no autoriza. Cuenta hueco de Goal 10.",
            pruebas="ExternalCapabilityHandlerTests.",
            recursos="n/a.",
            arquitectura="Catálogo, no skill con efectos.",
            live_owner="src/Baxy.Providers.Windows",
            owning_test="tests/Baxy.Providers.Windows.Tests/ExternalCapabilityHandlerTests.cs",
            valor_10_11="10.14",
            order=82,
        ),
        keep(
            "comunicacion",
            ["09.5.7:comunicacion"],
            conducta="message.* email.* calendar.*. Halt sin sesión. Halt de «envía un mensaje».",
            pruebas="DesktopMessagingAdapterTests.",
            recursos="n/a.",
            arquitectura="Estados honestos si falta cuenta.",
            live_owner="src/Baxy.Providers.Windows",
            owning_test="tests/Baxy.Providers.Windows.Tests/DesktopMessagingAdapterTests.cs",
            valor_10_11="10.15",
            order=83,
        ),
        keep(
            "sistema",
            ["09.5.7:sistema"],
            conducta="system.* audio.*. Postread Core Audio. Power no restaurable con razón.",
            pruebas="AudioVolumeHandlerTests.",
            recursos="n/a.",
            arquitectura="Mute con readback (no mute-sin-readback).",
            live_owner="src/Baxy.Providers.Windows",
            owning_test="tests/Baxy.Providers.Windows.Tests/AudioVolumeHandlerTests.cs",
            valor_10_11="10.13",
            order=84,
        ),
        keep(
            "conectividad",
            ["09.5.7:conectividad"],
            conducta="network.* wifi.* bluetooth.*. Dos lecturas; sin SSID inventado.",
            pruebas="WindowsNetworkStatusProviderTests.",
            recursos="n/a.",
            arquitectura="Estados honestos; puerta de dominio no fail-closed por verbo extra.",
            live_owner="src/Baxy.Providers.Windows",
            owning_test="tests/Baxy.Providers.Windows.Tests/WindowsNetworkStatusProviderTests.cs",
            valor_10_11="10.13",
            order=85,
        ),
        keep(
            "mision_compuesta",
            ["09.5.7:mision_compuesta"],
            conducta="app.open + input.visible.click. R6 6/6 22/22; Steam→biblioteca.",
            pruebas="test_compound_missions.py. Goal 10.16 pedirá C10≥74; aquí no se ejecuta.",
            recursos="MissionEngine vivo, no microagentes.",
            arquitectura="Encadenar operaciones, no añadir catálogo.",
            live_owner="src/Baxy.Kernel MissionEngine + src/baxy_mind/planner.py",
            owning_test="tests/test_compound_missions.py",
            valor_10_11="10.16",
            order=86,
        ),
        reject(
            "routers_en_serie",
            ["09.5.7:routers_en_serie"],
            conducta="Tres routers en serie Carter v4/v5; agent loop 911–1397 líneas; flags que apagan capas.",
            pruebas="Goal 01 mapa. carter-v4-agent-loop. FG planner no standalone.",
            recursos="10 de 16 s/turno sobrecarga propia (PG4).",
            arquitectura="Un router (mente) + kernel. No tres.",
            mecanismo_de_fracaso="Cada router tapa el fallo del anterior. Recortar el catálogo que el LLM ve.",
            coste="Acumulación, no reemplazo.",
            invariante="ley 2",
            order=87,
        ),
        reject(
            "listas_hardcodeadas_por_app",
            ["09.5.7:listas_hardcodeadas_por_app"],
            conducta="F0 prompt Steam/Discord/Spotify; CORE_PROMPT few-shots; capabilities/steam.py allowlist.",
            pruebas="f0-prompt-hardcodes-rechazado; carter-v2-hardcode-guard (marcas movidas a steam.py).",
            recursos="2.454 líneas / 4 apps.",
            arquitectura="Cubrir el PC, no las apps.",
            mecanismo_de_fracaso="El nombre de la app vive en catálogo y adapter. Cobertura falsa.",
            coste="Más catálogo, menos PC genérico.",
            invariante="Identidad: cubrir el PC",
            order=88,
        ),
        reject(
            "respuestas_fijas",
            ["09.5.7:respuestas_fijas"],
            conducta="CORE_PROMPT saludos fijos, regla 9, anti-echo post-LLM, harness stubs de hora.",
            pruebas="carter-v4-gemma4-core-prompt reject. Goal 04/06.",
            recursos="n/a.",
            arquitectura="Toda prosa la formula el modelo.",
            mecanismo_de_fracaso="Constante visible ≠ hecho verificado.",
            coste="Narración constante; Goal 04/06 ya lo vetan.",
            invariante="invariante 5",
            order=89,
        ),
        reject(
            "exitos_no_verificados",
            ["09.5.7:exitos_no_verificados"],
            conducta="verify.py «tool ok», mute sin readback, orchestrator UNVERIFIED heurístico, stubs OpenAI, Qwen-VL visual-diff.",
            pruebas="fake-success-eje-de-tesis; Goal 05.",
            recursos="n/a.",
            arquitectura="Postcondición independiente del ejecutor.",
            mecanismo_de_fracaso="El recibo del ejecutor no es Windows. PASS de stub no prueba efecto.",
            coste="Estados falsos (Carter v1 coordenadas ciegas).",
            invariante="invariante 2/3",
            order=90,
        ),
        keep(
            "simple-app-open-notepad",
            ["09.5.7:simple-app-open-notepad"],
            conducta="Misión Goal 10 inventariada: app.open Bloc de notas. Completa y verificada en el árbol vivo.",
            pruebas="AppOpenHandlerTests / compound. No se reconstruye el script Carter.",
            recursos="n/a.",
            arquitectura="Operación de catálogo, no smoke histórico.",
            live_owner="src/Baxy.Providers.Windows",
            owning_test="tests/Baxy.Providers.Windows.Tests/AppOpenHandlerTests.cs",
            valor_10_11="10.16 C10",
            order=91,
        ),
        keep(
            "simple-audio-volume",
            ["09.5.7:simple-audio-volume"],
            conducta="audio.volume con postread Core Audio. Completa en el vivo.",
            pruebas="AudioVolumeHandlerTests.",
            recursos="n/a.",
            arquitectura="Readback, no mute-sin-readback.",
            live_owner="src/Baxy.Providers.Windows",
            owning_test="tests/Baxy.Providers.Windows.Tests/AudioVolumeHandlerTests.cs",
            valor_10_11="10.16",
            order=92,
        ),
        keep(
            "simple-note-create",
            ["09.5.7:simple-note-create"],
            conducta="note.create verificado. Completa en el vivo.",
            pruebas="CoreNotesEndToEndTests.",
            recursos="n/a.",
            arquitectura="CAS/SHA, no creer a Create.",
            live_owner="src/Baxy.Core notes",
            owning_test="tests/Baxy.Integration.Tests/CoreNotesEndToEndTests.cs",
            valor_10_11="10.16 / 10.14",
            order=93,
        ),
        keep(
            "chained-steam-library",
            ["09.5.7:chained-steam-library"],
            conducta="Cadena «Abre Steam y ve a la biblioteca» medida 2026-08-23. Completa.",
            pruebas="test_compound_missions.py R6.",
            recursos="UIA/OCR, no Qwen-VL.",
            arquitectura="Misión = catálogo encadenado.",
            live_owner="src/Baxy.Kernel MissionEngine",
            owning_test="tests/test_compound_missions.py",
            valor_10_11="10.16",
            order=94,
        ),
        keep(
            "chained-open-then-volume",
            ["09.5.7:chained-open-then-volume"],
            conducta="Forma abrir+volumen. Completa.",
            pruebas="test_compound_missions.py.",
            recursos="n/a.",
            arquitectura="Encadenar, no microagente.",
            live_owner="src/Baxy.Kernel MissionEngine",
            owning_test="tests/test_compound_missions.py",
            valor_10_11="10.16",
            order=95,
        ),
        reject(
            "historical-carter-v2-compound-smoke",
            ["09.5.7:historical-carter-v2-compound-smoke"],
            conducta="Smoke Carter v2 scripted incompleto (detector ciego). No se hereda el detector.",
            pruebas="09.5.7: incomplete. Goal 10.16 usará C10≥74 del vivo, no el smoke.",
            recursos="n/a.",
            arquitectura="Detector ciego ≠ postcondición.",
            mecanismo_de_fracaso="Marca trivial; steam_open_client hardcodeado.",
            coste="Falso completo de misión.",
            invariante="invariante 2",
            order=96,
        ),
        keep(
            "runtime_servidor",
            ["09.5.8:runtime_servidor"],
            conducta="llama-server sidecar 127.0.0.1 puerto efímero; Job Object. No Ollama ni servicio Windows.",
            pruebas="R281. ADR-0005.",
            recursos="Subproceso, no servicio persistente.",
            arquitectura="Un runtime de inferencia.",
            live_owner="src/baxy_mind/llm.py + process_lifecycle.py",
            owning_test="tests/test_registered_runtime_expectation_r281.py",
            valor_10_11="10.0",
            order=100,
        ),
        keep(
            "carga_descarga_modelos",
            ["09.5.8:carga_descarga_modelos"],
            conducta="Keep-warm vivo (llama-server permanece cargado). vram_manager Carter / restart de perfiles no comparten hardware, llama.cpp ni escenario idle 10.2. No es un win histórico: no se transplanta unload.",
            pruebas="R281 carga al crear sidecar. Idle 15 min vs unload es medición de producto Goal 10.2, no comparabilidad de herencia.",
            recursos="Warm GPU ~3066 MiB. Unload histórico no sustituye keep-warm aquí.",
            arquitectura="Un sidecar; no se apila vram_manager.py.",
            live_owner="src/baxy_mind/llm.py",
            owning_test="tests/test_registered_runtime_expectation_r281.py",
            valor_10_11="10.2 mide presencia; 09.5.9 no transplanta unload",
            order=101,
        ),
        keep(
            "vram_ram_cpu",
            ["09.5.8:vram_ram_cpu"],
            conducta="Qwen pico ~3066/3072 MiB. Oído idle RSS 1088 MB, GPU 510/16380, llama-server off. hermes3 4857 MiB incomparable.",
            pruebas="Goal 03 / MVP + Goal 09 idle. Hardware+versión+escenario+denominador.",
            recursos="Techo 4 GiB producto; 16 GB host no es presupuesto.",
            arquitectura="Sobrecarga propia ≠ inferencia.",
            live_owner="src/baxy_mind/llm.py + Providers.Windows/SystemStatus",
            owning_test="tests/Baxy.Integration.Tests/GpuSystemStatusHandlerTests.cs",
            valor_10_11="10.2",
            order=102,
        ),
        keep(
            "latencia_llm",
            ["09.5.8:latencia"],
            conducta="p50 2,18 s / p90 3,02 s n=122. PG4 10/16 s es otro stack, no victoria del p50 vivo.",
            pruebas="Goal 03 corpus fresco. Listón 3 s; bajo carga p50 3,7–4,0 s ya en 09.5.5.",
            recursos="GPU decisor. Encoder E5 memo 27,5 ms no es el p50.",
            arquitectura="time_budget.py separa mente / Core / formulación / primer contenido.",
            live_owner="src/baxy_mind/llm_transport.py",
            owning_test="tests/Baxy.Kernel.Tests/FirstSignalTests.cs",
            valor_10_11="10.2 / 10.7",
            order=103,
        ),
        keep(
            "arranque",
            ["09.5.8:arranque"],
            conducta="Baxy.App + process_lifecycle. Tournament round_b_lifecycle no es cold start de producto. Carter preload NEEDS_ENVIRONMENT. No hay pieza histórica que transplantar; Goal 10.2 mide cold start/reinicio del vivo.",
            pruebas="test_process_lifecycle.py. Sin cifra alineada hardware+versión+escenario de arranque frío — incomparable, no lote de herencia.",
            recursos="Spawn Core + mente + WebView2; encoder E5 ~11 s histórico ya reparado.",
            arquitectura="Job Object kill-on-close. No soak 24 h.",
            live_owner="src/Baxy.App/CoreProcessClient.cs + process_lifecycle.py",
            owning_test="tests/test_process_lifecycle.py",
            valor_10_11="10.2 mide arranque; 09.5.9 conserva el vivo",
            order=104,
        ),
        keep(
            "watchdog",
            ["09.5.8:watchdog"],
            conducta="reap acotado + Job Object. No vram_watchdog.py entero (NVML pre-turno 250 ms).",
            pruebas="test_process_lifecycle.py. Framework PG4 es capa extra.",
            recursos="Sin pynvml por turno.",
            arquitectura="Un vigilante de hijos, no dos.",
            live_owner="src/baxy_mind/process_lifecycle.py",
            owning_test="tests/test_process_lifecycle.py",
            valor_10_11="10.2",
            order=105,
        ),
        keep(
            "estabilidad",
            ["09.5.8:estabilidad"],
            conducta="Idle 15 min es plan 10.2. _soak50 / 24 h no es requisito. soak-24h-as-requirement rechazado aparte.",
            pruebas="09.5.8 soak_24h_requirement=false.",
            recursos="No se reserva 24 h de GPU.",
            arquitectura="Presencia diaria ≠ soak.",
            live_owner="src/baxy_mind/process_lifecycle.py",
            owning_test="tests/test_process_lifecycle.py",
            valor_10_11="10.2 idle corto, no 24 h",
            order=106,
        ),
        keep(
            "field_ui_accesibilidad",
            ["09.5.8:field_ui_accesibilidad"],
            conducta="FieldUi dist ADR-0008. Accesibilidad central en el motor, modo en la UI. No se rescata ui_field/accessibility.py de PG4.",
            pruebas="ADR-0008. Goal 09 voz en el motor.",
            recursos="WebView2 local; bloqueo de requests externos.",
            arquitectura="No segunda UI histórica.",
            live_owner="src/Baxy.FieldUi",
            owning_test="tests/Baxy.App.Tests (FieldUi dist) / censo voz",
            valor_10_11="10.17",
            order=107,
        ),
        reject(
            "vision_camara",
            ["09.5.8:vision_camara"],
            conducta="Cámara-gaze PG4 es POC aislado (validity requiere_remeidir). Visión de producto = cascada de pantalla. Qwen-VL R-023 aparte.",
            pruebas="docs-010 visión/cámara. Cámara no es producto.",
            recursos="Cámara + gaze ≠ Click X.",
            arquitectura="No se añade cámara al recinto 10.10 como motor.",
            mecanismo_de_fracaso="POC de mirada no es visión verificable de Windows. Qwen-VL inventó juegos.",
            coste="Dispositivo + segundo pipeline.",
            invariante="Identidad: cubrir el PC (pantalla), no gaze",
            live_owner="src/Baxy.Providers.Windows (pantalla, no cámara)",
            owning_test="tests/Baxy.Providers.Windows.Tests/VisibleClickCascadeTests.cs",
            order=108,
        ),
        keep(
            "memoria_proactividad",
            ["09.5.8:memoria_proactividad"],
            conducta="Providers.Windows/Memory protegida. Identidad veta actuar solo. No jarvis proactive.",
            pruebas="MemoryAppFlowTests.",
            recursos="n/a.",
            arquitectura="Memoria ≠ proactividad no pedida.",
            live_owner="src/Baxy.Providers.Windows/Memory",
            owning_test="tests/Baxy.Integration.Tests/MemoryAppFlowTests.cs",
            valor_10_11="10.14",
            order=109,
        ),
        keep(
            "journal",
            ["09.5.8:journal"],
            conducta="Kernel/Journal HMAC v2.",
            pruebas="Kernel journal tests.",
            recursos="n/a.",
            arquitectura="Journal único, no telemetry.py.",
            live_owner="src/Baxy.Kernel/Journal",
            owning_test="tests/Baxy.Kernel.Tests (Journal HMAC)",
            valor_10_11="10.0 / 11",
            order=110,
        ),
        keep(
            "setup_publish",
            ["09.5.8:setup_publish"],
            conducta="Baxy.Setup NativeAOT ADR-0003/0004. hf_publish no es instalador.",
            pruebas="Baxy.Setup.Tests. Setup no se tocó.",
            recursos="13k líneas de setup: APLAZADOS, funciona.",
            arquitectura="Publish ≠ HuggingFace upload.",
            live_owner="src/Baxy.Setup",
            owning_test="tests/Baxy.Setup.Tests",
            valor_10_11="10.0",
            order=111,
        ),
        keep(
            "privacidad",
            ["09.5.8:privacidad"],
            conducta="Inbound web; cero contenido de usuario outbound. No telemetry.py ni API_KEY.",
            pruebas="MemoryAppFlowTests + ADR-0008 bloqueo externo.",
            recursos="n/a — dirección de red.",
            arquitectura="Invariante 6.",
            live_owner="src/Baxy.Kernel/Policy + Baxy.Security.Windows",
            owning_test="tests/Baxy.Integration.Tests/MemoryAppFlowTests.cs",
            valor_10_11="10.17",
            order=112,
        ),
        keep(
            "seguridad",
            ["09.5.8:seguridad"],
            conducta="ConfirmationAuthority + política de riesgo. AUTO_APPROVE rechazado en fila protegida aparte; el vivo se conserva.",
            pruebas="ConfirmationAuthorityTests.",
            recursos="n/a.",
            arquitectura="Invariantes 3 y 4. Token no reutilizable.",
            live_owner="src/Baxy.Kernel/Policy",
            owning_test="tests/Baxy.Kernel.Tests/ConfirmationAuthorityTests.cs",
            valor_10_11="10.17",
            order=113,
        ),
        keep(
            "diagnosticos",
            ["09.5.8:diagnosticos"],
            conducta="app.status + GPU provider + health llama-server. _diag PG4 no entra al runtime. Red/temp = no disponible, no inventado.",
            pruebas="GpuSystemStatusHandlerTests.",
            recursos="Telemetría local ADR-0008.",
            arquitectura="Existir un log de cacería no es health.",
            live_owner="src/Baxy.Providers.Windows/SystemStatus",
            owning_test="tests/Baxy.Integration.Tests/GpuSystemStatusHandlerTests.cs",
            valor_10_11="10.2",
            order=114,
        ),
        reject(
            "auto_approve",
            [],
            conducta="Carter AUTO_APPROVE en .env. El vivo exige confirmación ligada a invocationId. No se silencia: queda como rechazo protegido.",
            pruebas="carter-v2-runtime-env; ConfirmationAuthorityTests. 09.5.8 seguridad conserva el vivo y nombra AUTO_APPROVE como no-sustituto.",
            recursos="n/a.",
            arquitectura="Confirmación ≠ auto-yes.",
            mecanismo_de_fracaso="Efectos sin invocación confirmada. Rompe invariante 4.",
            coste="Efectos no pedidos (Goal 04).",
            invariante="invariante 4 (confirmación ligada a la invocación exacta)",
            live_owner="src/Baxy.Kernel ConfirmationAuthority",
            owning_test="tests/Baxy.Kernel.Tests/ConfirmationAuthorityTests.cs",
            protected=True,
            order=5,
        ),
        reject(
            "soak-24h-as-requirement",
            [],
            conducta="Soak 24 h no es listón de producto ni de 09.5.8/10.2. Idle corto 15 min es el recinto. _soak50 no se convierte en requisito.",
            pruebas="09.5.8 soak_24h_requirement=false. Goal 10.2: no hay soak ni reinicio de Windows.",
            recursos="24 h de GPU no se reserva.",
            arquitectura="Presencia diaria ≠ soak de lab.",
            mecanismo_de_fracaso="Convertir un soak de investigación en gate de cierre.",
            coste="Bloquea 10–11 con un listón que Identidad no pide.",
            invariante="ley 3 (sólo se arregla lo que bloquea) + recinto 10.2",
            live_owner="n/a — no hay soak en el vivo",
            owning_test="tests/test_goal095_0958_synthesis.py",
            protected=True,
            order=6,
        ),
        keep(
            "residual_docs",
            [],
            conducta="Tarjetas docs 09.5.2 no citadas por 09.5.5–09.5.8: auditoria leída. No hay mecanismo vivo que transplantar; el mapa/Identidad actuales cubren la tesis.",
            pruebas="Campaña docs 25/25 complete. validity documental.",
            recursos="n/a.",
            arquitectura="Evidencia, no instrucción. No se reabre biblioteca.",
            live_owner="documentacion/ + documentacion/herencia/",
            owning_test="tests/test_goal095_docs_ledger.py",
            valor_10_11="recordatorio, no lote",
            order=800,
        ),
        reject(
            "residual_code_foreign",
            [],
            conducta="Código Carter / Probando Gemma 4 / FunctionGemma / Schema Agent auditado y no seleccionado por 09.5.5–09.5.8. No entra al árbol vivo.",
            pruebas="Campaña code_tests 477/477. Cero trasplantes en síntesis previas.",
            recursos="Traer loaders/watchdogs/ui_field duplicaría el camino vivo.",
            arquitectura="Ley 1 ya se aplicó en 09.5.5–09.5.8; el resto es rechazo por no selección.",
            mecanismo_de_fracaso="Pieza histórica no comparada como win y no citada como mejor viva.",
            coste="Segundo runtime/UI/catálogo «por si acaso».",
            invariante="ley 2 (si se añade, se retira) — aquí no se añade",
            order=801,
        ),
        keep(
            "residual_code_predecessor",
            [],
            conducta="Código del BAXY anterior (a secas) auditado y no citado: el Definitivo ya absorbió la base .NET. Lo no seleccionado no se re-importa.",
            pruebas="code_tests baxy complete. Live owners en src/Baxy.* y src/baxy_mind.",
            recursos="No se clona Programacion/BAXY.",
            arquitectura="Predecesor = evidencia; el vivo manda.",
            live_owner="src/Baxy.* + src/baxy_mind",
            owning_test="tests/test_goal095_0958_synthesis.py",
            valor_10_11="no lote",
            order=802,
        ),
        keep(
            "residual_evidence",
            [],
            conducta="Assets/JSONL 09.5.4 no citados: parseados o inventariados. Existir no es works. No se copian datasets/GGUF. Hashes dispersos not invented.",
            pruebas="Campaña evidence 132/132. _09510_requirements.json.",
            recursos="17 GiB GGUF / 39 GiB data omitidos a propósito.",
            arquitectura="Evidencia fechada, no fuente de producto.",
            live_owner="artifacts/goal095/extract + _09510_requirements.json",
            owning_test="tests/test_goal095_0958_synthesis.py",
            valor_10_11="no lote; 10.1 no reparsea 09.5.4",
            order=803,
        ),
    ]


def _walk_card_ids(obj: Any, acc: list[str]) -> None:
    if isinstance(obj, dict):
        cid = obj.get("card_id")
        if cid:
            acc.append(str(cid))
        for value in obj.values():
            _walk_card_ids(value, acc)
    elif isinstance(obj, list):
        for value in obj:
            _walk_card_ids(value, acc)


def _synth_citation_map(repo: Path) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}

    def add(ref: str, obj: Any) -> None:
        found: list[str] = []
        _walk_card_ids(obj, found)
        mapping[ref] = found

    s55 = load_json(repo / SYNTHESIS_0955)
    for row in s55.get("current_stack") or []:
        add(f"09.5.5:{row['id']}", row)
    for row in s55.get("candidates") or []:
        add(f"09.5.5:{row['id']}", row)
    s56 = load_json(repo / SYNTHESIS_0956)
    for row in s56.get("subareas") or []:
        add(f"09.5.6:{row['id']}", row)
    add("09.5.6:qwen_asr", s56.get("qwen_asr") or {})
    add("09.5.6:gemma_native_audio", s56.get("gemma_native_audio") or {})
    s57 = load_json(repo / SYNTHESIS_0957)
    for row in s57.get("capabilities") or []:
        add(f"09.5.7:{row['id']}", row)
    for row in s57.get("rejections") or []:
        add(f"09.5.7:{row['pattern']}", row)
    for row in s57.get("missions") or []:
        add(f"09.5.7:{row['id']}", row)
    add("09.5.7:qwen_vl", s57.get("qwen_vl") or {})
    s58 = load_json(repo / SYNTHESIS_0958)
    for row in s58.get("areas") or []:
        add(f"09.5.8:{row['id']}", row)
    add("09.5.8:qwen_vl", s58.get("qwen_vl") or {})
    return mapping


def _audit_cards(repo: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    ledger_dir = repo / "artifacts" / "goal095" / "ledger"
    for path in sorted(ledger_dir.glob("*.json")):
        data = load_json(path)
        if data.get("kind") not in AUDIT_KINDS:
            continue
        kind = str(data.get("kind"))
        source = str(data.get("source_id") or "")
        for card in data.get("cards") or []:
            cid = card.get("card_id")
            if not cid or cid in seen:
                continue
            seen.add(str(cid))
            rows.append({"card_id": str(cid), "kind": kind, "source_id": source})
    return rows


def _residual_row(kind: str, source: str) -> str:
    if kind == "docs":
        return "residual_docs"
    if kind == "evidence_assets":
        return "residual_evidence"
    if source in {"carter", "probando_gemma4", "functiongemma", "baxy_schema_agent"}:
        return "residual_code_foreign"
    return "residual_code_predecessor"


EMPTY_REASON = (
    "09.5.5–09.5.8 no hallaron pieza histórica que gane al vivo en conducta, "
    "pruebas, recursos y arquitectura a la vez. Cero reusar_exacto, cero adaptar, "
    "cero medir_antes de herencia: unload-on-idle y arranque frío son mediciones "
    "de producto del Goal 10.2 sobre el keep-warm/process_lifecycle vigentes, no "
    "un vram_manager/Ollama/ui_field que transplantar. Los GGUF/datasets/checkpoints "
    "dispersos de Probando Gemma 4 no se nombran para reutilizar (hashes not invented). "
    "Cada lote de herencia habría tenido que retirar el mecanismo vivo en el mismo "
    "cambio; no hay tal lote. Rechazos protegidos (FunctionGemma en pesos, Qwen-VL "
    "R-023, Ollama/servicio Windows, AUTO_APPROVE, soak 24 h como requisito, "
    "Gemma-native-audio como oído) no reentran."
)


def build(repo: Path = REPO) -> dict[str, Any]:
    rows = responsibilities()
    by_id = {row["id"]: row for row in rows}
    if len(by_id) != len(rows):
        raise SystemExit("duplicate row id in builder")
    for name in PROTECTED_REJECTS:
        if name not in by_id or by_id[name]["decision"] != "rechazar":
            raise SystemExit(f"protected {name} missing or not rechazar")

    synth_ids = index_synthesis_responsibility_ids(repo)
    assigned_refs: set[str] = set()
    ref_to_row: dict[str, str] = {}
    for row in rows:
        for ref in row["synthesis_refs"]:
            if ref in assigned_refs:
                raise SystemExit(f"duplicate synthesis_ref {ref}")
            assigned_refs.add(ref)
            ref_to_row[ref] = row["id"]
    missing = synth_ids - assigned_refs
    extra = assigned_refs - synth_ids
    if missing or extra:
        raise SystemExit(f"synthesis ref mismatch missing={sorted(missing)} extra={sorted(extra)}")

    cite_map = _synth_citation_map(repo)
    assignment: dict[str, str] = {}
    # Protected rows first, then declaration order.
    ordered = sorted(rows, key=lambda row: (0 if row["id"] in PROTECTED_REJECTS else 1, row["order"], row["id"]))
    for row in ordered:
        for ref in row["synthesis_refs"]:
            for cid in cite_map.get(ref, []):
                assignment.setdefault(cid, row["id"])

    for card in _audit_cards(repo):
        cid = card["card_id"]
        if cid in assignment:
            continue
        assignment[cid] = _residual_row(card["kind"], card["source_id"])

    counts_by_row: dict[str, int] = {}
    for rid in assignment.values():
        counts_by_row[rid] = counts_by_row.get(rid, 0) + 1

    matrix = {
        "schema": SCHEMA,
        "goal": "09.5.9",
        "closed_utc": CLOSED_UTC,
        "inventory_source": "artifacts/goal095/ledger/*.json cards 09.5.2–09.5.4 + synthesis 09.5.5–09.5.8 JSON; no biblioteca bodies; no source-tree walk",
        "next_human_prompt": TRANSPLANT_PROMPT,
        "terminals": [
            "reusar_exacto",
            "adaptar",
            "conservar_actual",
            "medir_antes",
            "rechazar",
        ],
        "protected_rejects": list(PROTECTED_REJECTS),
        "languages_in_scope": ["es", "en", "spanglish"],
        "other_languages_create_work": False,
        "estado_del_arte_added": False,
        "live_src_changed": False,
        "live_weights_changed": False,
        "catalog_constraint": "El catálogo sigue siendo datos tipados autorizados por el kernel, nunca nombres cocidos en pesos.",
        "sparse_assets": {
            "ref": "artifacts/goal095/extract/_09510_requirements.json",
            "ids": ["pg4-gguf-models", "pg4-training-datasets", "pg4-training-checkpoints"],
            "individual_hashes": "not invented",
            "rule": "09.5.9 no reutiliza ningún blob disperso; 09.5.10 no pausa en FALLO_DE_AMBIENTE por GGUF/dataset/checkpoint",
        },
        "transplants_empty_reason": EMPTY_REASON,
        "card_counts": {
            "total": len(assignment),
            "by_row": counts_by_row,
        },
        "mapping_notes": (
            "09.5.8 `medir` en carga/descarga y arranque se mapea a conservar_actual: "
            "la pieza histórica es incomparable y no es candidata a transplant; Goal 10.2 "
            "mide el producto vivo. Etiquetas 09.5.5 conservar/medir/reemplazar_candidato "
            "y 09.5.8 reusar/medir no quedan como terminales vivos."
        ),
        "responsibilities": rows,
    }

    lots = lots_from_matrix(matrix)
    campaign = {
        "schema": "baxy.goal095.campaign.v1",
        "campaign_id": "transplant",
        "kind": "transplant",
        "required_human_launches": 1,
        "owner_prompt": TRANSPLANT_PROMPT,
        "migrated_from": "artifacts/goal095/synthesis/09.5.9_decidir_herencia.v1.json",
        "cursor_batch_id": None,
        "cursor_status": "complete" if not lots else "pending",
        "counts": {
            "pending": 0 if not lots else len(lots),
            "claimed": 0,
            "complete": 0,
            "total": len(lots),
        },
        "lots": lots,
        "empty_reason": EMPTY_REASON if not lots else "",
        "next_human_prompt": TRANSPLANT_PROMPT,
        "updated_utc": _now(),
        "protected_rejects_blocked": list(PROTECTED_REJECTS),
    }
    # keep counts in sync with helper
    synced = campaign_counts(campaign)
    campaign["counts"]["pending"] = synced["pending"]
    campaign["counts"]["claimed"] = synced["claimed"]
    campaign["counts"]["complete"] = synced["complete"]
    campaign["counts"]["total"] = len(lots)

    assignment_doc = {
        "schema": "baxy.goal095.0959-card-assignment.v1",
        "goal": "09.5.9",
        "matrix_ref": SYNTHESIS_REL.replace("\\", "/"),
        "total": len(assignment),
        "card_to_row": dict(sorted(assignment.items())),
    }

    dump_json(repo / SYNTHESIS_REL, matrix)
    dump_json(repo / ASSIGNMENT_REL, assignment_doc)
    dump_json(repo / CAMPAIGN_REL, campaign)

    ledger = {
        "schema": "baxy.goal095.0959-ledger.v1",
        "batch_id": "synthesis-09.5.9",
        "kind": "synthesis",
        "status": "complete",
        "goal": "09.5.9",
        "closed_utc": CLOSED_UTC,
        "synthesis_ref": SYNTHESIS_REL.replace("\\", "/"),
        "assignment_ref": ASSIGNMENT_REL.replace("\\", "/"),
        "campaign_ref": CAMPAIGN_REL.replace("\\", "/"),
        "markdown_ref": "documentacion/herencia/09_5_9_DECIDIR_HERENCIA.md",
        "inventory_source": matrix["inventory_source"],
        "campaigns_remain_closed": {
            "docs": "25/25 pending=0 claimed=0",
            "code_tests": "477/477 pending=0 claimed=0",
            "evidence_assets": "132/132 pending=0 claimed=0",
        },
        "transplant": {
            "pending": campaign["counts"]["pending"],
            "claimed": campaign["counts"]["claimed"],
            "complete": campaign["counts"]["complete"],
            "total": campaign["counts"]["total"],
        },
        "protected_rejects": list(PROTECTED_REJECTS),
        "live_src_changed": False,
        "estado_del_arte_added": False,
        "fallo_de_ambiente": [],
        "next_prompt": TRANSPLANT_PROMPT,
    }
    dump_json(repo / LEDGER_REL, ledger)
    return {
        "rows": len(rows),
        "cards": len(assignment),
        "lots": len(lots),
        "protected": list(PROTECTED_REJECTS),
    }


def main() -> None:
    summary = build(REPO)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
