# Cierre de misión — Mission-eval en vivo de Baxy (2026-06-09 / 2026-06-10)

> **Pedido del usuario:** fabricar a partir del dataset de finetuning un script
> que pruebe a Baxy **EN VIVO** (LLM real levantado), ≥18 categorías × ≥10
> prompts, para cazar fallas de calidad/latencia, hallar su causa raíz y
> arreglarlas. Objetivo: "dejar un Baxy perfecto".

> **REENTRENO DEL ENCODER (run10, aprobado por el usuario).** Tras revisar el
> historial (el re-FT del LLM E2B ya falló 2× y es irreducible en el 2B; el
> idioma post-tool ya se resolvió por runtime), se reentrenó el **encoder del
> router** (bajo riesgo, no degrada español) para consolidar los 4 huecos de
> corpus en el encoder mismo, no solo como exemplars. **v1:** huecos 25/25 pero
> holdout 0.9800→0.9767 (1 caso ES browser "buscar en sitio" sub-representado).
> Causa raíz medida (no era regresión de idioma): los 6 misses del viejo
> idénticos, +1 browser. **v2:** +28 ejemplos browser "buscar/comprar en sitio"
> (6 idiomas) → **holdout 0.9800 recuperado + huecos 25/25 + mismos 6 misses que
> el viejo (cero regresión)**. Promovido. El encoder (449 MB) NO se versiona
> (gitignored, regla >10 MB); la receta (`tool2vec_queries.jsonl`) + artefactos
> chicos sí; regeneración documentada en `gemma4_agent/data/README.md`. GOTCHA:
> el browser "buscar en sitio" sigue inconsistente en algunos fraseos (cola
> larga) — PERO el viejo fallaba igual, no es regresión.

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
- **Nota de versionado (RESUELTA en run5):** `router_exemplars.npz` y
  `router_eval_corpus.curated.jsonl` estaban gitignored. En run5 se
  force-trackearon (`git add -f`) siguiendo el precedente del repo
  (`router_eval_corpus.jsonl` + `tool2vec_centroids.npz` ya estaban así). Receta
  (corpus texto) + artefacto (npz) = reproducible con
  `scripts/router_exemplar_build.py`. Commit `d1861a3`, sincronizado en 4 refs.

## Addendum 2026-06-10 (run5) — BUG REAL: recordatorios 100% rotos en el router

El hallazgo más significativo de la misión. En el eval, `tool_mismatch`
escondía un bug real (no del mock): **«recordame sacar la basura mañana» /
«recuérdame comprar pan» / «remind me to call mom» no se ruteaban a `reminder`
ni `notification`** — iban a session/memory.

**Síntoma en vivo (medido):**
- ES: ejecutaba solo `session` y **MENTÍA** "Listo, te recordé sacar la basura"
  sin crear nada (bug de honestidad).
- EN: elegía `memory`×5 → **LOOP genuino** "límite de turnos".

**Causa raíz:** el corpus del router tenía **0 ejemplos** de `reminder` y **0**
de `notification`. La descripción de `notification` ya listaba estos fraseos
exactos, pero sin ejemplos que la anclen el encoder nunca ofrecía la tool. Una
**capacidad central** (recordatorios) era invisible para el router.

**Fix `d1861a3` (datos, no keywords):** +31 exemplars de recordatorio-de-acción
en 6 idiomas, etiqueta primaria `reminder` (como el dataset FT:
`correct=[reminder] also_valid=[notification]`). Regenerado el npz.

**Verificado:** routing 8/8 ofrece reminder/notification (antes **0/8**); en vivo
**3/5 crean el recordatorio de verdad (antes 0/5**, mentía siempre); router
holdout intacto (recall 0.9792, over-offers 0). Residual 2/5 (PT loop, FR
no-elige) = el 4B no elige la tool aunque se ofrezca → reentreno.

**Lección:** `tool_mismatch` no es siempre artefacto del mock — acá escondía una
capacidad central sin ningún ejemplo de anclaje. Vale inspeccionar los
`tool_mismatch` con `exp` de una tool concreta (no `[]`) buscando huecos de
corpus.

## Addendum 2026-06-10 (run6) — brillo multilingüe + método de barrido de huecos

Sistematicé la cacería: `scripts/_diag/_probe_router_gaps.py` mide
`select_tool_names` **sin LLM** (determinista) para separar huecos reales del
router del no-determinismo del 4B. Barriendo las tools `exp` que el router no
ofrecía, encontré el tercer hueco real.

**BUG `aff4044`: brillo no se ruteaba.** «Diminui o brilho» / «monte la
luminosité» / «mach den Bildschirm heller» / «aumenta o brilho» caían a
`session`; «abbassa la luminosità» caía a **`audio`** (confusión volumen/brillo).
El router solo ofrecía la tool de brillo para fraseos ES/EN directos con %.

**Causa raíz:** el corpus tenía **2 ejemplos** de brillo, ambos ES con %.
**Fix:** +31 exemplars subir/bajar/atenuar en 6 idiomas → `device_settings`.
Routing **2/10 → 9/10**; en vivo **0/6 → 4/6** ajustan (los 2 que no, honestos);
holdout **mejoró a 0.9795**, sin contaminar (hora→system, volumen→audio).

**Lección de diseño (importante): NO etiquetar contra el diseño.** Antes de
agregar exemplars verifiqué qué tool **implementa** y **documenta** la acción:
- Brillo es **`device_settings`** (su schema dice `brightness_up/down` "for
  'subí/bajá el brillo'"), aunque el dataset FT a veces lo marca `system`. Ambas
  implementan brillo, pero device_settings es la canónica → etiqueté esa.
- WiFi/Bluetooth son **`device_settings`** por diseño; el dataset los marcaba
  `system` (etiqueta mala). El router ya los ruteaba bien → **no se tocaron**.
  Si hubiera "arreglado" contra el dataset, habría roto routing correcto.

## Estado de la cacería de huecos de corpus (3 cerrados)

| run | hueco | fix | en vivo |
|-----|-------|-----|---------|
| run4 | volumen perifrástico («dejar sin sonido») | +35 exemplars → audio | 5/7 rutean |
| run5 | recordatorios (0 ejemplos reminder/notif) | +31 exemplars → reminder | 0/5→3/5 ejecutan |
| run6 | brillo multilingüe (2 ejemplos, solo ES%) | +31 exemplars → device_settings | 0/6→4/6 ajustan |
| run7 | cerrar/reiniciar app + focus ventana no-ES | +31 exemplars → app/window | routing 5/9→9/9, 0/3→3/3 |

Patrón común: capacidad real con **corpus vacío o monolingüe** → el encoder no la
ofrece → el 4B improvisa (miente o loopea). Fix de datos, reproducible, holdout
intacto (subió **0.9792 → 0.9800** acumulado en runs 5–7). **Residual recurrente**
(PT bajo umbral + el 4B no siempre elige la tool aunque se ofrezca) es del
**modelo** → reentreno (requiere OK del usuario).

## Addendum 2026-06-10 (run7) — cerrar/reiniciar app + focus de ventana (4º hueco)

Barrido determinista con `_probe_router_gaps.py`: «encerra o Word»→`office`,
«Quitte Chrome»→`browser` (la app-de-tipo homónima secuestraba el cierre);
«restart Spotify»/«reinicia Discord»→`session`; «porta in primo piano» / «bring
to the front» / «trae al frente»→`session` (focus de ventana sin rutear).

**Diseño verificado:** `app` = "abrir, **cerrar** o encontrar un programa";
`window` = "list windows, **focus**, …"; `office` solo **crea** documentos (no
cierra Word). Etiqueté contra el diseño, no contra el dataset.

**Causa raíz:** cobertura multilingüe escasa — restart tenía 8 ejemplos (todos
ES), focus solo 4 (poco diversos). **Fix `78b9a34`:** +19 app (restart 6-idiomas
+ cerrar Word/Chrome/Excel) +12 window (focus 6-idiomas). Routing app **5/9→9/9**,
window **0/3→3/3**; holdout **0.9800**, control intacto.

**Pendiente real encontrado (no del router):** el guard de honestidad no atrapa
«ho spostato X in primo piano» (IT) cuando el 4B ejecutó 0 tools → miente 2/4
corridas. Es un detector **estructural** del guard, no del corpus. **Resuelto en
run8 ↓.**

## Addendum 2026-06-10 (run8) — BUG DE HONESTIDAD: detector solo-español

El hallazgo de **mayor impacto** de la misión. Al medir la cobertura del guard
de honestidad estructural (`detect_action_claim_without_evidence`) en 6 idiomas:
**1/10 — solo español.** El 4B podía **mentir impune** en EN/IT/PT/FR/DE
afirmando acciones que no ejecutó: «I have opened the app», «Ho spostato la
Calcolatrice in primo piano», «J'ai ouvert», «Ich habe … geöffnet» con 0 tools
pasaban como verdad. La honestidad estructural es un **principio central** del
producto → este era un agujero grave. Mismo sesgo-al-español de toda la misión,
ahora en el guard.

**Causa raíz:** `_AUX_PERFECT/_CONTINUOUS` y `_CONSUMMATED_STEMS` eran solo ES.

**Fix `2578290` (estructural, no enumeración):**
- Auxiliares de perfecto/continuo en 6 idiomas.
- **Detección MORFOLÓGICA de participio** (-ato/-ito/-uto/-ado/-ido, ge-…-t/-en):
  atrapa verbos NO enumerados. Aprendizaje clave: añadí 50 raíces y el 4B usó la
  #51 («ho **portato**») → la señal correcta es la **morfología**, no el lema
  (confirma la memoria «perseguir strings es infinito → detector estructural»).
- Guardas anti-FP: participios de estado/ser (stato/été/been), cortesía
  (obrigado/encantado), idiom de conocimiento («oído hablar de» / «sentito
  parlare di» / «heard of»).

**Verificado:** cobertura **1/10 → 10/10**; **auditoría adversarial 25/25 sin
falsos positivos** (conocimiento/charla/oferta/estado respetados en 6 idiomas);
morfológico atrapa verbos no-enumerados con 0 FP. Suite honestidad **64/64**.
Test de regresión multilingüe añadido.

**Pendiente (clase distinta):** afirmar el **estado-resultado** sin actuar →
**resuelto en run9 ↓.**

## Addendum 2026-06-10 (run9) — estado-resultado afirmado sin actuar

La otra mitad del bug de honestidad. El 4B, ante «traer al frente / maximizar»
sin ejecutar tool, afirmaba el **estado-resultado** en vez de la acción:
«Calculator is now in front», «la calcolatrice è ora in primo piano», «Notepad
is now maximized». No es aux+participio (el detector de run8 no lo cubría): es
**copula + estado**. Medido en vivo: ~25% de las corridas 0-events.

**Fix `a8e8cce` — `_claims_result_state_without_action`, CONSERVADOR.** Señal
discriminante (medida contra adversarial): marcador «ahora» (now/ora/agora/ya/
jetzt/adesso/maintenant) **O** opener de completitud (Done/Listo/Perfetto/Fertig)
+ estado-de-ventana (in front/primo piano/primer plano/maximiz/minimiz). Excluye
ofertas/preguntas/condicionales. **8/8 mentiras detectadas en 6 idiomas, 0 FP**
(conocimiento/definición/oferta respetados); suite 65/65; en vivo **25% → ~12%**.

**Decisión conservadora (regla: no arriesgar FP):** NO se marca el estado-resultado
**pelado** sin «ahora»/opener («La X está en primer plano» a secas) porque
colisiona con definiciones de conocimiento («primer plano significa…»). Ese
residual cae en el **reentreno** (enseñar al 4B a no afirmar lo no verificado),
no en heurística frágil.

## Resumen de la misión (runs 4–9)

| run | hallazgo | tipo | resultado |
|-----|----------|------|-----------|
| 1–3 | 8 fixes del sesgo-al-español (lang_drift, WhatsApp, desahogo, close-app, fallbacks…) | pipeline | issues 140→117, lang_drift 63→10 |
| 4 | volumen perifrástico | hueco de corpus | 5/7 rutean |
| 5 | recordatorios (capacidad central rota) | hueco de corpus | 0/5→3/5 ejecutan |
| 6 | brillo multilingüe | hueco de corpus | 0/6→4/6 ajustan |
| 7 | cerrar/reiniciar app + focus ventana | hueco de corpus | routing 5/9→9/9, 0/3→3/3 |
| 8 | **honestidad: detector solo-español** | guard | cobertura 1/10→10/10, 0 FP |
| 9 | honestidad: estado-resultado | guard | 8/8, 25%→12% en vivo |

**Hilo conductor:** TODO era el mismo **sesgo-al-español** — en el modelo, en el
corpus del router, y en los guards de honestidad. Cada fix lo ataca en el
**pipeline** (datos/estructura), reproducible y con holdout intacto. El residual
recurrente (el 4B no siempre elige la tool aunque se ofrezca; afirmaciones peladas
de estado) es del **modelo** → la cura de fondo es el **reentreno con rebalanceo
SFT**, que requiere OK del usuario.

## Fuentes

- Cohere, *"The Language Confusion Benchmark"*, EMNLP 2024 — base del
  diagnóstico de drift.
- Memoria: `reference_idioma_posttool_language_confusion_2026_06_06`,
  `reference_gemma4_finetune_oficial_2026_06_06`.
