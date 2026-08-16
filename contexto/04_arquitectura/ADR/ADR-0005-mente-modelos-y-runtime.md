# ADR-0005 — Mente de BAXY 1.0: arquitectura de inteligencia y modelos

- Estado: **aceptado**.
- Fecha: 2026-07-16.
- Ámbito: router de intención, LLM de conversación/tools, STT, y el runtime
  de modelos como sidecar Python. No modifica el cuerpo determinista
  (ADR-0001) ni el catálogo congelado de 22 operaciones/21 tools.
- Protocolos congelados antes de medir:
  `experiments/mind_router_spike/tournament_encoder_protocol.json` y
  `experiments/mind_llm_tournament/protocol.json` (commit `fc3141c`).
- Evidencia: `experiments/mind_router_spike/results/` (spike + scorecard de
  encoders), `experiments/mind_llm_tournament/results/` (scorecard LLM +
  revisión juzgada + medición VRAM).

## Contexto

El cuerpo determinista quedó en 8/15 Must con cuatro costuras listas. Los
gates 4, 7, 8, 9 y 12 exigen: comprensión de intención por embeddings (ley
de no-keywords), voz al cerebro, planner/composición con riesgo, conversación
general y medición honesta del presupuesto 4 GB VRAM con fallback CPU.

El spike de de-riesgo (Fase 2) demostró que un router por pools de embeddings
multilingües iguala al regex interino sobre los 675 casos de los oráculos
congelados (674/675, cero contratos violados) y generaliza 89,3 % (LOO)
donde el regex generaliza ≈0 %. Veredicto: PROCEDE
(`experiments/mind_router_spike/VEREDICTO.md`).

## Arquitectura de la mente

```
texto ──► MissionInput ──► sidecar mente (Python, JSONL + Job Object)
voz ──► STT (Parakeet v3, CPU) ──► VoiceTranscript ─┘
                    │
        1) Router embeddings (e5-small, CPU, ~16 ms)
           ├─ intención clara → operación tipada → core .NET (21 tools)
           └─ abstención (fail-closed) → 2) LLM (Gemma-4 E2B QAT, llama.cpp)
                    ├─ conversación natural ES/EN/spanglish
                    ├─ tool-calling sobre el catálogo (schemas del hello)
                    └─ composición/planner con política de riesgo del core
        3) Narración: resultado tipado → respuesta natural (LLM con
           fallback determinista al narrador actual)
```

- Los modelos viven SOLO en el sidecar Python, segundo proceso local sobre la
  frontera JSONL UTF-8 estricta con Job Object kill-on-close que Codex dejó
  acreditada. El core .NET no incorpora IA.
- El router decide primero (barato, fail-closed); el LLM recibe solo lo que
  el router abstiene, más la extracción de argumentos y la conversación.
- La política de riesgo/confirmación permanece en el core determinista: la
  mente propone operaciones tipadas; el core valida schema, riesgo y
  confirmaciones exactamente como hoy.

## Decisión 1 — Router de intención: `intfloat/multilingual-e5-small`

Torneo de 4 candidatos bajo protocolo congelado (umbral por candidato fijado
solo en dev; corrida única sobre oráculos; hard gate = 0 contratos violados
en cobertura y CPU puro):

| Candidato | Cobertura | LOO | Peligrosos LOO | ms/consulta CPU | RAM MiB | Peso MiB |
|---|---|---|---|---|---|---|
| **multilingual-e5-small (118M)** | **99,85 %** | **89,33 %** | 37 | **15,8** | **880** | **470** |
| embeddinggemma-300m | 99,85 % | 87,11 % | **21** | 78,0 | 1110 | 1211 |
| Qwen3-Embedding-0.6B | 99,41 % ✗ | 88,30 % | 28 | 243,4 | 1178 | 1152 |
| paraphrase-MiniLM-L12-v2 | 98,67 % ✗ | 84,74 % | 26 | 13,6 | 1222 | 4407 |

- Qwen3-0.6B y MiniLM fallan el hard gate (sobre-abstención/rutas falsas en
  positivos de cobertura). e5-small y EmbeddingGemma comparten el único
  residual benigno («cuánta memoria me queda libre» → `system.status:memory`,
  read-only y semánticamente correcto; el contrato real del oráculo se
  cumple).
- Entre los dos de la frontera, la regla congelada (mayor LOO, diferencia
  2,2 pp > 1 pp) da ganador a e5-small — que además es el más rápido, liviano
  y pequeño. EmbeddingGemma queda como fallback documentado (menos fallos
  peligrosos en LOO: 21 vs 37; si la integración muestra exceso de rutas
  peligrosas, es el primer candidato de reemplazo).
- El banco de producción = anclas autoradas + corpus curado completo
  (positivos y negativos), con clave de identidad que conserva tildes
  (`accent_polarity`). Crecimiento futuro por telemetría→exemplars, sin
  retrain (decisión heredada documentada).

## Decisión 2 — LLM de conversación y tools: Gemma-4 E2B it QAT (Q4_K_XL, llama.cpp)

Torneo de 5 candidatos GGUF contra 362 casos de oráculo (tools reales del
hello del core) + 30 probes de conversación curados ES/EN/spanglish:

| Candidato | Tools+args | Abstención neg. | Conversación juzgada | p50 | VRAM delta | GGUF MiB |
|---|---|---|---|---|---|---|
| **gemma4-e2b-qat** | 76,5 % | **92,9 %** | **87 %** | **0,32 s** | **1.540 MiB** | 2.499 |
| qwen3.5-4b | **84,8 %** | 91,8 % | 77 % | 0,79 s | 3.028 MiB | 2.614 |
| qwen3.5-0.8b | 65,2 % | 49,0 % ✗ | — | 0,32 s | — | 508 |
| lfm2.5-1.2b | 35,6 % | 65,3 % ✗ | — | 0,21 s | — | ~800 |
| phi-4-mini | excluido técnico: no emite tool calls bajo llama.cpp `--jinja` | | | | | 2.376 |

- Fórmula congelada (pos·0,4 + abst·0,3 + convo·0,3): gemma4 0,846 vs qwen
  0,840 → empate <2 pp → desempate congelado por menor VRAM pico:
  **1.540 vs 3.028 MiB** (delta del total de GPU con inferencia real; el
  contador por-proceso de nvidia-smi da N/A bajo WDDM). Gana gemma4-e2b-qat.
- Hallazgos cualitativos versionados (`convo_judged_review.md`): Qwen3.5-4B
  responde en español a prompts en inglés (6/30) y registró un recordatorio
  como memoria (capacidad inventada); Gemma-4 E2B hizo 0 llamadas mutantes en
  conversación y mantiene la identidad/límites. Coincide con la evidencia
  interna previa (experimento unificado 28/29, 2,3× más rápido).
- Debilidad conocida de ambos: argumentos de esquemas pesados de `memory.*`
  a pelo (10–47 %). Mitigación arquitectónica: el router enruta la intención
  de memoria (100 % cobertura) y el LLM extrae argumentos con la tool ya
  forzada (`tool_choice` dirigido); la gramática determinista de memoria y
  sus confirmaciones no cambian.
- Fallback documentado: Qwen3.5-4B (Apache 2.0), mejor en args crudos, a
  costa de idioma y doble VRAM.

## Decisión 3 — STT: Parakeet-TDT-0.6B-v3 int8 CPU (sherpa-onnx)

- Evidencia interna: barrido STT de julio 2026 (documentado) lo mantiene
  óptimo ES/EN; el stack de voz ya exportado y verificado (D28/D29) lo corre
  int8 en CPU vía sherpa-onnx con corrector fonético ES/EN y VAD; sin
  alucinación en silencio (evidencia Carter).
- Evidencia externa: Open ASR leaderboard 2026 (6,32 % WER vs 7,44 % de
  whisper-large-v3), paper arXiv 2509.14128; ~3.333× realtime.
- No se repite un torneo completo de STT: sería duplicar el barrido de este
  mismo mes (proporcionalidad). El gate 7 exige de todos modos validación
  física integrada (latencia y transcripción ES/EN/code-switch contra la
  puerta `VoiceTranscript`), que es donde se mide.
- Upgrade candidato documentado: Nemotron-3.5 ASR streaming 0.6B int4
  (ya en caché, soportado por sherpa-onnx) si el producto pasa a streaming
  parcial en vivo.

## Presupuesto de recursos (previo al gate 12)

| Componente | VRAM | RAM | Latencia |
|---|---|---|---|
| LLM Gemma-4 E2B QAT (GPU) | 1.540 MiB delta | ~2 GB | p50 0,32 s / p95 1,58 s |
| Router e5-small (CPU puro) | 0 | ~0,9 GB | ~16 ms |
| STT Parakeet int8 (CPU puro) | 0 | ~1 GB (histórico) | tiempo real |
| **Total estimado** | **~1,6 GB ≪ 4 GB** | ~4 GB | |

El fallback CPU del LLM existe por construcción (`-ngl 0` en llama.cpp). La
medición formal del gate 12 (VRAM/RAM/latencia/estabilidad, GPU capada y CPU
puro) se ejecuta sobre el sidecar integrado en la Fase 4 y queda como
artefacto propio.

## Consecuencias

1. La costura #1 se reemplaza por el router de embeddings; ninguna frase de
   idioma sobrevive fuera de la capa de parser declarada (la gramática
   determinista de memoria y la desambiguación de notas permanecen como capa
   de política/argumentos, no de detección de intención).
2. La costura #2 gana narración por LLM con fallback determinista fail-closed
   (si el sidecar no está o tarda, el narrador actual responde).
3. La costura #3 se consume tal cual: los schemas del hello son la fuente de
   verdad del tool-calling; el core sigue validando todo.
4. La costura #4 se materializa: un solo sidecar Python (`baxy-mind`) aloja
   router + LLM + STT, con llama-server como subproceso propio del sidecar
   bajo el mismo Job Object.
5. Los oráculos congelados pasan a ser la red de regresión de la mente: la
   configuración integrada debe igualar 675/675 contratos antes de cerrar
   gate 4.

## Revisión de eficiencia — 2026-07-23

La frontera de producto se fija ahora en **3 GiB de VRAM para la mente
completa**, no 4 GiB. La investigación vigente y la prueba local confirman que
Gemma-4 E2B QAT sigue siendo el ganador Pareto: E4B Q4 supera 5 GiB; Qwen3.5
4B supera el techo práctico del producto; y los candidatos menores no pasaron
el torneo de acciones seguro. El detalle, fuentes primarias actuales y
evidencia se conservan en
`contexto/03_investigacion/LLM_ESTADO_DEL_ARTE_2026-07-23.md`.

El perfil distribuible limita el contexto a 4.096 tokens, una sola ranura de
servidor, Flash Attention y KV Q8. No se habilita el contexto nominal de 128K,
MTP ni audio multimodal de Gemma sin una medición integrada nueva: Parakeet,
VAD, wake word, router y TTS continúan en CPU. El gate de lenguaje de este
perfil aprobó 25/25 y observó 1.507 MiB de delta de VRAM; el total de procesos
ajenos de Windows no se atribuye a BAXY.

## Criterio de reapertura

Reabrir si la integración física muestra: rutas peligrosas del router por
encima de lo tolerable (candidato: EmbeddingGemma), fallo del hard gate de
idioma o de efectos fabricados del LLM en el gate 9 (candidato: Qwen3.5-4B),
degradación de los oráculos congelados, o incumplimiento medido del
presupuesto 4 GB en el gate 12.
