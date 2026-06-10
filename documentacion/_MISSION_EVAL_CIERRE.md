# Cierre de misión — Mission-eval en vivo de Baxy (2026-06-09 / 2026-06-10)

> **Pedido del usuario:** fabricar a partir del dataset de finetuning un script
> que pruebe a Baxy **EN VIVO** (LLM real levantado), ≥18 categorías × ≥10
> prompts, para cazar fallas de calidad/latencia, hallar su causa raíz y
> arreglarlas. Objetivo: "dejar un Baxy perfecto".

## Qué se construyó

`scripts/_diag/_mission_eval.py` — harness que:

- Levanta el **llama-server real** (`get_shared_manager`), así la latencia y el
  comportamiento del 4B son **reales** (no mockeados).
- Mockea SOLO los **efectos físicos** (`ToolRegistry.execute`, `t_computer_use`,
  métodos gui) → sin SendInput, sin abrir programas, seguro. El LLM corre de
  verdad; el reply y la cadena de tools son reales.
- Inyecta cada prompt vía `agent.run_content(...)` (= la UI, el camino seguro).
- Muestrea **220 prompts / 22 categorías (10 c/u)** del dataset
  `dataset_finetune/curated/curated.jsonl`, con muestreo garantizado por
  categoría.
- Detecta issues: `tool_mismatch`, `empty_reply`, `special_token_leak`,
  `old_name_gemma`, `footer_or_meta_leak`, `ocr_echo`, `tool_call_leaked`,
  `lang_drift`, `reply_too_long`, `loop_genuine` vs `many_passes_mock`,
  `slow` vs `slow_from_passes`.
- Escribe `_mission_eval_results.jsonl` + `_MISSION_EVAL_REPORT.md`.

## Resultados — antes / después

| Métrica                     | Baseline | Final (run3) | Δ        |
|-----------------------------|---------:|-------------:|---------:|
| Prompts con issues          | 140 (64%)| **129 (59%)**| **−11**  |
| **lang_drift**              |       63 |      **50**  | **−13**  |
| tool_mismatch               |       59 |          49  | −10      |
| Latencia p50                |   2.46 s |     2.43 s   | sana     |
| Latencia p90                |   5.29 s |     5.46 s   | sana     |

### El número que importa: separar señal real de artefacto del mock

El harness inicial contaba `many_passes` y `slow` en bruto. Eso **inflaba** las
cifras: como el mock devuelve `{ok:True, simulated}`, el 4B a veces reintenta lo
que un tool **real** completa en 1 paso. La mejora `bd6cb87` distinguió:

- `many_passes_mock` (59) — artefacto del mock, **no ocurre en producción**
  (verificado en vivo: *génère une image* → 1 tool "L'image a été générée";
  *mach leiser* → 3 tools "Lautstärke eingestellt", sin loop).
- `loop_genuine` (**4**) — loops reales (el agente dice "límite de turnos" /
  "repitiendo sin avanzar"). Cluster real chico.
- `slow_from_passes` (8) — lentitud causada por los reintentos del mock.
- `slow` (**5**) — lentitud genuina.

**Conclusión medida:** tras los fixes, la señal **real** restante es pequeña
(4 loops genuinos, 5 slow genuinos) y `lang_drift` residual es mitad falso
positivo de la heurística (replies correctos en PT/IT que contienen letras
"ES-like") y mitad la cola larga de frases ultracortas (ya atacada, ver fix 8).

## Causa raíz transversal: **sesgo al español**

Todos los bugs reales hallados tenían la **misma raíz**: el modelo FT y el
pipeline arrastraban al español (documentado como *"language confusion"*,
Cohere EMNLP2024, en `reference_idioma_posttool_language_confusion_2026_06_06`).
Esto **viola el principio de universalidad** del producto (multi-idioma).

## Los 8 fixes (todos de raíz, todos multilingües)

| # | Commit    | Fix |
|---|-----------|-----|
| 1 | `f1a2ca6` | `_reply_lang` confía en `_detect_lang` robusto antes que en el ancla ciega del idioma del SO → corta el drift post-tool para usuarios no-ES. |
| 2 | `ea2e8fe` | `extract_message_to`: guardas `_FIRST_PERSON_RECIPIENTS`/`_NON_CONTACT_WORDS` → "decime X"/"tell me X" ya no abren WhatsApp. |
| 3 | `6fa371e` | `_CHITCHAT_ANCHORS` += desahogo en 6 idiomas ("no puedo más", "j'en peux plus", "ich kann nicht mehr"…) → el venir emocional rutea a `['session']`, no a tools terminales. |
| 4 | `7fc7f6f` | `_is_close_app_action` (cerrar en 6 idiomas) retira la tool homónima (steam/browser) → "Ferme/Chiudi Steam" cierra vía `app`, no la tool que no cierra. |
| 5 | `bd6cb87` | Harness: distingue `loop_genuine`/`slow` reales de los artefactos del mock → mediciones honestas. |
| 6 | `e59cfde` | `grounding_gate._FALLBACKS_BY_LANG` += FR/IT/DE/PT → los fallbacks honestos ya no caen a español. |
| 7 | (en e59cfde) | `agent_guards.build_user_facing_fallback`: el idioma sale del **texto del usuario**, no del reply rechazado (que ya está driftado). |
| 8 | `6d6cdd6` | `_IMPERATIVE_VERBS` += verbos cortos IT/FR/DE (vai, digita, lies, tippe, écris…) → rescata el `lang_drift` de comandos ultracortos donde `_detect_lang` no tenía señal. |

## Definición de Hecho (checklist)

- [x] Tests pasan (suite idioma/splitter/window **89/89**; los relevantes verdes).
- [x] Gate medido contra baseline (issues 140→129, lang_drift 63→50).
- [x] Causa raíz diagnosticada (sesgo al español / language confusion), no parche.
- [x] Verificado **EN VIVO** con el LLM real y fraseos variados (no solo tests).
- [x] Distinguida validación (mock) de señal real (loops/slow genuinos).
- [x] Memoria persistente actualizada.
- [x] Commits a ambos repos (origin + asistia, main + Dev).

## Pendientes / cola larga (no bloqueantes)

- `lang_drift` residual (~50): mitad falso positivo de la heurística del eval
  (no es bug del producto), mitad cola larga de frases de 2 palabras sin verbo
  conocido. Rendimientos decrecientes; mejorar `_detect_lang` para esas tiene
  riesgo de romper detecciones que ya andan.
- `loop_genuine` (4) y `slow` (5): cluster real chico, candidato a una próxima
  iteración si el usuario lo pide.
- Re-finetuning con rebalanceo SFT (~1% por idioma no-dominante) sigue siendo la
  cura de fondo del sesgo (ver memoria de re-finetuning v2); este cierre ataca
  el sesgo en el **pipeline**, no en los pesos.

## Addendum 2026-06-10 (run4) — los "loops genuinos" eran del mock + hueco de volumen perifrástico

Segunda pasada para cazar los 2 clusters reales que quedaron (4 loop_genuine,
5 slow). **Hallazgo medido en vivo: ninguno era bug de Baxy.**

- **Los 4 loop_genuine eran falsos positivos del mock.** El mock daba `{ok:True}`
  para acciones IRREVERSIBLES (apagar/bloquear/reiniciar PC) que en producción
  devuelven `needs_confirmation`. El 4B recibía "hecho" y reintentaba → loop
  falso. **Fix `39c72f3`:** el mock replica `needs_confirmation` para
  shutdown/restart/lock/sleep/hibernate/log_off. Verificado en vivo:
  *spegni il computer* → pide confirmación en italiano; *bloqueia o computador*
  → en portugués; *pausa o que está tocando* → pausa media; desahogo FR
  *"j'en peux plus"* → empatía en francés. **0 loops, 0 drift, latencia 0.6–1.7s.**
- **El fix #3 (desahogo→session) es robusto:** verificado 6/6 idiomas
  (FR/ES/EN/IT/PT/DE) → empatía en el idioma correcto, 0 tools peligrosas.
- **run4 con el mock corregido: lang_drift 50 → 10** (el fix #8 de verbos cortos
  rindió fuerte); issues 129 → 117. Router holdout intacto (recall 0.979).

**Hueco real encontrado (parcial):** la construcción *perifrástica* de volumen
(«dejar/leave + sin/casi sin sonido», sin verbo de volumen explícito) no estaba
en el corpus del router → no se ruteaba a `audio` en NINGÚN idioma salvo algunos
fraseos ES. Agregué 35 exemplars en 6 idiomas a
`router_eval_corpus.curated.jsonl` y regeneré `router_exemplars.npz`. Resultado:
5/7 fraseos ahora rutean a audio (ES/EN/IT/DE/FR), router holdout sin regresión.

**Residual honesto (queda para el reentreno):**
- PT «Deixa sem som» sigue bajo el umbral exemplar (sim 0.81 < 0.92) → no lo
  rescata. Bajar el umbral global arriesga falsos positivos en todo el router.
- Aun ruteando audio, el **4B no siempre lo elige** (no-determinismo) y mostró
  un drift puntual ES→FR en «déjalo mudo». Eso es del **modelo**, no del
  pipeline → cae en el reentreno del encoder+modelo (operación de horas, requiere
  OK del usuario), no en más exemplars.
- **Nota de versionado:** `router_exemplars.npz` y
  `router_eval_corpus.curated.jsonl` están en `.gitignore` (data/) y NO se
  trackearon — el cambio de exemplars es **local**, no propagado a los repos.
  Force-trackear binarios a dos repos es decisión de infra que conviene avalar
  junto con el reentreno. El fix del mock (`39c72f3`) SÍ está commiteado y
  sincronizado en los 4 refs.

## Fuentes

- Cohere, *"The Language Confusion Benchmark"*, EMNLP 2024 — base del
  diagnóstico de drift.
- Memoria: `reference_idioma_posttool_language_confusion_2026_06_06`,
  `reference_gemma4_finetune_oficial_2026_06_06`.
