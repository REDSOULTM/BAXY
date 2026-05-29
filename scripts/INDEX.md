# scripts/ — INDEX

Inventario de scripts del repo, categorizados por rol. Sprint R8
del [[architecture_audit_2026_05_27]] (2026-05-28). Cuenta actualizada
automáticamente por `gemma4_agent/test_scripts_inventory.py`.

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
| `mine_tool_failures.py` | Mineria forense de fallos por tool desde `traces.jsonl` (per-tool fail rate, top errores, orfanos, proxy zombies). |
| `stress_test_cuda_crash.py` | Stress test del bug CUDA #22527 (Plan A research v3). Mide crashes en N turnos diversos con/sin thinking. |

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
| `_r2_finalize_subpkg.py` | R2 finalize: convertir 36 siblings a sub-paquete `domain_tools/`. | R2 |
| `_r2_fix_subpkg_imports.py` | R2 finalize: arregla imports relativos dentro del nuevo sub-paquete. | R2 |
| `_r2_make_shims_aliased.py` | R2 finalize: shims `domain_tools_X.py` como aliases del módulo real (sys.modules). | R2 |
| `_r4_revert_aliases.py` | R4 cleanup: revierte `_ok_tr/_err_tr` aliases a `_ok/_err` directos. | R4 |
| `_r4_final_cleanup.py` | R4 cleanup: borra defs duplicadas tras el revert, limpia imports. | R4 |
| `_r3_remove_redundant_lazies.py` | R3 deep cleanup: elimina lazies que duplican imports top-level del mismo archivo. | R3 |
| `_reorg_tests_to_subpkg.py` | Reorg 2026-05-28: mueve 181 `test_*.py` a `gemma4_agent/tests/` + reescribe imports relativos. | reorg |
| `_reorg_fix_paths.py` | Reorg 2026-05-28: ajusta cadenas `Path(__file__).resolve().parent` tras mover tests al sub-directorio. | reorg |
| `_reorg_pkg_subpackage.py` | Reorg 2026-05-28: mueve N modulos a `gemma4_agent/<subpkg>/` + crea shims aliased (patron R2). | reorg |
| `_reorg_finalize_subpkg.py` | Reorg 2026-05-28: completa shims + reescribe imports para archivos ya movidos a un subpkg (recovery del move parcial). | reorg |
| `_reorg_kill_shims.py` | Reorg 2026-05-28: migra imports externos + borra shims top-level (post-validacion). | reorg |
| `_reorg_fix_relative_imports.py` | Reorg 2026-05-28: tras matar shims, ajusta `from ..X` y `from .X` y absolutos a los subpkgs reales. | reorg |
| `_reorg_fix_from_pkg_import.py` | Reorg 2026-05-28: reescribe `from gemma4_agent import X as Y` -> subpkg real. | reorg |
| `_reorg_fix_intra_subpkg.py` | Reorg 2026-05-28: convierte `from ..X` a `from .X` cuando X esta en el mismo subpkg. | reorg |
| `_reorg_migrate_python_m_docs.py` | Reorg 2026-05-28: actualiza `python -m gemma4_agent.X` -> `python -m gemma4_agent.<subpkg>.X` en docs activos (NO sprints/_archive). | reorg |
| `_reorg_create_runnable_shims.py` | Reorg 2026-05-28: crea 12 shims fisicos para los modulos runnable (`python -m gemma4_agent.X` sin RuntimeWarning, compat con Windows Scheduled Tasks). | reorg |

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
| `_diag_calc_route.py` | routing de "calculá" |
| `_diag_empty_reply.py` | reply vacío |
| `_diag_forced_retry.py` | forced-tool retry |
| `_diag_info_tool.py` | info-turn que usa tool |
| `_diag_prefix_divergence.py` | divergencia del prefix-cache |
| `_diag_dump_history.py` | dump de history interna del turno |
| `_diag_python_cancel.py` | mis-route "explicá Python" → cancelar (a11y) |

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

## Categoría L — Latencia / streaming / validación en vivo (2026-05-28/29)

Scripts de las sesiones de latencia (v22, prefill-cache, streaming) y de
adopción de competidores (B1/B2/B7). Validadores en vivo (regla #3.5) y
mediciones one-shot. Muchos requieren el LLM en `:8080`.

| script | propósito |
|---|---|
| `_validate_stream_tts.py` | Valida streaming TTS truthful (guards pass-through). |
| `_validate_stream_info.py` | Valida streaming de turnos INFO + veracidad (voiced-prefix-of-final). |
| `_validate_lean_frcot.py` | Valida lean-prompt + FR-CoT en vivo. |
| `_validate_web_fallback.py` | B7: valida fallback web DDG→Bing (regex Bing vs HTML real). |
| `_validate_b1_b2.py` | B1 (error-recovery) + B2 (memory-tools) en vivo. |
| `_validate_reminder_schedule.py` | B8: valida que reminder con hora crea un Scheduled Task real en el SO (+ cleanup). |
| `_validate_b4_b6_direct.py` | B4/B6 capacidad (sin LLM): data_analysis sobre CSV + document sobre PDF funcionan. |
| `_validate_b4_b6_live.py` | B4/B6 conexión: ¿el 4B elige data_analysis/document en vivo? (gap de routing medido). |
| `_gen_product_doc.py` | Genera el Word de producto (riesgos+mitigaciones + comparativa competencia) con python-docx. |
| `_measure_pass1.py` | Mide latencia/tokens del pass-1. |
| `_measure_thinking0.py` | Mide efecto de `thinking_budget=0`. |
| `_measure_summary_cache.py` | Mide cache-hit del summary pass (lever de −1s). |
| `_measure_crossturn_cache.py` | Mide cache cross-turn (intermitente). |
| `_measure_history_growth.py` | Mide crecimiento del historial por turno. |
| `_measure_agent_prompt_live.py` | Mide el prompt real del agente en vivo. |
| `_measure_full_request.py` | Mide el request completo a llama-server. |
| `_measure_prompt_size.py` | Mide tamaño del system prompt. |
| `_measure_tool_schemas.py` | Mide tamaño de los schemas de tools. |
| `_verify_cache_hit.py` | Verifica el cache-hit (`cache_n`) del prefix. |
| `_verify_frcot.py` | Verifica FR-CoT (thinking estructurado). |
| `_verify_a2_quality.py` | Verifica calidad tras Plan A2 (system prompt 9.4k→5k). |
| `_verify_v22_defaults.py` | Verifica los defaults del bundle v22 (FA-off, lean). |
| `_audit_prompt_tokens.py` | Audita el desglose de tokens del prompt. |
| `_soak50.py` | Soak test 50 turnos (crash-safety del cache-hit). |
| `_stress_v22.py` | Stress test del bundle v22. |
| `_revert_live_probe.py` | Revierte un probe en vivo (cleanup). |
| `_kill_eval_boot_procs.py` | Mata los procesos del boot de eval. |
| `_kill_server_ports.py` | Libera los puertos del server (`:8080`). |
| `_reset_server.py` | Reinicia el llama-server gestionado. |

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
