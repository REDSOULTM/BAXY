# C03 — relevo de Opus 5 High (2026-09-06)

**C03 EN_CURSO.** No hay 100/100. El WIP propio y el heredado ya **no** están sólo en el
árbol: viven en la rama `Goal-c03` de `origin` (el dueño pidió el traspaso a otro PC el
2026-09-06). `main` sigue en `5f572ee`, sin tocar. Sin tocar pins para salir en verde.
Raíz de origen `c:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo`.
Continuación: `C03_OPUS5_CONTINUACION_METODO.md`.

**El PC de destino no tiene Granite descargado.** El GGUF no viaja por git y tampoco está
en los candidatos de `assets.manifest.json` (que aún nombran Qwen3-4B y gemma-4): Granite
se registró a mano. Sin él no hay panel, no hay tramo D y no hay cierre; sí hay pytest,
.NET y censo, que no lo necesitan. Lo que hay que copiar y registrar está al final de
este documento.

## Candidato (sha256, 16 primeros) — lo demás es heredado de C02/Grok
`llm.py` `f0569f87d070a043` · `request_reading.py` `60b9e8b595976ea1` · `__main__.py`
`5092f2e5c3a89ae9` · `UserMessagePolicy.cs` `5fb71082e7851de8` (era `b0c8baf4b706509d`) · `UserMessagePhrases.cs`
`29ee866bbed09384` · `MainWindowViewModel.cs` `3889ccd755146dcb` · `ModelMessageComposer.cs`
`45cf5cfa6a73b0db` · `FieldUiProbe.cs` `06b0733966ccc24d` · `censo_voz_visible.py`
`a503171e01922ab9` · `pair_conductor_turns.py` `3d6c2bd1126d5eec` ·
`request_reading_cases.json` `66dcd7a6cd663a8a` (92 casos). Granite 4.2 3B Q4_K_M
registrado, gguf `e0406663`, sin `BAXY_MIND_LLM_GGUF`. Trampa: el conductor arranca
**Release** (`Directory.Build.props` → `BaxyDevelopmentConfiguration=Release`); un
`dotnet build -c Debug` no llega a la corrida (`seguimiento-8` no midió nada).

## Comprobado con corrida propia
1. **Seguimiento elíptico.** Causa real: todo turno conversacional degradado llega al
   compositor con `{"kind":"conversation","polarity":"success"}` y nada más. Reparado con
   `is_elliptical_followup`/`request_topic`/`followup_topic` y `priorRequests` desde el
   shell. De **0 de 9** en tema (`seguimiento-3`) a **7–9 de 9** (`seguimiento-11`, `-13`,
   `-14`). Detalle en `SEGUIMIENTOS.md`.
2. **Censo de prosa visible** salta docstrings vía `ast`: censo **0**.
3. **Capacidades y límites** se leen por forma, no por frase, y nunca se aclaran
   (tres salidas cerradas: aclaración explícita, decisión final, recuperación).
   `limites-22/`: **8 de 9** fieles, cifra exacta leída una a una.
4. **Falso veto reparado**: la respuesta correcta del catálogo se rechazaba como
   `unsolicited_catalog` y el turno moría agotado (`limites-18/006`).
   `RequestReadingConformanceTests` compara ahora las dos lecturas sobre el corpus.

## Provisional (verde en pytest, sin panel completo)
Exención «las palabras del pedido no son vocabulario del encargo»
(`compose_visible_defect`, `repeats_a_sent_instruction`); `nothing_to_clarify` con
`continue_constraint`; `answered_with_a_question`; «una explicación no es una pregunta».

## Esa prueba roja ya está en verde (2026-09-06)
`AcceptingTheConstraintInThePersonsOwnWordsIsNotVetoed` **pasa**. El veto era
`ContainsInternalCode`, entrada literal «keep talking» (`UserMessagePolicy.cs`), que
miraba sólo la respuesta y nunca el pedido. La mente ya tenía la exención desde
`limites-19/009` (`llm.py`, `prompt_echo`: «lo que dijo la persona no es una instrucción
interna aunque la instrucción lo repita»); el shell la ignoraba y volvía a matar el mismo
borrador que ya se había publicado seis veces en `limites-22/t9`.

Reparación: las nueve frases de encargo —`name the pc network`, `pc network name`,
`in one short sentence`, `stay in the conversation`, `keep talking`,
`received the instruction`, `not yourself`, `do not introduce yourself`,
`do not describe presence`— y el prefijo `name the ` pasan a `InstructionEchoPhrases` y
sólo vetan cuando la persona no las escribió, igual que `LeakedInternalTerm` con los
términos prohibidos. Los marcadores de máquina —snake_case, identificadores con punto,
`<think>`, `status: success`, `el mensaje es`…— siguen siendo absolutos, y
`set the clock` y `respond in english as` se dejaron **fuera** de la exención por ser
órdenes y no vocabulario.

El lado contrario se exige en prueba nueva,
`TheSameInstructionWordsAreStillVetoedWhenNobodyAskedForThem`: esas mismas palabras
siguen dando `internal_code` cuando el pedido no las lleva. Sin ese lado la regla sólo
sería una lista más corta.

`RequestReadingConformanceTests.cs` `4d2de6ef9672eb07`. **Falta el panel**: la reparación
está probada por owner, no medida sobre Granite.

## Otros fallos pendientes (panel completo más reciente: `panel-opus-13/`, 78 turnos,
75 publicados, 2 agotamientos, 1 silencio, ~75 % fieles —estimación—, `ADJUDICACION.md`,
anterior a las reparaciones de límites)
- Seguimiento en tema que repite la definición: `panel-opus-13/020`, `/022`. C05/C06.
- Saludo mal formado «Hello hi!»: `panel-opus-13/001`, `/003`, `/004`.
- Persona impersonal «se puede abrir…»: `panel-opus-13/029`.
- Fuga de contrato: `panel-opus-13/040`; `/044` reparado sin panel que lo confirme.
- Agotamientos y silencio: `panel-opus-13/056`, `/062`, `/010`.

## Hipótesis descartadas (no repetir)
Turno anterior como contexto (`panel-opus-4/-5`); muestreo 0.2/0.9 (`panel-opus-6`);
forzar la ruta contextual (`seguimiento-3`, cuyo diagnóstico era falso); prohibir la
definición en un seguimiento (`seguimiento-12` contra `-11`: de 9 en tema a 6). Las cuatro
revertidas y anotadas en el código donde vivían.

## Validación recogida
- pytest con el intérprete del manifiesto
  (`%LOCALAPPDATA%\BAXYRuntime\python\mind-runtime-v1\Scripts\python.exe`), sobre los sha
  de arriba: `test_request_reading.py` **177 pass**; `-k "turn or planner or compose or
  reading or policy or goal06"` **1853 pass, 101 subtests**.
- .NET Integration completo: **2922 pass, 1 skip**, anterior a la prueba roja.
- **Full: NO VERIFICADO para este candidato.** Último intento `scratchpad/full_gate8.txt`:
  todas las etapas verdes (dotnet-format, build-release, 60+2920+138+451+477, ruff,
  compileall, eslint, tsc, censo 0) salvo `test_stt_quality_evaluators`, por deriva del pin
  `EXPECTED_PROGRAM_TREE_SHA256` al editar durante la corrida. El pin **no** se refrescó al
  cerrar: refrescarlo con su nota (corpus, motores y hashes STT/TTS/wake no cambian) y
  relanzar Full.
- Procesos: ninguno vivo (`Baxy.exe` y `llama-server.exe` ausentes). Un bucle de espera
  propio (`b9qahado5`) quedó **INTERRUMPIDO**, sin efecto sobre el producto ni efectos
  pendientes de observar.
## Siguiente clase, ya diagnosticada y sin reparar: el saludo mal formado
`panel-opus-13/001`, `/003`, `/004` — «Good afternoon» → «Hello hi!». Leído en
`panel-opus-13/paired.json`, es determinista y **no** es generación de C05/C06:

1. `llm.py` fija `payload["greeting"] = "hi" if language == "en" else "hola"` para todo
   turno que salude, sin mirar con qué saludó la persona; el prompt de bienvenida dice
   «One sentence with situation.greeting», así que el modelo pega el literal.
2. En `t1`/`t4` el primer borrador era **bueno** —«Hi! How can I help you today?»— y lo
   tiró el veto `welcome_question`, que perdona el «?» sólo si el pedido y la respuesta
   empiezan por `hola|hi|hey|hello|buenas`. «Good afternoon» y «Good evening» no están en
   esa lista de prefijos, aunque `read_request` ya los lee como saludo (`reading.greets`
   es cierto: por eso hay `greeting` en el payload). En el reintento sale «Hello hi!».
   En `t3` («Hi again») el primer borrador cayó por `lowercase` y el reintento dio
   «Hello hi.».

Hipótesis a probar, una variable causal por comparación: que el veto lea el saludo por el
owner (`read_request(...).greets`) en vez de por la lista de prefijos, y que el payload
lleve el saludo de la persona en vez del literal fijo. Owner primero: es determinista y
no necesita Granite. Panel después.

## Siguiente acción concreta
1. Reparar el saludo por owner y fijarlo en pytest/.NET (no necesita Granite).
2. `panel-opus-14` sobre `panel-opus-13.turns.jsonl` — misma población, para medir juntas
   la exención de encargo copiado y el saludo. **Requiere Granite en la máquina.**
3. Sólo con el panel fiel, congelar la población v19 y correr el tramo D. Congelarla
   antes la quema como población fresca.

## Lo que hace falta en el PC de destino para poder medir
El árbol y los artefactos vienen enteros en `Goal-c03`. Lo que no viaja por git:

| Pieza | Ruta en el PC de origen | Tamaño | SHA-256 |
|---|---|---|---|
| `granite-4.2-3b-Q4_K_M.gguf` | `D:\BAXYRuntime\assets\models\` | 2,09 GB | `e0406663965846ae22a403456eb826ccce5f450840491f71952f18a7cb78e7d5` |
| `llama-b9980-cuda12.4\llama-server.exe` + sus DLL | `%LOCALAPPDATA%\BAXYRuntime\assets\` | 1,14 GB | `38a9d28ea414442590486459a7d1f5e32655db83148b7a114b79cd1ad242946e` |
| `sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8` (STT) | `%USERPROFILE%\.gemma4\models\` | 640 MB | `5a70e0862ca0ed713a2bb1bfd50bf4886ae027815c8634a3800da7bdec6ab28f` |

Granite **no** está en los candidatos de `assets.manifest.json`, así que `bootstrap.ps1`
no lo encuentra solo: se declara a mano, y el manifiesto resultante
(`%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json`) debe quedar con
`gguf_sha256` = `e0406663…` y `python_path` apuntando al `src` de **este** clon.

    .\scripts\register_mind_runtime.ps1 -Gguf '<RAIZ>\models\granite-4.2-3b-Q4_K_M.gguf'

No pongas `BAXY_MIND_LLM_GGUF`: el candidato se midió sin ese override, y un runtime
reproducible sin override es criterio de cierre de C03. El resto del arranque de una
máquina limpia está en `documentacion/sprints/00_ARRANQUE_PC_NUEVO.md` (su tabla nombra
todavía Qwen3-4B como decisor: para C03 el GGUF conversacional es Granite, y esa
expectativa está registrada en
`artifacts/runtime/registered_runtime_expectation_r281.json`).
