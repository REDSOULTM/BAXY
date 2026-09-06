# C03 — relevo de Opus 5 High (2026-09-06)

**C03 EN_CURSO.** No hay 100/100. Nada publicado; el WIP propio y el heredado siguen en
el árbol sin commit. Sin tocar pins para salir en verde. Raíz
`c:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo`, rama `main`, HEAD `5f572ee`
(sin commits nuevos). Continuación: `C03_OPUS5_CONTINUACION_METODO.md`.

## Candidato (sha256, 16 primeros) — lo demás es heredado de C02/Grok
`llm.py` `f0569f87d070a043` · `request_reading.py` `60b9e8b595976ea1` · `__main__.py`
`5092f2e5c3a89ae9` · `UserMessagePolicy.cs` `b0c8baf4b706509d` · `UserMessagePhrases.cs`
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

## Fallo abierto, con prueba roja escrita a propósito
`tests/Baxy.Integration.Tests/RequestReadingConformanceTests.cs` →
`AcceptingTheConstraintInThePersonsOwnWordsIsNotVetoed` **FALLA** (`internal_code`). Es
caracterización, no regresión: el compositor ya publica «I will keep talking without
launching anything.» (`limites-22/t9`, seis veces `pub=True`) y el veto del shell la tira,
así que el turno acaba `composition_failed`. Falta ver qué condición de
`ModelResponseRejectionReason` la marca (`LooksLikeMachineSlotAsk`,
`ContainsPersonMetadiscourse`, `HasRepeatedWord`, `ContainsInternalCode`).

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
## Siguiente acción concreta
Poner en verde la prueba roja identificando el veto exacto; después `panel-opus-14` sobre
`panel-opus-13.turns.jsonl`; y sólo con el panel fiel, congelar la población v19 y correr
el tramo D. Congelarla antes la quema como población fresca.
