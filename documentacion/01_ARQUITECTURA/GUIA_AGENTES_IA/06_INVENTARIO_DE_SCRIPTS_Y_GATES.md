# Inventario de scripts y gates

Este índice evita ejecutar un script por su nombre sin comprender qué lee,
qué escribe o qué efecto puede producir. El código del script y su `--help` o
`param(...)` siguen siendo la fuente exacta de argumentos.

## Leyenda

| Clase | Significado |
|---|---|
| Biblioteca | se importa/dot-source; no se invoca como tarea |
| Validación | no pretende cambiar producto ni mundo externo |
| Output | escribe build, reporte, corpus, cache o evidencia |
| Runtime | instala dependencias/assets o reemplaza un manifest local |
| Privado | lee o reconstruye corpus/sesiones que no deben publicarse |
| Físico | abre o modifica apps, audio, hardware, cuentas o sistema |
| Instalación | muta versiones instaladas o datos del producto |
| Sellado | consume una reserva/estado de evaluación con reglas especiales |

“Validación” puede crear temporales seguros y caches controlados. “Output” no
autoriza a sobrescribir evidencia existente. “Físico” e “Instalación”
requieren target y autorización explícitos.

## Desarrollo, build y librerías

| Archivo | Clase | Función y cautela |
|---|---|---|
| `__init__.py` | Biblioteca | expone scripts Python a tests focalizados |
| `build_layout.py` | Biblioteca/validación | interpreta el contrato MSBuild y calcula outputs seguros |
| `build_layout.ps1` | Biblioteca/validación | equivalente PowerShell del layout |
| `path_safety.ps1` | Biblioteca | descendencia estricta, reparse y limpieza acotada |
| `product_build_common.ps1` | Biblioteca | payload cerrado, JSON canónico, hashes, ZIP y snapshot Git |
| `python_runtime_common.ps1` | Biblioteca | resuelve Python/manifest, invoca y valida locks |
| `baxy_runtime_config.py` | Biblioteca/validación | resolución fail-closed del runtime mind registrado |
| `asset_resolver.ps1` | Biblioteca/validación | interpreta `assets.manifest.json` y el override local sin descargar assets |
| `mind_runtime_manifest.ps1` | Biblioteca/validación | calcula y vuelve a comprobar los SHA-256 del registro mind |
| `run_baxy.ps1` | Runtime de desarrollo | lanza App/Core y configura Mind; normalmente se llama desde `main.py` |
| `test_source_quality.ps1` | Validación | compuerta Fast/Full; no instala ni regenera `dist` |

Entrada normal:

```powershell
py main.py
```

No invoques helpers dot-sourced como si fueran scripts autónomos.

## Dependencias y runtime mind

| Archivo | Clase | Función y cautela |
|---|---|---|
| `lock_python_dependencies.ps1` | Output | `-Check` resuelve y compara; sin `-Check` reemplaza solo el `pylock.*` usando requirements + constraints como inputs |
| `verify_python_runtime_lock.py` | Validación | valida lock, constraints y entorno activo |
| `bootstrap.ps1` | Runtime/validación | `-CheckOnly` diagnostica; sin él crea el venv externo y registra assets existentes, sin descargar modelos |
| `setup_mind_voice.ps1` | Runtime | instala el grafo runtime aprobado en un Python explícito |
| `register_mind_runtime.ps1` | Runtime | valida y reemplaza `mind-runtime-v1.json` |
| `install_nemotron_streaming_stt.ps1` | Runtime | instala bundle STT opcional y recibo bajo assets externos |
| `install_baxy_wake_model.ps1` | Runtime | instala solo un KWS con reporte calibrado promocionable |
| `restore_agent_assets.ps1` | Runtime/privado | restaura corpus/muestra exactos por hash; no publica |
| `baxy-wakeword-production.yaml` | Configuración | training KWS aislado; no ejecutar en el runtime ni GPU no apta |

Revisar un lock:

```powershell
.\scripts\lock_python_dependencies.ps1 -Profile Runtime -Check
.\scripts\lock_python_dependencies.ps1 -Profile Test -Check
```

Registrar o instalar cambia estado bajo `%LOCALAPPDATA%\BAXYRuntime` o en una
ubicación declarada por `assets.manifest.json`; no es parte de una validación
de source.

## Entrega y ciclo instalado

| Archivo | Clase | Función y cautela |
|---|---|---|
| `build_product.ps1` | Output | build determinista/A-B dentro del entorno declarado desde HEAD limpio; reemplaza output permitido |
| `package_product.ps1` | Output | ZIP determinista + digest; reemplaza output permitido |
| `build_setup.ps1` | Output | verifica/embebe paquete; output debe ser nuevo |
| `capture_product.ps1` | Output/físico | abre el producto y captura evidencia visual; revisar target |
| `test_app_open.ps1` | Físico/output | prueba apertura real y preservación de procesos |
| `test_gpu_status.ps1` | Output/hardware read-only | build/gate NativeAOT sobre GPU local |
| `attest_in_place_upgrade.ps1` | Instalación/output | upgrade, recovery, rollback y reactivación same-host |
| `test_gate14_clean_environment.ps1` | Instalación/output | instalación inicial/upgrade/uninstall/purge en cuenta o VM desechable |

El pipeline detallado está en
[02_CONSTRUCCION_EJECUCION_Y_ENTREGA.md](02_CONSTRUCCION_EJECUCION_Y_ENTREGA.md).
No ejecutes los dos últimos sobre el perfil cotidiano.

## Gates de runtime y producto

| Archivo | Clase | Función y cautela |
|---|---|---|
| `measure_mind_budget.py` | Output/GPU/alto costo | levanta sidecar GPU y CPU y mide recursos/latencia |
| `detect_promotion_boundary_decisions.py` | Output/E5/sin modelo | recorre el corpus bajo el régimen léxico y el semántico y reporta qué turnos pueden cambiar de decisión por readiness; no invoca al LLM ni despacha operaciones |
| `detect_social_envelope_equivalence.py` | Output/sin modelo/sin efectos | oráculo de envoltura social: cruza los 64 casos congelados de `tests/test_effect_intent.py` con 13 envolturas y compara la forma envuelta contra la desnuda en los dos brazos del reconocedor. Distingue tres fallos —petición escondida, operación degradada y autoridad inventada— y sólo aprueba si no hay regresiones contra el reconocedor anterior. Segundos, sin GPU. Úsalo, y no la igualdad exacta contra P, para gatear cualquier ampliación del reconocedor determinista |
| `run_mind_shell_e2e_gate.ps1` | Output/modelo | recorridos shell→mind→core read-only |
| `run_planner_corpus_gate.py` | Output/modelo | evalúa planes sin grounding, core ni efectos |
| `run_user_behavior_gate.py` | Output/modelo | lenguaje visible de conversación/narración |
| `test_mind_router_oracles.py` | Validación/modelo | router productivo contra oráculos congelados |
| `test_mind_voice.py` | Output/audio sintético | SAPI→ASR headless; no usa voz humana |
| `run_voice_system_gate.py` | Físico/output | abre mic/loopback; `--physical-output` habla y cancela SAPI |
| `run_external_adapter_gate.py` | Físico/output | adapters reales; deja DOCX en `Documentos\BAXY` y puede conservar estado de apps/browser/media: no es totalmente autorrestaurable |
| `run_hardware_effect_gate.py` | Físico/output | hardware/impresión/red/settings solo con targets descubiertos |
| `run_bluetooth_radio_roundtrip_gate.py` | Físico/output | cambia radio Bluetooth y restaura baseline exacto |
| `run_llm_plan_execution_gate.py` | Físico/output/modelo | cruza `turn.decide -> plan -> Core -> provider -> postlectura` con runtime registrado; revisa cada misión. Una precondición ambiental exacta puede quedar `environment_blocked` sólo con `effectMayHaveOccurred=false`, nunca contada como pass |
| `run_steam_launch_gate.py` | Físico/output | lanza un juego instalado exacto y cierra solo su proceso nuevo |
| `measure_app_visible_path.ps1` | Físico/GPU/alto costo | mide el camino visible tecla→pintado con brazos frío y caliente en orden ABBA. **Toma el escritorio**: lanza BAXY real, la trae al frente y escribe en su campo por UI Automation durante ~30 min. Sólo pregunta cosas de conversación y de estado; ningún escenario ejecuta un efecto externo. Escribe trazas crudas y un índice en `artifacts/fixes/app_visible_path_v3/` |
| `summarize_app_visible_path.py` | Sin modelo/sin efectos | convierte ese índice en el artefacto por etapa con valores individuales y dispersión; no lanza nada |

Aunque un gate describa operaciones “read-only”, puede levantar procesos
pesados, abrir ventanas o escribir evidencia. Lee el archivo y el catálogo de
casos antes.

## Corpus histórico y ledger

| Archivo | Clase | Función y cautela |
|---|---|---|
| `freeze_historical_sources.py` | Output/privado | fija frontera de fuentes por commit/hash sin copiar contenido |
| `build_historical_corpus.py` | Output/privado | extrae corpus trazable de mensajes y procedencia |
| `build_exhaustive_message_ledger.py` | Output/privado/alto costo | inventario completo de ocurrencias históricas |
| `build_exhaustive_runtime_oracle.py` | Output/privado | oráculo independiente de resultados esperados |
| `build_exhaustive_runtime_language_scope.py` | Output/privado | separa scope ES/EN/spanglish |
| `build_historical_runtime_hints.py` | Output/privado | hints sin texto ni autoridad desde el oráculo |
| `audit_all_historical_missions.py` | Output/privado | contabiliza misiones sin tratar ruido como producto |
| `audit_planner_corpus.py` | Output/privado | auditoría honesta de misiones compuestas |
| `build_turn_training_corpus.py` | Output/privado | exporta evidencia para training/evaluación offline |
| `run_exhaustive_runtime_model_gate.py` | Output/privado/modelo/alto costo | replay secuencial de casos exactos por sidecar |
| `run_exhaustive_runtime_model_gate_parallel.py` | Output/privado/modelo/alto costo | runner batched con servidor persistente |
| `run_exhaustive_runtime_model_gate_resilient.py` | Output/privado/modelo/alto costo | resume shards tras crash sin omitir filas |
| `merge_exhaustive_runtime_model_gate.py` | Output | fusiona shards disjuntos y verifica ledger |

Los JSONL exhaustivos pueden superar 1 GiB y están ignorados. No los imprimas
ni añadas a Git. Un runner paralelo sigue sin conceder autoridad al corpus.

## Evidencia pública, policies y sellos

| Archivo | Clase | Función y cautela |
|---|---|---|
| `build_presto_turn_evidence.py` | Output | promueve PRESTO/MASSIVE desde archives oficiales verificados |
| `build_public_turn_evidence.py` | Output | entrypoint compatible del builder público |
| `build_mtop_turn_evidence.py` | Output/sellado | development EN/ES separado del hash de test oficial |
| `prepare_turn_policy_runtime_development.py` | Output | prepara train/validation solo desde split train |
| `measure_turn_policy_v5_validation_cascade.py` | Output/modelo | diagnóstico de desarrollo, no gate de release |
| `measure_turn_policy_v52_mtop_validation.py` | Output/modelo | cascada MTOP solo validation |
| `audit_turn_policy_v51_failures.py` | Output | audita fallos seleccionados de un reporte text-free |
| `train_turn_policy_e5_development.py` | Output/training | candidato fuera de runtime, solo train/validation |
| `verify_turn_policy_e5_selective_gate.py` | Validación | verifica cadena agregada ya producida; no entrena/promueve |
| `run_turn_evidence_encoder_gate.py` | Output/modelo | cache E5 aislado, reload y retrieval; sin Core |
| `run_turn_linear_probe_gate.py` | Output/sellado | validation congela; final puntúa una sola vez |
| `run_turn_policy_gate.py` | Output/modelo | A/B LLM reproducible de policy unilateral |
| `seal_turn_evidence_final_subset.py` | Sellado/output | sella IDs sin leer labels/scores |
| `blind_reset_turn_evidence_final_seal.py` | Sellado/output | reset v2 tras contaminación declarada |
| `blind_reset_turn_evidence_final_seal_v3.py` | Sellado/output | reset v3 tras fallo técnico documentado |
| `blind_reset_turn_evidence_final_seal_v4.py` | Sellado/output | reset v4 desde reserva intacta |

Los scripts `blind_reset_*` no son un botón para repetir hasta pasar. Solo se
usan bajo el protocolo de ceguera y contaminación que documentan. Abrir un
holdout o reparar guards después de observar resultados invalida el claim.

## Wake y audio

| Archivo | Clase | Función y cautela |
|---|---|---|
| `evaluate_wake_corpus.py` | Output/audio privado | calcula FAR/FRR sin persistir audio, nombres ni texto |
| `run_wakeword_physical_room_gate.py` | Físico/output | reproduce un corpus por altavoz y evalúa solo la captura de micrófono; requiere `--physical-output` y no conserva audio |
| `baxy-wakeword-production.yaml` | Configuración/training | entorno CUDA aislado y dependencias de training |
| `install_baxy_wake_model.ps1` | Runtime | exige modelo y calibration report ligados por hash |
| `test_mind_voice.py` | Output | gate sintético/headless |
| `run_voice_system_gate.py` | Físico/output | gate integral del host |

Una evaluación promocionable exige corpus y límites estadísticos declarados.
Una muestra positiva corta no acredita FAR por hora.

## Archivo de sesiones de agentes

| Archivo | Clase | Función y cautela |
|---|---|---|
| `export_codex_subagents.py` | Output/privado | exporta índice sanitizado y segmentos privados |

`--force` reemplaza el export privado anterior y reescribe metadata del host.
No lo ejecutes durante onboarding ni lo uses para inferir agentes actuales.
Consulta `documentacion/agentes/README.md`.

## Cómo decidir si ejecutar un script

Antes:

1. abre docstring/`param`;
2. ejecuta `--help` solo si el script lo soporta sin side effects;
3. resuelve inputs y outputs absolutos;
4. comprueba si el output ya existe;
5. busca su prueba: `grep` de `nombre_script` acotado a `tests`;
6. identifica secrets/corpus/targets;
7. clasifica el efecto con la leyenda;
8. pide autoridad si cruza runtime, físico o instalación.

Después:

1. comprueba exit code;
2. valida schema/hashes del output;
3. revisa `git status`;
4. no mezcles evidencia con source sin intención;
5. reporta qué observó el gate y qué no acredita.
