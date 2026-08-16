# Auditoría del pipeline FT v3 contra fuentes — 2026-06-11 (pre-entrenamiento)

Fase 1 del cierre del fine-tuning v3 (ver `_HANDOFF_FINETUNE_V3_2026-06-11.md`).
Cada afirmación del pipeline se contrastó contra documentación oficial, el
modelo local REAL, o medición directa. Convención: **CONFIRMADO** (la fuente o
la medición lo respalda), **CORREGIDO** (contradecía la evidencia; se arregló
antes de entrenar), **REFUTADO** (la afirmación era falsa; se documenta).

## Tabla afirmación → fuente → veredicto

| # | Afirmación del pipeline | Fuente / medición | Veredicto |
|---|---|---|---|
| 1a | Tokens: `<\|tool_response>`=50, `<tool_response\|>`=51, `<turn\|>`=106, eos=1, bos=2 | `tokenizer.json` del modelo local (medido con `_audit_token_ids.py`); coincide con [function-calling-gemma4](https://ai.google.dev/gemma/docs/capabilities/text/function-calling-gemma4) | CONFIRMADO |
| 1b | `generation_config.eos_token_id=[1,106,50]` — "token 50 sin identificar" (memoria) | Medido: 50 = `<\|tool_response>` → el server PARA cuando el modelo abriría un tool_response (coherente con el jinja, que tras tool_call sin response emite `<\|tool_response>`) | RESUELTO (actualiza la memoria) |
| 1c | El GGUF de prod embebe el mismo chat_template que el jinja del training | Medido (`_audit_gguf_template.py`): IDÉNTICOS char a char (17.336) | CONFIRMADO |
| 1d | **"Render de build_messages_v3 bit-idéntico al re-feed de prod"** | Medido contra el motor REAL (llama-server `--jinja`, endpoint `/apply-template`, CPU): los `arguments` como string JSON renderizaban `call:audio{{"action": "set_volume"}}` mientras prod renderiza el formato NATIVO `call:audio{action:<\|"\|>set_volume<\|"\|>,level:20}` (llama.cpp parsea el string OpenAI a objeto; jinja2 local no) | **CORREGIDO**: `arguments` como dict en `build_messages_v3`/`build_messages`/G6/test → re-medido **5/5 filas bit-idénticas** (single, multi-tool secuencial, history, ok:false, no-tool). Deltas esperados: `<bos>` (token, no texto; un solo BOS verificado en ambos caminos) y `<turn\|>` final (training lo cierra para enseñar el stop; en prod es generación) |
| 1e | Formato nativo de args/response con `<\|"\|>` y keys sin comillas | [function-calling-gemma4](https://ai.google.dev/gemma/docs/capabilities/text/function-calling-gemma4) + render real del server | CONFIRMADO (el fix 1d alinea el training con esto) |
| 1f | Prod re-alimenta `role:"tool"` + `tool_call_id` + JSON compactado | `agent.py:4501-4505` + `agent_compaction.py:221` (results chicos pasan sin tocar) | CONFIRMADO |
| 1g | El re-feed secuencial (call→response→call→response) en UN turno model | jinja líneas 220-235 (`continue_same_model_turn`) + render del server (fila multi-tool bit-idéntica) | CONFIRMADO |
| 2a | Máscara spans [50..51] inclusive, tool_call y reply CON loss | `_test_mask_v3.py` PASS (sintético multi-bloque + fila real); test revisado línea a línea; composición con `train_on_responses_only` correcta (wrapper sobre el collator ya parcheado) | CONFIRMADO |
| 2b | Enmascarar el tool_response es necesario (sin máscara se enseña a alucinar results) | Consistente con el diseño: en deploy esos tokens son SIEMPRE prefill del runtime; `train_on_responses_only` solo deja loss desde `<\|turn>model` y el result vive DENTRO de ese turno | CONFIRMADO (estructural) |
| 3a | r=16, α=32, lr=2e-4, QLoRA 4-bit, adamw_8bit, cosine | [Guía oficial Unsloth Gemma 4](https://unsloth.ai/docs/models/gemma-4/train): r 8-32, α ≥ r, lr 2e-4, adamw_8bit, linear/cosine, QLoRA E2B ~8GB (smoke previo midió 8,4GB) | CONFIRMADO |
| 3b | dropout=0.05 y weight_decay=0.01 | Unsloth sugiere dropout 0 y wd 0.001 — divergencia menor; dropout>0 es regularización extra (consistente con el historial de sobreajuste del E2B) | DIVERGENCIA MENOR (documentada, no bloqueante) |
| 3c | **"3 epochs sobreajusta el E2B (medido rollback v1)"** (handoff/doc v3) | La propia memoria del proyecto ([rollback v1, round 6](project_refinetuning_v1_rollback_2026_06_05)): con el pipeline ARREGLADO el barrido 2/3/4ep lo ganó **3ep** (routing 4/4 vs 1/4 de 2ep; hash c68688 = el modelo EN PROD hoy). El fallo v1 con 3ep estaba CONFUNDIDO por el merge corrupto + sample_weight | **REFUTADO** como regla general. Decisión para v3: entrenar 2ep (plan de registro; el dataset v3 difiere y no hay medición propia) con CONTINGENCIA: si el gate de routing falla, variante 3ep y comparar — el FAIL sería la evidencia nueva que pide el handoff |
| 4 | Fix 2 de Unsloth (use_cache=False + KV-sharing → basura; E2B num_kv_shared=20) vigente | Verificado EN EL PAQUETE INSTALADO: `.venv_ft/.../unsloth_zoo/temporary_patches/gemma4.py` (unsloth 2026.5.10 / zoo 2026.5.5), "Gemma-4 E2B: num_kv_shared_layers=20 → Fix 2 engages"; mismo venv que produjo el modelo de prod actual. La [guía Unsloth](https://unsloth.ai/docs/models/gemma-4/train) advierte el mismo bug | CONFIRMADO |
| 5a | Merge: recarga Unsloth-bf16 + `merge_and_unload()` + save HF (nunca `save_pretrained_merged`) | Empírico (round 5/6: este camino produjo el modelo de prod que funciona). El bug real de `save_pretrained_merged` es [#5386](https://github.com/unslothai/unsloth/issues/5386) (reescribe eos `<turn\|>`→`<eos>`, rompe el stop) — nuestro camino no lo toca. Se agrega verificación post-merge del eos en F2 | CONFIRMADO |
| 5b | GGUF: convert `--outtype bf16` → imatrix → Q4_K_M, converter 5757c4dcb (=build 9090 prod) | `quantize_gguf.py` consistente; el GGUF de prod salió de este mismo camino y opera en vivo | CONFIRMADO |
| 5c | Issues NUEVOS llama.cpp (jun 2026) | [PSA 131k metadata](https://github.com/ggml-org/llama.cpp/discussions/24198): solo 12B, N/A. [unused49](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/discussions/2): quants UD del 26B, N/A. [MTP perf #24266](https://github.com/ggml-org/llama.cpp/issues/24266): builds nuevos, prod fijo en b9090, N/A. **[PLE #22243](https://github.com/ggml-org/llama.cpp/issues/22243) ABIERTO**: llama.cpp no inyecta las Per-Layer Embeddings de E2B/E4B en el grafo → degradación sutil de calidad. Medido local: nuestro GGUF SÍ conserva los 3 tensores per_layer (Q6_K/BF16/F32) — afecta IGUAL a baseline y candidato (mismo converter+server) → no bloquea el FT; techo de calidad del producto a re-evaluar cuando llama.cpp lo implemente | CONFIRMADO (con limitación conocida documentada) |
| 6a | validate_v3.py todos los gates PASS | Medido 2 veces (antes y después de los fixes): **24/24 PASS** (eran 19; +5 nuevos G15-G19) sobre 6.877 filas | CONFIRMADO |
| 6b | "Verificación semántica muestral" (etapa 3 APIGen [arXiv:2406.18518](https://arxiv.org/abs/2406.18518)) | 36 filas estratificadas juzgadas a mano (13 familias): ~28 coherentes; **5 clases de incoherencia halladas y medidas sobre el dataset completo** (ver abajo) | **CORREGIDO** |

## Clases de incoherencia halladas (ronda 3 de auditoría semántica) y su cierre

| Clase | Tamaño medido | Fix en build_v3.py | Gate nuevo |
|---|---|---|---|
| A: intent pausa/stop/next/prev → `media(play)` con query basura (el bug vivo de 2026-06-10 invertido) | 55 matches (≈42 reales tras depurar FPs del contador) | `_guess_media_action()` multi-idioma (gana al default y a hints legados "play"; respeta hints transport explícitos) + 5 familias de frases ×6 idiomas | G16 |
| B: intent captura → `gui(click)` ("pantallazo" no matcheaba la detección vieja) | 35 filas de intent (las rotas tenían action=click) | regex ampliada (pantallazo/capture/bildschirmfoto/schermata/print screen) | G19 |
| C: "abrí Steam" → `steam(search_store)` con el TEXTO del reply como `results[].name` | 86 | branch propio de steam: open/library/store/store_page/search_store por intent, `query` (param real del handler, tools.py:1881-1893), payload action-shaped, nunca reply-en-name | G17 |
| D: en multi-tool, el result del paso 1 narraba el desenlace de TODO el turno ("Found the number AND SENT IT") — fabricación con forma de evidencia | 53 | familia de contenido: payload genérico en filas multi-tool (la red de seguridad G1 sigue siendo note en el ÚLTIMO result, by-design) | G18 |
| E: web/knowledge(search) con reply "Listo."/"Done." — enseña a IGNORAR resultados (el bug "buscaba pero no respondía" de 2026-06-08) | 31 | DROP (criterio LIMA, mismo precedente que pregunta+ack) | G15 |

Dataset final: **6.877 filas** (antes 6.907: −31 drop search+ack, ±re-síntesis),
es efectivo 56,7% (rango 52-62 ✓), attempted 35 (≥30 ✓), ok:false 45 (≥30 ✓),
multi-turno 66 (≥50 ✓), top reply "Listo." ×43 (≤80 ✓). Máscara re-PASS.
Residual conocido: 1 FP del contador propio ("ponme algo para ver" = play
correcto; "para ver" es preposición, no verbo parar).

## Hallazgo central de la auditoría (el que justificó hacerla)

El claim "bit-idéntico al re-feed" de v3 era **auto-referencial** (jinja2 vs
jinja2). Al comparar contra el MOTOR REAL de prod (minja, `/apply-template`),
los tool_call de training salían en formato JSON-crudo mientras prod ve/espera
el formato nativo de Gemma 4. Entrenar así habría enseñado al modelo a EMITIR
args que el parser nativo de llama.cpp no espera — candidato fuerte a causa de
fondo de los args degenerados a `_raw` (familia bug #1756) que la iteración 3
atribuyó solo a los args vacíos. v1/v2 entrenaron con este mismo defecto.

## Lo que sé con evidencia vs lo que asumo

**Con evidencia (medido en esta sesión):** todo lo de la tabla con "Medido";
en particular el render 5/5 bit-idéntico, los 24 gates, la máscara, los token
IDs, el template embebido idéntico, el Fix 2 presente en el venv real.

**Asumo (sin medición propia, declarado):**
- Que 2 epochs alcanzan para v3 (el barrido round-6 favoreció 3ep en OTRO
  dataset; contingencia definida).
- Que el residual de calidad por PLE no cambia el A/B candidato-vs-baseline
  (mismo runtime para ambos; estructuralmente cierto, no medido).
- Que la muestra de 36 filas es representativa (estratificada por las 13
  familias estructurales; clases halladas medidas luego sobre el 100%).

## Veredicto Fase 1

**Sin rojos abiertos.** El único rojo (formato de args) fue corregido y
re-verificado contra el motor real antes de entrenar. Pipeline habilitado
para Fase 2 (smoke → full → GGUF → 6 gates de aceptación → en vivo).
