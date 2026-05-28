# scripts/ — INDEX

Inventario de los 76 scripts del repo, categorizados por rol. Sprint R8
del [[architecture_audit_2026_05_27]] (2026-05-28).

## Convención de prefijos

- `_<area>_<verb>.py` — internal helper / one-shot reproducible
  (`_arch_*`, `_code_smell_*`, `_r1_*`/`_r2_*`/`_r3_*` para los sprints
  de refactor)
- `_diag_*.py` — diagnoses ad-hoc por sesión (vivieron afuera; se mueven a `_diag/`)
- `_exhaustive_*.py` — harnesses de medición exhaustivos (escenarios x N)
- `_marathon_*.py` — corridas largas de evaluación
- `_measure_*.py` — mediciones one-shot
- `train_*.py` — entrenamiento de modelos custom
- `wake_universal_*.py` — pipeline universal de wake-word
- `router_*.py` — pipeline del router semántico
- `stt_*.py` — evals de STT
- `eval_*.py` / `*_eval.py` — evaluadores oficiales (gates)
- `setup_*.py` / `download_*.py` — bootstrap

## Categoría A — Evaluadores oficiales (correr antes/después de cambios grandes)

| script | propósito |
|---|---|
| `battery_all_caps.py` | **Bateria integral 60×25 categorías**. Gate principal del repo. **Requiere LLM en :8080**. |
| `smoke_e2e.py` | Smoke E2E rápido (32 casos). Verifica router + agent + tools. |
| `wake_universal_eval_livekit.py` | Gate wake universal (recall ≥ 0.60, fp/hr ≤ 1.0 sobre held-out). |
| `accessibility_eval.py` | Eval de modos de accesibilidad (movilidad/no-vidente). |
| `computer_use_live_eval.py` | Eval de computer_use contra agente real. |
| `computer_use_mission_eval.py` | Eval por-misión (110 misiones del Tier-eval). |
| `computer_use_tier_eval.py` | Eval por-tier estructural. |
| `eval_profile_actions.py` | Eval acciones por VRAM-profile. |
| `router_canary_eval.py` | Canary del router (subset de oro). |
| `router_eval.py` | Eval completo del router (split train/dev/test). |
| `voice_pipeline_e2e_test.py` | E2E voz: wake → STT → agent → TTS. |
| `validate_profiles.py` | Sanity check de los perfiles VRAM. |

## Categoría B — Pipelines de generación / entrenamiento

| script | propósito |
|---|---|
| `router_corpus_build.py` | Construye corpus del router desde traces. |
| `router_corpus_curate.py` | Curado humano (interactivo) del corpus. |
| `router_corpus_labels.py` | Asigna labels a casos del corpus. |
| `router_exemplar_build.py` | Construye exemplars para semántico. |
| `router_ft_pipeline.py` | Fine-tuning del encoder del router. |
| `router_tool2vec_build.py` | Construye centroides tool2vec. |
| `router_tool2vec_generate.py` | Genera embeddings tool2vec. |
| `train_abstain_head.py` | Entrena la cabeza de abstención. |
| `train_hey_gemma_v8.py` | Entrenamiento wake v8 (legacy). |
| `train_hey_gemma_v9.py` | Entrenamiento wake v9 (legacy, hoy se usa LiveKit). |
| `train_router_encoder.py` | Entrena el encoder del router. |
| `train_tool_head.py` | Entrena la cabeza per-tool. |
| `wake_universal_download_negatives.py` | Baja negativos para wake. |
| `wake_universal_download_voices.py` | Baja voces sintéticas. |
| `wake_universal_generate_positives.py` | Genera positivos sintéticos. |
| `wake_universal_voices.py` | Lista las voces disponibles. |
| `download_fleurs_es.py` | Descarga FLEURS-es para STT eval. |

## Categoría C — STT específico

| script | propósito |
|---|---|
| `stt_decode_sweep.py` | Sweep de parámetros de decode. |
| `stt_eval_commands.py` | Eval STT sobre comandos curados. |
| `stt_noise_robustness.py` | STT bajo ruido. |
| `stt_prompt_calibration.py` | Calibra `initial_prompt` por idioma. |
| `stt_real_voice_eval.py` | Eval STT con voz real grabada. |
| `stt_synthetic_eval.py` | Eval STT sintético (TTS → STT). |
| `spike_sherpa_parakeet.py` | Spike de Parakeet/sherpa-onnx. |
| `probar_parakeet_mic.py` | Probador interactivo de Parakeet con mic. |

## Categoría D — Wake universal

| script | propósito |
|---|---|
| `wake_universal_eval.py` | Eval wake (versión clásica). |
| `wake_universal_eval_livekit.py` | Eval wake (versión LiveKit ONNX, oficial). |

## Categoría E — Bootstrap / setup

| script | propósito |
|---|---|
| `setup_cuda_runtime.py` | Instala CUDA runtime. |
| `_boot_server_for_eval.py` | Arranca llama-server para tests. |
| `measure_vram_profiles.py` | Mide VRAM real por perfil. |
| `vram_calculator.py` | Calculadora de VRAM (paper Q×n_ctx). |
| `_ort_throttle.py` | Helper ONNX Runtime throttling (anti-freeze). |

## Categoría F — Análisis arquitectural / refactor sprints

| script | propósito | sprint |
|---|---|---|
| `_arch_dep_graph.py` | Detector de ciclos + import inventory. | audit base |
| `_code_smell_inventory.py` | Inventory de try/except/pass, prints, eval/exec. | audit base |
| `_r1_extract_decide.py` | R1.1: extrae `_decide_turn`. | R1 |
| `_r1_extract_execute.py` | R1.2: extrae `_execute_turn`. | R1 |
| `_r1_extract_finalize.py` | R1.3: extrae `_finalize_turn`. | R1 |
| `_r2_replace_block.py` | R2: reemplazo de bloque por línea (mecánico). | R2 |
| `_r2_restore_head.py` | R2: restaura archivos a HEAD via `git show` (workaround harness). | R2 |
| `_r3_rewrite_imports.py` | R3: reescribe lazy → top-level imports. | R3 |
| `_r3_resolve_stranded.py` | R3: limpia merge-stage huérfanos via `update-index`. | R3 |
| `_r4_migrate_batch.py` | R4: migración batch _ok/_err → ToolResult con .to_dict(). | R4 |

## Categoría G — Diagnoses ad-hoc (movibles a `_diag/`)

Estos scripts fueron creados para una sesión específica de diagnóstico y NO
son parte del pipeline regular. Se mueven a `scripts/_diag/` (ver sección
de migración).

| script | sesión origen |
|---|---|
| `_diag_chain_unab_canvas.py` | UNIEJ Canvas chain |
| `_diag_portal_unab.py` | Portal UNIEJ |
| `_diag_quien_eres.py` | "¿quién eres?" routing |
| `_diag_unab_canvas_goal.py` | UNIEJ Canvas goal-mission |

## Categoría H — Harnesses exhaustivos (one-shot)

| script | propósito |
|---|---|
| `_exhaustive_click_test.py` | Cascada click 40+ variantes. |
| `_exhaustive_discord_test.py` | Discord caliente vs frío 10×. |
| `_exhaustive_gui_test.py` | Click_button calc 40-clicks 10/10. |
| `_exhaustive_llm_test.py` | LLM E2E 9 escenarios. |

## Categoría I — Marathons

| script | propósito |
|---|---|
| `_marathon_cu_e2e.py` | Marathon computer-use E2E (multi-misión). |
| `_marathon_llm_plans.py` | Marathon LLM emitiendo planes. |
| `_marathon_p3_stress.py` | Marathon p3 stress (alta concurrencia). |

## Categoría J — Mediciones one-shot

| script | propósito |
|---|---|
| `_measure_4b_composes.py` | Mide si el 4B encadena 2-pasos solo. |
| `_measure_4b_plan_emission.py` | Mide tasa de emisión de plan. |
| `_measure_cu_optionA.py` | Mide opción A de computer_use. |
| `_measure_cu_optionB.py` | Mide opción B de computer_use. |
| `_measure_cu_wired_e2e.py` | Mide CU wired E2E. |
| `_measure_e4b_q3_vram.py` | **OBSOLETO** — el perfil `e4b_q3` ya no existe. |
| `_measure_iq3_toolcall.py` | Mide IQ3 tool-call rate. |

## Categoría K — Operativos / utilidades

| script | propósito |
|---|---|
| `analyze_traces.py` | Parser de trace.jsonl. |
| `trace_audit.py` | Auditor de traces (detecta silent fallback). |
| `bench_model_speed.py` | Bench velocidad por modelo. |
| `guided_commands_set2.py` | Set-2 comandos guiados. |
| `router_diag.py` | Diagnostic del router (output verbose). |
| `watch.py` | Watch de cambios + auto-reload. |

## Cosas pendientes (futuras sesiones)

- **Mover** `_diag_*.py` → `scripts/_diag/` cuando se confirme que ningún
  test los importa por path (verificado a este día: 0 imports).
- **Borrar** `_measure_e4b_q3_vram.py` — el perfil murió.
- **Auditar** scripts en categorías H, I, J para identificar cuáles vivieron
  pasaron a producción y cuáles son chatarra de sesión.

---

**Generado**: 2026-05-28 sprint R8.
**Próximas re-corridas**: cuando aparezcan ≥10 scripts nuevos sin
categorizar, regenerar este índice manualmente.
