# Brief de investigación — modelos para la mente de BAXY 1.0

- Fecha: 2026-07-15. Autor: Fable (mente). Estado: **panorama sin favoritos**;
  ningún candidato queda aprobado hasta el torneo de la Fase 3.
- Regla de de-sesgo aplicada: ningún modelo entra por haber sido usado antes
  (ni Gemma, ni Parakeet, ni FunctionGemma). Cada candidato entra por mérito
  levantado en investigación abierta (fuentes externas) o por evidencia interna
  reproducible del repo. Las dos procedencias se marcan.
- Restricciones reales: producto local Windows; presupuesto **4 GB VRAM**
  (~3 GB útiles con margen) **con fallback CPU**; ES/EN/spanglish incluidos
  code-switch y errores de STT; fail-closed; modelos SOLO en sidecar Python
  (JSONL + Job Object); la solución más simple que cierre el gate gana.

## Rol 1 — Embeddings de intención (router, gate 4)

Tarea: `texto → operación tipada` sobre el catálogo congelado (22 ops/21 tools),
con abstención fail-closed ante negativos y composiciones. Debe correr bien en
CPU (el router no puede depender de la GPU del usuario).

| Candidato | Tamaño | Procedencia | Fortalezas | Debilidades |
|---|---|---|---|---|
| Qwen3-Embedding-0.6B | 595M | Externa: MTEB 2026, paper Qwen3-Embedding | 64,3 MTEB; 100+ idiomas; eficiente en dimensiones bajas (32–128) vía MRL; Apache 2.0 | 0.6B es pesado para CPU si queremos p95 bajo; en caché HF no está (descarga) |
| EmbeddingGemma-300M | 300M | Externa: arXiv 2509.20354, comparativas 2026 | Gana a Qwen3-0.6B en clasificación multilabel/pair y reranking; diseñado on-device; QAT int4 | Licencia Gemma; requiere descarga |
| multilingual-e5-small | 118M | Externa (familia E5 sigue vigente en MMTEB) + **ya en caché local** | Muy liviano, CPU-friendly, sólido ES/EN; evidencia previa de uso en el stack histórico | Techo de calidad menor que 0.6B en tareas duras; prompt "query:/passage:" a respetar |
| paraphrase-multilingual-MiniLM-L12-v2 | 118M | Externa (clásico ST) + en caché local | Rápido, robusto a paráfrasis; bueno para pools de similitud | Generación 2021; suele perder contra E5/GTE modernos |
| mDeBERTa-v3-xnli (zero-shot NLI) | 279M | En caché local; literatura de intent-routing | Zero-shot por entailment, sin exemplars | Latencia por par (una pasada por etiqueta); histórico de fragilidad en spanglish |
| Static/Model2Vec (potion-multilingual) | ~30M | Externa: benchmarks de edge 2026 | Latencia sub-ms CPU | Calidad claramente menor; riesgo en code-switch |

Evidencia interna relevante: la ley histórica del repo (no keywords) nació de
que 99,64 % curado cayó a 85,7 % en logs reales con routers frágiles; el diseño
encoder→shortlist→caller del split FunctionGemma demostró que un encoder
multilingüe con pools por intención + abstención es viable y barato.

Plan de medición: spike Fase 2 con exemplars **disjuntos** de los oráculos
(sin contaminación train/eval), matriz de confusión por set y abstención en
negativos duros.

## Rol 2 — STT (gate 7)

Tarea: micrófono → `VoiceTranscript` hacia `MissionInput`. ES/EN/spanglish,
robusto a silencio (sin alucinación), local, presupuesto compartido con el LLM.

| Candidato | Tamaño | Procedencia | Fortalezas | Debilidades |
|---|---|---|---|---|
| NVIDIA Parakeet-TDT-0.6B-v3 | 0.6B | Externa: Open ASR leaderboard (6,32 % WER vs 7,44 % whisper-l-v3), paper 2509.14128 + **en caché y con evidencia interna** | ~3.333× realtime; sin alucinación en silencio (evidencia interna Carter); 25 idiomas incl. ES; corre CPU | Recuperación de entidades 81 % en evidencia interna; no streaming nativo en NeMo simple |
| Nemotron-3.5 ASR streaming 0.6B (onnx int4) | 0.6B int4 | Externa (sherpa-onnx) + en caché local | Streaming real de baja latencia; int4 CPU | Menos evidencia pública ES; calidad a medir |
| Canary-1B-v2 | 1B | Externa: 5,3 % WER multilingüe, RTFx 749 | Mejor WER multilingüe que whisper-l-v3; timestamps | 1B compite por presupuesto; más lento que Parakeet |
| Whisper large-v3-turbo | 809M | Externa: cobertura 99 idiomas | Mejor cobertura de idiomas y puntuación; robusto code-switch | ~6 GB VRAM cómodo o CPU lento; alucina en silencio (evidencia interna) |
| Moonshine 245M | 245M | Externa: reviews 2026 | Streaming diseñado; mínima VRAM | Cobertura 8 idiomas; ES a verificar; riesgo en spanglish |

Evidencia interna: el barrido STT de julio 2026 (documentado) mantuvo Parakeet
v3 como óptimo ES/EN con Nemotron-3.5 streaming como único candidato de
upgrade. El gate 7 exige además VAD y la puerta única `VoiceTranscript` (ya
construida); wake/AEC/barge-in físicos son post-1.0 salvo que el corpus los
exija.

## Rol 3 — LLM de conversación + tool-calling (gates 8, 9, 12)

Tarea: conversación general ES/EN/spanglish (gate 9), composición/planner con
política de riesgo sobre las 21 tools (gate 8), presupuesto 4 GB VRAM con
fallback CPU (gate 12).

| Candidato | Tamaño | Procedencia | Fortalezas | Debilidades |
|---|---|---|---|---|
| Gemma 4 E2B (QAT int4) | 5.1B total / 2.3B efectivos | Externa: guías 2026 (function calling nativo, audio-in nativo, 128K ctx) + **QAT GGUF en caché + evidencia interna** | Experimento interno: un solo E2B para chat+visión+STT+tools empató 28/29 y fue 2,3× más rápido que el split; function calling nativo; ~4–5 GB en int4 | Al límite del presupuesto 4 GB; licencia Gemma; sobre-activación histórica medida (mitigada con shortlist) |
| Qwen3.5-4B | 4B | Externa: release mar-2026, Apache 2.0 | Tool-calling estable (familia con mejor reputación 2026); multilingüe fuerte; thinking opcional | ~2,5–3 GB en Q4; sin evidencia interna; ES nativo bueno pero a medir en spanglish |
| Qwen3.5-0.8B / Qwen3-1.7B | 0.8–1.7B | Externa | Muy baratos; margen de VRAM enorme | Conversación general más pobre; riesgo gate 9 |
| Phi-4-mini 3.8B | 3.8B | Externa: ~2,5 GB Q4, JSON fiable | Estructurado/tool-calling predecible | ES/spanglish más débil que Qwen/Gemma; licencia MIT ok |
| SmolLM3-3B | 3B | Externa: SLM abierto top de 2026 | Totalmente abierto; 64K ctx | Multilingüe limitado (foco EN); riesgo ES |
| FunctionGemma-270M (run9-525) + encoder (split) | 270M | Interna: split validado 13/14 no-tool, 12/13 standalone | Caller CPU baratísimo tras shortlist; ya entrenado | Solo llama tools, no conversa; catálogo creció de 9→21 tools y la decisión interna fue NO retrain (crecer vía bridge); dos modelos = más costuras |
| LFM2-1.2B | 1.2B | Externa: top fine-tuning 2026 | Edge eficiente | Requiere fine-tune para brillar; base ES a verificar |

Arquitecturas candidatas (se deciden en el torneo, no antes):
- **A. Unificada:** un LLM (~2–4B int4) hace conversación + tool-calling, con
  el router de embeddings como shortlist/gate previo (fail-closed).
- **B. Split:** encoder-router → caller chico (FunctionGemma) para tools +
  LLM apartado para conversación. Más piezas, menos VRAM pico.
- La evidencia interna (experimento Gemma unificado, 28/29 y 2,3×) favorece A,
  pero A se mide contra B bajo protocolo congelado; el techo 4 GB puede
  invertir el resultado.

## Rol 4 — Visión (fuera de gates 1.0; registro para no perderlo)

Ningún gate de la mente (4/7/8/9/12) exige visión; el catálogo congelado no
tiene operación de visión. Se registra el panorama para post-1.0: MiniCPM-V 2B
(mejor OCR sub-4GB según reviews 2026), SmolVLM2-2.2B, Moondream2 1.9B,
Qwen3.5-0.8B multimodal. Evidencia interna: dos motores + honestidad (ningún
VLM afirma nombres sin corroborar OCR). **No se invierte más aquí en 1.0** —
proporcionalidad.

## Fuentes externas principales

- MTEB/embeddings: codesota.com/benchmarks/mteb, bentoml.com (open-source
  embedding models 2026), arXiv 2509.20354 (EmbeddingGemma), arXiv 2506.05176
  (Qwen3 Embedding).
- ASR: arXiv 2509.14128 (Canary-1B-v2 & Parakeet-TDT-0.6B-v3),
  northflank.com benchmarks 2026, Open ASR leaderboard vía reviews.
- SLM/tool-calling: bentoml.com SLMs 2026, presenc.ai under-3B 2026,
  datacamp.com top SLMs, mayhemcode.com 4GB VRAM guide 2026, unsloth.ai/docs
  (Gemma 4), gemma4.wiki (VRAM E2B).
- VLM: roboflow.com local VLMs, localaimaster.com vision tasks 2026.

## Qué decide esto y qué no

Este brief solo poda el espacio: define los candidatos que entran al spike
(Rol 1) y al torneo (Roles 2–3). No aprueba ningún modelo. El spike de la
Fase 2 (router embeddings vs regex contra los oráculos congelados) es la
compuerta que decide si el plan procede.
