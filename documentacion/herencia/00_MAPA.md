# El mapa de la herencia

Qué hay construido en los cinco intentos de este proyecto, **qué de eso funciona
hoy comprobado ejecutándolo**, y qué se trae a BAXY.

Goal 01, cerrado el **2026-08-16**. Los otros diez goals deberían poder leer sólo
este documento. El único anexo es [`D_ADAPTADORES_POR_APP.md`](D_ADAPTADORES_POR_APP.md),
que lista fichero por fichero los adaptadores por aplicación.

> **Actualización 09.5.12 (2026-08-31):** el linaje reconciliado está en
> [§11](#11-reconciliacion-095). Las fechas y conclusiones del Goal 01
> (**2026-08-16**) no se reescriben. Herencia previa, delta nuevo, piezas
> trasplantadas (cero lotes) y rechazos quedan nombrados aparte.

> **Lo más importante que encontró este goal, en una línea:** la medición que
> justificaba consolidar el catálogo a 16 herramientas **existe y dice lo
> contrario de lo que se creía**. Está en [§6](#6-el-problema-de-la-comprensión).

---

## 1. Los cinco intentos

No son proyectos distintos. El README de `Probando Gemma 4` lo dice literal: *«el
proyecto se renombró a Baxy (antes Gemma 4 Agent, brevemente Carter)»*. Es el
mismo producto escrito cinco veces, y por eso los errores de uno son los del
siguiente.

| # | Carpeta | Cuándo | Qué se propuso | Por qué se abandonó |
|---|---|---|---|---|
| 1 | `Carter OS AI` (v1–v3) | abr 2026 | Agente local con watchdog de VRAM, perfiles y UIA | Visión por coordenadas ciegas y backends no atestados producían **estados falsos**: afirmaba haber hecho cosas que no hizo |
| 2 | `Carter OS AI/carter_v5` (v4–v5) | may 2026 | Consolidar: ≤16 herramientas, prompt recortado, skills/microagentes | **Se autodiagnosticó**: «el proyecto crece por acumulación, no por reemplazo». Tres routers en serie, ocho capas, `agent.py` a 1.397 líneas contra su objetivo de 400 |
| 3 | `Probando Gemma 4` | may–jun 2026 | Gemma 4 Agent → Baxy. Voz, router entrenado, computer-use, accesibilidad, memoria | La investigación más profunda del linaje, pero **una suma de componentes no es un release**: 10 de los 16 s por turno eran sobrecarga propia |
| 4 | `FunctionGemma` | jun 2026 | Modelo 270M fine-tuneado sólo para emitir tool-calls + encoder de router | Rápido pero **no conversa** (0/3 conocimiento, 0/4 smalltalk medido) y el catálogo queda cocido en los pesos |
| 5 | `BAXY` (a secas) | jul–ago 2026 | Reconstrucción sobre .NET con contratos, kernel y journal verificados | **No se abandonó**: es la base directa de `BAXY Definitivo`. Sus activos de runtime siguen viviendo ahí |

`JRVS` no entra: es otro producto (operaciones self-hosted para equipos) y no
comparte linaje.

**Dónde viven los activos.** Esto sorprende y conviene saberlo antes de tocar
nada: el runtime del BAXY actual **no tiene sus modelos dentro del repositorio**.
`%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json` apunta a
`Programacion\BAXY\legacy\models\artifacts\`, es decir al repositorio del cuarto
intento. Borrar `BAXY` deja a `BAXY Definitivo` sin modelo, sin llama-server y sin
wake word.

---

## 2. Qué funciona hoy — ejecutado, no leído

Todo lo de esta tabla se corrió el 2026-08-16 en esta máquina. Lo que no pude
ejecutar está dicho como tal.

| Pieza | Dónde está | Resultado medido | Veredicto |
|---|---|---|---|
| **STT Parakeet TDT 0.6b v3 int8** | `~/.gemma4/models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8` | Carga 2,4 s. **RTF 0,065–0,087** en CPU. Transcribió 18,7 s de español con 1 error de 47 palabras | **Funciona** |
| **Wake word** `baxy.onnx` | `BAXY/legacy/models/artifacts/wake_livekit/` | Positivo (voz real repitiendo «baxy»): **máx 0,916**, 664 ventanas sobre 0,5. Negativo (18,7 s de español sin «baxy»): **máx 0,225, 0 disparos**. RTF 0,026 | **Funciona, con separación limpia** |
| **LLM Gemma-4-E2B QAT Q4_K_XL** | `BAXY/legacy/models/artifacts/gemma4-e2b/` | Prosa española correcta, persona «Soy BAXY» **sólo con system prompt**. Pero **6,3–11,4 s por turno**, de los que 200–400 tokens son *thinking* en inglés | **Funciona y no sirve** — ver §5 |
| **Encoder de router** `model_int8.onnx` | `BAXY/legacy/models/artifacts/router_encoder_ft/` | Carga 0,40 s, **2,1 ms/frase**, 384 dim. «abre spotify» ≈ «abre spotify por favor» 0,88; «pausa la música» ≈ «pon música» 0,75; la pregunta de conocimiento queda a ≤0,24 de todo | **Funciona bien** |
| **FunctionGemma 270M FT** | `BAXY/legacy/models/artifacts/functiongemma-ft-270m-it-Q8_0.gguf` | **0,11–0,23 s** por decisión. Pero inventa nombres fuera del catálogo declarado (`set_volume`, `no_query_query`) y emite call incluso en preguntas de conocimiento | **Funciona y se rechaza** — ver §6 |
| **Accesibilidad** (3 modos) | `Probando Gemma 4/gemma4_agent/computer_use_pkg/` | Importa y corre standalone. 3 modos cargados, `no_vidente` con hint de 1.047 caracteres. **El modo persistido en `~/.gemma4` es `no_vidente`**: se usó de verdad | **Funciona** |
| **OCR Tesseract 5.4.0** | `C:\Program Files\Tesseract-OCR` | Instalado y en PATH. **Sólo idiomas `eng` y `osd`: no hay `spa`** | **Funciona a medias** |
| **Compuerta .NET** | este repositorio | Release, 0 advertencias, 0 errores. 3.865 pruebas: 3.863 pasan, 1 omitida, **1 en rojo desde antes de este goal** (§8) | **Funciona, con un sello caducado** |

**Lo que resultó ser promesa y no activo:** en `Probando Gemma 4`, los directorios
`checkpoints/` y `captures/` que el goal señalaba como pista **están vacíos, 0
ficheros**. Lo que sí hay son 17 GB en `models/` y 39 GB en `data/`.

---

## 3. Las cuatro herencias obligatorias

### A. Accesibilidad — **existe, completa y medida**

Implementada en `Probando Gemma 4`, 2.927 líneas:
`computer_use_pkg/accessibility.py` (175), `accessibility_voice.py` (198),
`safety_pkg/reply_validator.py` (1.553), `scripts/accessibility_eval.py` (1.001).

No es promesa de README. Tiene **tres modos separados a propósito** —`normal`,
`no_vidente`, `movilidad`— porque la necesidad perceptual y la motora son
distintas: el no vidente quiere **más audio**, el de movilidad reducida ve bien y
quiere que el agente **actúe** por él.

Gates medidos el 2026-05-26, todos PASS: activación por voz 10/10 con 0 falsos
positivos; hands-free recall 100 %, 0 FP; narración no vidente 6/6; anti-regresión
de `normal` limpia. 58 tests unitarios.

Dos hallazgos propios al ejecutarlo: **arranca standalone** (no arrastra el resto
del agente) y **el modo persistido en esta máquina es `no_vidente`**, o sea que el
dueño lo usó.

**Se hereda el diseño, no el código.** La activación por voz por embeddings
multilingües y las dos guardas estructurales del `reply_validator` son la parte
valiosa; el acoplamiento a `agent.py` no viene. Y el límite que ya se documentó
sigue en pie: *«el techo del control por voz es el del computer-use»*.

### B. Cascada UIA → OCR → visión — **existe a medias, y el reparto sorprende**

El detalle está en [`D_ADAPTADORES_POR_APP.md`](D_ADAPTADORES_POR_APP.md). Lo que
hay que saber aquí:

- **El escalón OCR existe y funciona**: `CaptureVisionAdapter.cs` (452 líneas) ya
  invoca `tesseract.exe`. Pero **sin `spa.traineddata`**, y BAXY es
  español primero. Es un fichero de 15 MB, no un problema de diseño.
- **El escalón UIA existe, pero en PowerShell**: `DesktopClickVisible.ps1` (100) y
  `DesktopSelectAll.ps1` (264) hacen UIA real y sin nombre de aplicación. En C#
  sólo hay un fichero que toca UI Automation.
- **El escalón de visión no existe** como política: hay `vision.describe`, no hay
  una cascada que decida cuándo baja de UIA a OCR a visión.

Traducido para el goal 07: **no se empieza de cero, se sube un escalón.** Falta el
UIA en código, la política de cascada y el modelo de visión.

### C. El set de 16 herramientas de Carter v4 — **existe, y su medición dice lo contrario**

Esto es lo más importante del goal y está desarrollado en [§6](#6-el-problema-de-la-comprensión).

En corto: el set consolidado existe y la reducción de tokens existe, pero
**«−68 % de tokens sin perder calidad» no es lo que midió nadie**. Son dos
recortes distintos —CORE_PROMPT 3400→883 tokens (−74 %) y anchors 25→8 (−68 %)—
y el benchmark que debía probar el «sin perder calidad» **se corrió y salió
peor**: 75,93 % → 62,96 %.

### D. Cuantización y prosa (FunctionGemma) — **existía, y lo medí de nuevo**

La identidad pide explícitamente no heredar la conclusión sino medir. Los dos
GGUF están en `Probando Gemma 4/models/E2B-QAT/`, así que corrí el A/B:

| | Q2_K_XL (2,19 GB) | Q4_K_XL (2,62 GB) |
|---|---|---|
| Persona | «Soy BAXY.» — seca | «Soy BAXY, tu compañero. Vivo aquí en el PC…» |
| Prosa descriptiva | Correcta pero plana | Correcta y con registro |
| Seguir «en cuatro frases» | **No la cumple** (3 frases) | La cumple |
| Degeneración | **Sí**: «Problemas de conexión o problemas de conexión» | No observada |
| Palabras inventadas | **No las reproduje** | No |
| Latencia | 8,1–12,6 s | 6,3–11,4 s |

**Matiz honesto:** el síntoma heredado —«cuecer», «vertir», «alredad»— **no lo
reproduje** en este sondeo, ni en Q2 ni en Q4. Lo que Q2 sí muestra es
degeneración por repetición y pérdida de seguimiento de instrucción. Y Q2 **no
compensa en velocidad**: fue más lento en las seis pruebas.

Conclusión para el goal 06: Q2 no gana nada aquí, así que la decisión heredada
(Q4_K_XL QAT) se sostiene — pero por un motivo distinto del documentado, y sobre
un sondeo de 6 prompts, no un corpus. **La medición seria sigue pendiente.**

---

## 4. Qué se hereda

| Qué | De dónde | Qué hace falta para traerlo |
|---|---|---|
| **Wake word `baxy.onnx`** + verificador logreg | `BAXY/legacy/.../wake_livekit/` | Copiarlo a un sitio propio y escribir su manifiesto: hoy `wake_manifest` es `null` y `wake_on_start` es `false`, o sea que **está apagado** |
| **STT Parakeet int8** | `~/.gemma4/models/` | Nada técnico: ya lo resuelve `assets.manifest.json`. Sí hace falta resolver el sesgo de nombre propio (§7) |
| **Encoder de router 384-dim** | `BAXY/legacy/.../router_encoder_ft/` | Reentrenar sobre el catálogo actual. El encoder está atado al set de 31, no a las ~170 operaciones de hoy |
| **Diseño de los 3 modos de accesibilidad** | `Probando Gemma 4` | Reimplementar sobre .NET. El motor accesible siempre; el modo sólo cambia la presentación |
| **`CaptureVisionAdapter` + scripts UIA** | este repositorio | Ya están. Falta `spa.traineddata` y la política de cascada |
| **Corpus y bancos de evaluación** | `Probando Gemma 4/data` (39 GB), `D:\BAXYRuntime\datasets` | Inventariar antes de usar: hay holdouts contaminados documentados |
| **Toda la capa .NET** | este repositorio | Nada. Decisión ya tomada y auditada |
| **La lección del benchmark 540** | `Carter OS AI/La razon de carter/*.json` | Leerla antes de consolidar el catálogo (§6) |

## 5. Qué no se hereda, y por qué

Un rechazo con el mecanismo entendido vale tanto como una herencia.

| Qué | Por qué no |
|---|---|
| **Gemma-4-E2B como decisor tal cual** | Gasta 200–400 tokens de *thinking* en inglés **antes de cada respuesta**, incluso para «Abre Spotify» (341 tokens, 7,7 s). El listón del dueño es **3 segundos sin señal**. Ninguna de las 6 pruebas bajó de 4,2 s. Y `--reasoning-budget 0` **lo empeora**: el llama-server b9980 deja de separar el razonamiento y el borrador en inglés **pasa a ser la respuesta visible**. Se hereda el modelo como candidato, no como decisión. **El goal 03 lo cerró midiendo**: contra Qwen3-4B sobre la misma población pierde 63 decisiones crudas a 82 y p90 3,59 s a 3,02 s, y sale |
| **FunctionGemma 270M como caller** | Es 30–50× más rápido (0,15 s), pero **emitió nombres que no estaban en el catálogo declarado** (`set_volume` por `audio_volume`, `no_query_query` inexistente) en 4 de 8 casos, y llamó a una herramienta ante una pregunta de conocimiento. El catálogo quedó **cocido en los pesos**, lo que choca de frente con «el catálogo es datos, no código». Cambiar una operación exigiría reentrenar |
| **Q2_K_XL** | No es más rápido y sí degenera. Ahorra 0,43 GB por una pérdida de calidad sin contrapartida |
| **`agent.py` y el bucle de Carter** | 1.397 líneas contra su propio objetivo de 400. Es el patrón que el proyecto viene a no repetir |
| **Los tres routers en serie** | Cada uno existía para tapar el fallo del anterior. Es la señal de fracaso que la identidad nombra explícitamente |
| **Redirects ad hoc por frase** | Documentado en abril: reparar cada fallo con un redirect acumula colisiones |
| **Adaptadores por aplicación** | 2.454 líneas que sirven a 4 aplicaciones. Es cobertura falsa: sustituirlos por la cascada da **menos catálogo y más cobertura** |
| **`checkpoints/` y `captures/`** | Están vacíos. No hay nada que heredar |
| **Los 13 GGUF de FunctionGemma** | 5,8 GB de iteraciones de fine-tuning (`iter1`…`iter4`, `run7`…`run9`). Sólo el campeón tiene valor, y se rechaza igual |
| **El instalador certificado** | `Baxy.Setup` son **13.194 líneas de producción y 10.068 de pruebas**: el **17,8 %** de las 74.066 líneas de `src/`. Funciona y no se tira, pero la instalación certificada está fuera de alcance por decisión del dueño. **Que nadie lo arrastre entero al hacer cuentas de tamaño** |

---

## 6. El problema de la comprensión

Aquí arranca el goal 03. Hay **cuatro soluciones construidas** al mismo problema
—de un texto libre a la operación correcta— y son comparables.

> **Cerrado el 2026-08-17, y lo que midió está en
> [`../base/03_COMPRENSION.md`](../base/03_COMPRENSION.md).** En corto: la
> comprensión sobre paráfrasis frescas es **46,0 %**, no ≥ 90 %; el decisor pasó
> a **Qwen3-4B** por medición; y la frontera tiene nombre — sin la puerta de
> dominio léxica la comprensión sube a 66,9 % pero 20 de 36 peticiones fuera de
> catálogo ejecutan un efecto no pedido. Lo que sigue abajo es el contexto con el
> que arrancó, no la conclusión.

| # | Solución | Dónde | Lo que midió | Estado |
|---|---|---|---|---|
| 1 | **Router semántico + centroides Tool2Vec** (MiniLM-L12 384-dim fine-tuneado) | `FunctionGemma/router/`, pesos en `BAXY/legacy/.../router_encoder_ft/` | **Holdout tool recall 0,9521**. Y el dato clave: encoder-67 vs encoder-31 **equivalentes, 0,9521 los dos** | Ejecutado hoy: 2,1 ms/frase, separación semántica correcta |
| 2 | **Planner completo** (router + memoria de ejemplares + cabeza de abstención + cabeza por herramienta) | `FunctionGemma/router/routing/`, `heads/` | Más preciso que el 1 según su README, sin número publicado | No ejecutable standalone: importa de `gemma4_agent` |
| 3 | **FunctionGemma 270M fine-tuneado** | `BAXY/legacy/.../functiongemma-ft-270m-it-Q8_0.gguf` | Base vs base: acción 6/13 vs 5/13 de E2B, **conocimiento 0/3, smalltalk 0/4** | Ejecutado hoy: 0,15 s, inventa nombres. Rechazado (§5) |
| 4 | **Política de turno del BAXY actual** (`turn.decide`, e5-small multilingüe, familia + árbitro semántico, bge-m3 y reranker en evaluación) | `src/baxy_mind/`, experimentos R186–R281 | Umbrales congelados en torneo: tau 0,90, margen 0,005 | En producción. **Es el que falla**: ve hasta 28 candidatos y elige mal |

### La medición que hay que leer antes de consolidar

El goal 03 iba a arrancar de «Carter midió −68 % de tokens sin perder calidad al
consolidar a 16». **Fui a la fuente y no es eso.**

En `06_benchmark_540.md` hay dos recortes distintos, y ninguno es «−68 % de
tokens por consolidar el catálogo»:

- CORE_PROMPT 3400 → 883 tokens = **−74 %**
- Anchors 25 → 8 = **−68 %**
- El catálogo se bajó a ≤16 por otra razón: *«tool count > 22 → degradación documentada»*

Y sobre el «sin perder calidad»: el propio documento dice *«[Pendiente — se
actualiza en `07_score_final_honesto.md` cuando termine el bench]»*. **Ese
documento no existe en ningún sitio.** Pero los datos crudos sí, en la misma
carpeta:

| Corrida | Pass | Partial | Fail | Tasa |
|---|---:|---:|---:|---:|
| `baseline_p0_per_cat_3.json` | 41 | 10 | 3 | **75,93 %** |
| `post_refactor_p0_per_cat_3.json` | 34 | 9 | **11** | **62,96 %** |
| `step1_revert_prompt_anchors.json` | 30 | 11 | 13 | 55,56 % |
| `step2_no_missiongoal_no_eager.json` | 35 | 11 | 8 | 64,81 % |

**El refactor costó 13 puntos y casi cuadruplicó los fallos (3 → 11).** El
informe que lo diría nunca se escribió; los JSON se quedaron.

Y el daño no fue uniforme — esto es lo accionable:

| Categoría | Δ pass |
|---|---:|
| C08 web/URLs | **−2** |
| C17 follow-ups | **−2** |
| C05 conversación vs acción, C06 router, C09 Steam, C15 latencia, C16 multilingüe/typos | −1 cada una |
| C02 identidad, C14 misiones compuestas | +1 cada una |

Se rompió justo donde el contexto importa: **seguimiento de conversación,
multilingüe y encadenado de herramientas**. Es decir, el recorte de prompt y
anchors se llevó por delante el andamiaje de desambiguación, no el catálogo.

**Las dos mediciones juntas dicen algo que ninguna dice sola:** consolidar es
gratis en la *recuperación* (67→31 no perdió nada: 0,9521 en ambos) y caro en la
*ejecución de punta a punta* (75,93 → 62,96). El goal 03 debe medir las dos
cosas, y la identidad ya lo pedía al exigir **cobertura y cuenta a la vez**.

---

## 7. Preguntas ya respondidas — y cuáles caducaron

Para que ningún goal vuelva a correr un torneo que alguien ya corrió. La fecha es
lo que decide: **la conclusión caduca, el método y el mecanismo no.**

### Vigente — úsalo tal cual

| Pregunta | Respuesta | Dónde | Fecha |
|---|---|---|---|
| ¿Por qué fracasó el proyecto cuatro veces? | Acumulación en vez de reemplazo | `biblioteca/carter/la-razon-de-carter/11_lecciones_v1_a_v4.md` | may 2026 |
| ¿Sirve un harness de 540 casos para validar? | No por sí solo: 489/540 automáticos eran 417/540 reales, **72 falsos positivos** | `06_benchmark_540.md` y auditoría v4 | may 2026 |
| ¿Consolidar el catálogo sale gratis? | **No.** −13 puntos end-to-end | los cuatro JSON de `La razon de carter` | may 2026 |
| ¿Un encoder pequeño pierde al reducir el catálogo? | **No**: 67 vs 31 idénticos, recall 0,9521 | `FunctionGemma/router/README_ROUTER.md` | jun 2026 |
| ¿Se puede tener la persona sin fine-tuning? | **Sí**, sólo con system prompt | verificado hoy | ago 2026 |
| ¿Hacen falta modos de accesibilidad separados? | **Sí**, perceptual y motora se sirven mal con un solo modo | `modos_accesibilidad.md` | may 2026 |
| ¿Es mejor UIA→OCR→visión que coordenadas ciegas? | Sí, y las coordenadas ciegas producen estados falsos | `04_computer_use/` | may 2026 |
| ¿Qué gotchas tiene FunctionGemma? | 8 medidos: rol `developer`, ctx 32K, stop token, sesgo al inglés… | `FunctionGemma/README_TOOLS.md` | jun 2026 |
| ¿Se puede confiar en un holdout heredado? | No: 99,64 % curado cayó a 85,7 % en logs reales | `02_router/05_HISTORIAL_SPRINTS.md` | jun 2026 |

### Caducado — hay que rehacerlo contra lo que existe hoy

| Pregunta | Por qué caducó |
|---|---|
| **Torneo de STT** (Parakeet vs Whisper vs faster-whisper) | may–jun 2026. Han salido reconocedores nuevos; y el problema real —el nombre propio— sigue abierto |
| **Comparativa de LLM local** | may–jun 2026, con E2B/E4B. El `assets.manifest.json` ya lista Qwen3-4B **por delante** de Gemma-4-E2B, o sea que la decisión ya se movió sin que se rehiciera el torneo |
| **Auditoría de 10 competidores** | may 2026. Actualizar sólo lo que cambió, no rehacerla |
| **Perfiles de VRAM de 4 GB** | Nunca hubo medición en GPU física de 4 GB: era proxy. **Está prohibido afirmar 4 GB hasta medirlo** |
| **Investigación de eye-tracking por webcam** | may 2026, y no hay decisión de producto que dependa de ella |
| **El −68 % / −74 % de tokens** | Su premisa está refutada por los JSON de su propia carpeta (§6) |

La biblioteca tiene **1.350 documentos** indexados en
[`biblioteca/00_INDICE.md`](../../biblioteca/00_INDICE.md) por qué pregunta
responde cada área, y [`01_INVENTARIO.md`](../../biblioteca/01_INVENTARIO.md) los
lista con título y fecha para buscar por palabra.

---

## 8. Lo que este goal cambió en el código

Las tres deficiencias medidas que el goal mandaba arreglar al heredar:

**1. Adaptadores por aplicación.** Inventariados fichero por fichero en
[`D_ADAPTADORES_POR_APP.md`](D_ADAPTADORES_POR_APP.md). No se construye aquí: es
el goal 07. El dato que ordena ese trabajo es que **el escalón OCR ya existe**.

**2. `MissionEngine`: de ocho constructores a uno.** Resuelto con
`MissionEngineOptions`. El fichero pasó de 473 a 381 líneas.

**3. `MainWindowViewModel` descompuesto.** De **3.678 a 3.162 líneas**, con cinco
responsabilidades extraídas a ficheros propios y sin estado compartido:

| Fichero nuevo | Líneas | Una responsabilidad |
|---|---:|---|
| `ModelMessageComposer.cs` | 178 | Redactar con el modelo el texto de una respuesta ya verificada |
| `PendingModelMessageQueue.cs` | 192 | La cola de respuestas verificadas que esperan texto, con su reintento |
| `PrivateOperationNarration.cs` | 119 | El texto de memoria privada y audio: confirmación, fallo, pendiente |
| `MissionNarration.cs` | 87 | El texto de una misión multipaso: completada, detenida, recuperada |
| `MindArgumentNormalization.cs` | 45 | Llevar los argumentos que extrajo el modelo a su forma canónica |

Ninguno recibe el ViewModel: la cola habla por cuatro delegados y los otros
cuatro son funciones puras. Eso es el nivel 1 de `03_COSTURAS.md` — borde real,
no reparto de líneas.

**Lo que queda, dicho claro:** el ViewModel sigue en 3.162 líneas. Lo que no se
descompuso es **la máquina de estados del turno** —ejecución de plan multipaso y
flujo de confirmación de memoria, unas 1.050 líneas— porque comparten
`_pendingMindPlan`, `_planStore` y `AddMessage`, y separarlas exige un colaborador
con estado, no una extracción. Está anotado en `APLAZADOS.md` con su borde
nombrado.

### La compuerta, dicha como está

**Compilación Release: 0 advertencias, 0 errores**, con `TreatWarningsAsErrors`,
`Nullable enable`, analizadores en `latest-recommended` y `EnforceCodeStyleInBuild`.

| Proyecto | Pasan | Fallan | Omitidas | Total |
|---|---:|---:|---:|---:|
| `Baxy.Contracts.Tests` | 59 | 0 | 0 | 59 |
| `Baxy.Kernel.Tests` | 116 | 0 | 0 | 116 |
| `Baxy.Providers.Windows.Tests` | 442 | 0 | 0 | 442 |
| `Baxy.Setup.Tests` | 477 | 0 | 0 | 477 |
| `Baxy.Integration.Tests` | 2.769 | **1** | 1 | 2.771 |
| **Total** | **3.863** | **1** | **1** | **3.865** |

El total es exactamente los **3.865** esperados. Hay una prueba en rojo, y **no la
causó este goal**:

- **`FieldSourceAndRebuiltPayloadMatchTheCurrentSeal`** sella el árbol de
  `src/Baxy.FieldUi`: espera 38 ficheros y SHA-256 `0F6C38D1…`. El árbol
  comprometido tiene **35 ficheros y `12929F7A…`**. `git status` da ese directorio
  limpio, o sea que el árbol es byte a byte el de `HEAD` y **la prueba falla igual
  en `HEAD`**, con o sin los cambios de este goal. El sello lleva mal desde el
  commit inicial `7662b80`, que introdujo a la vez el árbol y la prueba.
  **No se corrige subiendo la constante**: un sello existe justamente para que un
  cambio silencioso ponga la compuerta en rojo, y no está establecido cuál de los
  dos árboles es el bueno. Anotado en `APLAZADOS.md`.

### Actualización 09.5.11A — sello FieldUi (el hallazgo de arriba no se borra)

**Antes (Goal 01, 2026-08-16):** el sello esperaba 38 ficheros y
`0F6C38D1E3C377012BD7231372363334DB7ADD51845578074E59EFB1195E8122`; el árbol
comprometido tenía 35 y `12929F7A…`. La constante no se tocó.

**Evidencia nueva:** [`../base/00_COMPUERTA.md`](../base/00_COMPUERTA.md) §1.
Goal 02 recuperó `dist/index.html`, `dist/assets/index-CjozYCnU.css` y
`dist/assets/index-D3QuhrLm.js`. El hash del árbol de 38 cuadra el sello
publicado. La constante no se subió.

**Efecto:** el rechazo de «subir la constante al hash de 35» se conserva. El
árbol correcto era el de 38, y ya está versionado.

### Actualización 09.5.11B — prosa de escucha (el hallazgo de Goal 06 no se borra)

**Antes (Goal 06, 2026-08-23):** censo 0 literales / 0 ficheros. Toda prosa
visible sale de hechos JSON + `message.compose`.

**Evidencia nueva:** Goal 09 (`273a321`) reintrodujo cuatro constantes en
`MainWindowViewModel` para el interruptor de escucha. El censo vivo las
contaba. 09.5.11B las sustituye por `TurnVisibleFacts`; el censo vuelve a 0/0.
No se relajó el censo ni se aplazó al Goal 10.

Y un hallazgo de entorno que **sí** se arregló: 8 pruebas de
`MindShellEndToEndTests` fallaban por `FileNotFoundException: The deterministic
mind contract test requires Python`, porque `FindPython` busca
`experiments/mind_router_spike/.venv/Scripts/python.exe` o `C:\Windows\py.exe` y
ninguno existía en esta máquina. La fixture es stdlib puro, así que se creó el venv
en la ruta que el propio repositorio espera.

---

## 9. Cómo se decidió qué entra

Los tres filtros del goal, aplicados en orden:

1. **¿Funciona de verdad hoy?** Ejecutado, no leído. Por eso `checkpoints/` no
   entra y el wake word sí.
2. **¿Sigue siendo la mejor opción conocida?** Por eso Gemma-4-E2B baja de
   decisión a candidato: su coste de *thinking* incumple el listón de 3 segundos.
3. **¿Cabe en el presupuesto?** Nada de lo heredado lo rompe: el STT son 640 MB en
   CPU, el wake word 3,3 MB, el encoder de router 118 MB.

Y el que manda sobre los tres: **si una pieza exige tocar los invariantes de
arquitectura, no entra.** FunctionGemma es el caso: obligaría a que el catálogo
fuese pesos en vez de datos.

---

## 10. Lo que este mapa no cubre

Para que nadie lo dé por hecho:

- **Los corpus no están inventariados uno a uno.** Son 39 GB en `Probando Gemma 4/data`
  y más en `D:\BAXYRuntime\datasets`. Sé que están y que hay contaminación
  documentada; no sé qué contiene cada uno. El goal que vaya a usarlos tiene que
  mirarlos.
- **La medición de cuantización es un sondeo de 6 prompts, no un corpus.** Sirve
  para rechazar Q2, no para cerrar la fila del goal 06.
- **El wake word se midió con dos ficheros de audio**, uno positivo y uno
  negativo sintético. Basta para decir «funciona y separa»; no basta para un umbral
  de producción ni para falsos disparos por hora.
- **`carter_v5` no se ejecutó.** Se leyeron su arquitectura y sus benchmarks. Es el
  diseño más elaborado del linaje y merece una lectura propia si el goal 07 se
  atasca.
- **El planner completo del router** (ejemplares + abstención + cabeza por
  herramienta) no se pudo ejecutar: importa de `gemma4_agent`. Sólo se ejecutó el
  encoder.

<!-- goal095-12-generated:begin -->
## 11. Reconciliación 09.5 <a id="11-reconciliacion-095"></a>

Actualización **09.5.12**, cerrada 2026-08-31. No borra las fechas ni las conclusiones del Goal 01 (**2026-08-16**): §1–§10 siguen siendo el mapa que los Goals 02–09 leyeron. Este apartado nombra las cuatro clases del linaje reconciliado: herencia previa, delta nuevo, piezas trasplantadas (cero lotes) y rechazos.

# Reconciliación 09.5 — linaje publicado

Generado por `scripts/goal095_09512_integrate.py` desde manifiestos y síntesis. Goal 01 cerrado el **2026-08-16**. No copia secretos, binarios ni corpus privados.

## Las cuatro clases

### Herencia previa

Fuentes ya contempladas el 2026-08-16: `Carter OS AI`, `Probando Gemma 4`, `FunctionGemma`, `BAXY`, biblioteca 1.350 documentos, mapa `00_MAPA.md` §1–§10. Schema Agent se audita en el historial Git de `BAXY`, no como carpeta hermana. `JRVS` y `Probando schemas` siguen fuera.

### Delta nuevo

Manifiesto 09.5.1: 28373 archivos hasheados; cola 19512; duplicados 8348; cobertura previa 513; faltantes 0; solapes 0. Cobertura 100 %.
Llegó material intelectual adicional en los mismos árboles, la etapa Schema Agent dentro de `BAXY`, y la declaración de fuente dispersa (GGUF/datasets/checkpoints de Probando Gemma 4 omitidos a propósito; hashes individuales not invented).

### Piezas trasplantadas

Cero lotes. `pending=0` `claimed=0` `complete=0` `total=0`. Decisión 09.5.9/10: `conservar_actual`. Un trasplante vacío es un hecho medido, no un hueco a rellenar.

09.5.5–09.5.8 no hallaron pieza histórica que gane al vivo en conducta, pruebas, recursos y arquitectura a la vez. Cero reusar_exacto, cero adaptar, cero medir_antes de herencia: unload-on-idle y arranque frío son mediciones de producto del Goal 10.2 sobre el keep-warm/process_lifecycle vigentes, no un vram_manager/Ollama/ui_field que transplantar. Los GGUF/datasets/checkpoints dispersos de Probando Gemma 4 no se nombran para reutilizar (hashes not invented). Cada lote de herencia habría tenido que retirar el mecanismo vivo en el mismo cambio; no hay tal lote. Rechazos protegidos (FunctionGemma en pesos, Qwen-VL R-023, Ollama/servicio Windows, AUTO_APPROVE, soak 24 h como requisito, Gemma-native-audio como oído) no reentran.

### Rechazos

Protegidos (no reentran): `functiongemma-270m-ft`, `qwen-vl`, `ollama-runtime`, `auto_approve`, `soak-24h-as-requirement`, `gemma-native-audio`.

Decisiones 09.5.9 por terminal: {"conservar_actual": 61, "rechazar": 35}.

## Campañas

| Campaña | pending | claimed | complete | total |
|---|---:|---:|---:|---:|
| `docs` | 0 | 0 | 25 | 25 |
| `code_tests` | 0 | 0 | 477 | 477 |
| `evidence_assets` | 0 | 0 | 132 | 132 |
| `transplant` | 0 | 0 | 0 | 0 |

## Hashes de manifiesto 09.5.0 (reproducibles)

- `functiongemma` `ff150df27808ca19c7a80fe40127011ef050be170b83bcd28bacf8d56f619eaa` (match)
- `probando_gemma4` `72f9e5fc6597be5169c99e282d33749d6f7537813fb824809beb85e1b13c7e71` (match)

## Tarjetas 09.5.9 → valor 10/11

| Id | Decisión | valor_10_11 |
|---|---|---|
| `llm_decisor` | `conservar_actual` | 10.0/10.7 comprensión y prosa |
| `cuantizacion` | `conservar_actual` | 10.2 techo VRAM |
| `runtime_inferencia` | `conservar_actual` | 10.0 runtime |
| `encoder_recuperador` | `conservar_actual` | 10.7/03 revalidación shortlist |
| `puerta_abstencion` | `conservar_actual` | 10.7 abstención honesta |
| `catalogo_tipado` | `conservar_actual` | 10.1 corpus / 11 contratos |
| `verificador_identidad` | `conservar_actual` | 10.7 no inventar operaciones |
| `functiongemma-270m-ft` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `gemma4-e2b-qat` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `gemma4-e4b` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `gemma4-26b` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `gemma4-31b` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `qwen3.5-4b` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `qwen3.5-0.8b` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `qwen3-4b-instruct-2507` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `qwen3-8b` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `qwen2.5-7b-instruct` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `hermes3-8b` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `phi-4-mini` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `lfm2.5-1.2b` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `embeddinggemma-300m` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `minilm-l12-tool2vec` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `qwen3-embedding-0.6b` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `bge-m3` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `cross-encoder-reranker` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `ollama-runtime` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `agent-function-schema` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `q2-quant-gemma` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `kva-abstain-head` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `qwen-vl` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `qwen-asr` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `gemma-native-audio` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `wake_word` | `conservar_actual` | 10.11 audio / 10.2 presencia |
| `falsos_disparos` | `conservar_actual` | 10.2 presencia (no retocar 0,5) |
| `ruido` | `conservar_actual` | 10.11 |
| `vad` | `conservar_actual` | 10.11 primera señal oído |
| `stt` | `conservar_actual` | 10.11 |
| `nombres_propios` | `conservar_actual` | 10.11 (aplazado, no bloquea) |
| `bilingue_spanglish` | `conservar_actual` | 10.7 / 10.11 |
| `tts` | `conservar_actual` | 10.11 |
| `primera_senal_oido` | `conservar_actual` | 10.2 / 08 |
| `barge_in` | `conservar_actual` | 10.11 |
| `audio_ducking` | `conservar_actual` | 10.11 |
| `dispositivos_audio` | `conservar_actual` | 10.2 preflight |
| `modelos_assets_voz` | `conservar_actual` | 10.0 / 10.11 |
| `voz_latencia` | `conservar_actual` | 10.2 / 10.11 |
| `voz_recursos` | `conservar_actual` | 10.2 |
| `presencia` | `conservar_actual` | 10.2 presencia diaria |
| `tools` | `conservar_actual` | 10.1 / 10.16 |
| `skills` | `conservar_actual` | 10.16 no es un segundo motor |
| `microagentes` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `uia_ocr_vision` | `conservar_actual` | 10.10 apps/ventanas/visión |
| `adapters_providers` | `conservar_actual` | 10.10 / 10.12 (no hereda allowlist) |
| `planes` | `conservar_actual` | 10.16 misiones |
| `confirmacion` | `conservar_actual` | 10.17 identidad |
| `verificacion` | `conservar_actual` | 10.0 / 11 verificación |
| `steam_media` | `conservar_actual` | 10.12 / 10.16 |
| `archivos` | `conservar_actual` | 10.14 |
| `apps` | `conservar_actual` | 10.10 |
| `navegador` | `conservar_actual` | 10.9 / 10.15 |
| `office` | `conservar_actual` | 10.14 |
| `comunicacion` | `conservar_actual` | 10.15 |
| `sistema` | `conservar_actual` | 10.13 |
| `conectividad` | `conservar_actual` | 10.13 |
| `mision_compuesta` | `conservar_actual` | 10.16 |
| `routers_en_serie` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `listas_hardcodeadas_por_app` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `respuestas_fijas` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `exitos_no_verificados` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `simple-app-open-notepad` | `conservar_actual` | 10.16 C10 |
| `simple-audio-volume` | `conservar_actual` | 10.16 |
| `simple-note-create` | `conservar_actual` | 10.16 / 10.14 |
| `chained-steam-library` | `conservar_actual` | 10.16 |
| `chained-open-then-volume` | `conservar_actual` | 10.16 |
| `historical-carter-v2-compound-smoke` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `runtime_servidor` | `conservar_actual` | 10.0 |
| `carga_descarga_modelos` | `conservar_actual` | 10.2 mide presencia; 09.5.9 no transplanta unload |
| `vram_ram_cpu` | `conservar_actual` | 10.2 |
| `latencia_llm` | `conservar_actual` | 10.2 / 10.7 |
| `arranque` | `conservar_actual` | 10.2 mide arranque; 09.5.9 conserva el vivo |
| `watchdog` | `conservar_actual` | 10.2 |
| `estabilidad` | `conservar_actual` | 10.2 idle corto, no 24 h |
| `field_ui_accesibilidad` | `conservar_actual` | 10.17 |
| `vision_camara` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `memoria_proactividad` | `conservar_actual` | 10.14 |
| `journal` | `conservar_actual` | 10.0 / 11 |
| `setup_publish` | `conservar_actual` | 10.0 |
| `privacidad` | `conservar_actual` | 10.17 |
| `seguridad` | `conservar_actual` | 10.17 |
| `diagnosticos` | `conservar_actual` | 10.2 |
| `auto_approve` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `soak-24h-as-requirement` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `residual_docs` | `conservar_actual` | recordatorio, no lote |
| `residual_code_foreign` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `residual_code_predecessor` | `conservar_actual` | no lote |
| `residual_evidence` | `conservar_actual` | no lote; 10.1 no reparsea 09.5.4 |

Las 9.268 tarjetas de auditoría 09.5.2–09.5.4 viven en `artifacts/goal095/ledger/` y `artifacts/goal095/synthesis/09.5.9_card_assignment.v1.json`. No se copian árboles fuente, GGUF, datasets ni secretos a `biblioteca/`.


Huecos del Goal 01 §10 que 09.5 cubrió sin reescribirlos: corpus y assets tienen terminal 09.5.4 (`parseado_completo` / `binario_inventariado` / `excluido_razonado`); `carter_v5` se leyó en la campaña `docs`/`code_tests`; el planner FunctionGemma sigue rechazado. Lo que sigue siendo medición de producto (unload-on-idle, arranque frío, cascada de visión como política, 200 turnos) no se convierte en lote de trasplante.
<!-- goal095-12-generated:end -->
