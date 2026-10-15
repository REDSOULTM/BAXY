# Pendientes de la ronda 5 (computer use v3)

Integración `fable/cu-v3-ronda5` sobre `fable/cu-universal-v3` (rondas 1–4 y `uia-sin-frente`). `PROGRESO_V3.md` es
del líder y queda en la versión de la base. Informes de las ramas: `%LOCALAPPDATA%\BAXY\cu-v3\r5i\<rama>.json`;
análisis de origen: `%LOCALAPPDATA%\BAXY\cu-v3\r5a\*.md`. `fable/cu-v3-regr5` (Steam/Spotify/Discord/Calculadora, de
otro agente) no se fusiona aquí: la fusiona el líder.

## Fusiones y conflictos

Orden: elevacion-finales (`7800a4a0c`), destino (`7524510c4`), descomponer (`1df99b9d2`), semantico (`3b50b1484`),
todas `--no-ff` y todas sobre `17886882e` (anterior a la ronda 4).

- `tests/test_cu_live_estados_v3.py` (elevacion contra la ronda 4): las dos partes añadían tests al final; quedan los de
  la base (medidor, repetir, turno) y después el del arnés que abre sin elevar.
- `src/baxy_mind/computer_use.py` (semantico contra descomponer), en `_decide_step`: descomponer añadía las pistas de
  ruta (`route_hints`) a los nombres que ordenan la vista y semantico los parecidos E5 (`_similar_controls`, línea
  «Parecidos al objetivo»). Quedan los dos: `names` = nombres del lugar + ruta, `similar` = parecidos. Son señales
  distintas (etiquetas del camino pedidas al modelo cuando se atasca; vecinos E5 del objetivo en la vista), no una
  copia.
- Sin conflicto de texto pero roto: ver «una sola lectura de la app de la conversación».

## Duplicados (ley 2)

- **`conversation_application` estaba dos veces** en `semantic/missions.py` (descomponer la sacó de
  `follow_up_in_application`; destino escribió la suya para el destino). La segunda tapaba a la primera y
  `follow_up_in_application` y la puerta de cobertura la llamaban con la otra firma (TypeError). Queda una, la de
  destino (resolvedor único), con las dos reglas de corte que sólo tenía la otra (fijadas en
  `test_cu_v2_seguimiento_en_la_app`): con las operaciones disponibles, una orden que sirve una operación tipada
  propia corta la herencia (era el pendiente de destino) y un pedido que abrió dos apps no nombra ninguna. Commit
  `1162a5902`.
- La lectura «app enmarcada al frente con hasta tres palabras más» estaba copiada en `_question_in_place` y
  `application_question`: `_head_application`.
- **Resolvedor de app:** uno, el de destino (`said_application` / `mission_destination` / `place_application`). El
  `_named_precisely` que usan las preguntas sobre una app de descomponer es el del lector de misiones de la base, no
  uno nuevo. El E5 de semantico (`semantic/cu_semejanza.py`) empareja el objetivo con los controles de una vista, no
  la app; el gancho `similar` de destino para nombres de app en otro idioma sigue sin cablear (nadie lo llama).
- **Ir al motor:** la puerta de cobertura (`_engine_for_an_unserved_order`) es la capa única tras `turn.decide`. Queda
  una segunda llamada a `_order_served_elsewhere` dentro de la ruta del decisor (ronda 3, antes de la puerta): misma
  función, y la puerta vuelve sin tocar el turno cuando ya es `mission.computer.use`, así que no actúa dos veces. Probé
  quitarla: `test_cu_v3_cobertura` fija esa conversión llamando sólo a la ruta del decisor (con su etapa
  `served_elsewhere` en el audit), así que no la quité en la integración. Unirla es mover esos tests a la puerta.
- La conversión de una charla por «escribir que nadie pidió» en una orden dentro de una app (v3-27, descomponer) es
  otra entrada al motor, pero de un caso que la puerta no ve (la puerta no mira `talk`).
- `_prior_user_requests` (destino) y `_prior_user_texts` (base) son casi iguales: la de destino quita siempre el último
  turno de la persona porque en un paso de plan la evidencia no es el mensaje. No las uní (15 llamadores de la base).

## Seguridad extra

Sin aplicación resuelta, el gemelo de destino (`NoApplicationWrites`: ni teclas ni texto en una ventana que la misión
no abrió ni le resolvieron) pasa a cubrir también clic, scroll y arrastre: `NoApplicationActs` en
`ComputerUseMission.BindToMissionWindow`; t-menu-1 hacía clic derecho en la ventana de la persona. Para con
`computer_use_no_application` («no toqué la ventana de delante; decime en cuál»). Contracaso: si la persona nombra esa
ventana («en esta ventana …», «en la ventana activa/actual/de delante …», «in this/the active window …»; fuera de un
texto dictado y sin app enmarcada), la mente pone `frontWindow: true` (nuevo booleano del esquema de
`mission.computer.use` en `ProductCatalog`) y la ventana de delante es el destino. Tests: C#
`WithNoApplicationResolvedNothingIsDoneInThePersonsWindow`, `WithNoApplicationTheWindowInFrontIsTouchedOnlyWhenThePersonNamedIt`,
`WithNoApplicationAClickOnThePersonsWindowIsNotSent`, `ProductCatalogTests` (frontWindow); Python
`test_cu_v3_destino.py` (las dos tablas de `frontWindow`).

Límite: «entrada reciente de la persona» por ventana no existe en el provider; el sustituto sigue siendo «ni la abrió
la misión ni se la resolvieron». Riesgo visto y no tocado: la rama `clarify_in_application` de la puerta no mira si el
turno era habla captada (M123, `overheard`); el decider route convierte esa habla en `clarify`, y la puerta podría
pasar ese `clarify` al motor si lo dicho es una orden dentro de una app.

## Validación

Sin suite completa ni Full:

- `dotnet build src/Baxy.App -c Release`: 0 errores, 0 avisos; `dotnet publish src/Baxy.Core -c Release -r win-x64`:
  0 errores.
- pytest (mind-runtime-v1, `PYTHONPATH=<worktree>\src`, `-X utf8 -p no:cacheprovider`): `test_computer_use*.py
  test_cu_*.py test_compound_missions.py test_reading_lives_in_semantic.py test_censo_voz_visible.py
  test_compose_contract.py test_c03_inventory_output_budget.py test_c03_process_scope_prompt.py test_c03_m1*.py
  test_router.py` → **5295 passed**, 6 subtests; los 63 ficheros cuyo nombre lleva decider/dialogue/compose/uso_real/
  catalog/app_open más los que citan los informes (turn_policy, planner, mind_budget_gate, sidecar_lifecycle,
  reopen1993_*, effect_intent, m77, m128, m143, m155, m167, semantic_audit_1993, prose_projection, cpu_prose,
  pointless_questions, seguimiento_en_la_app…) → **8236 passed**, 121 subtests; `test_turn_latency.py -k model_call`
  → 2 passed. 0 skips.
- `scripts/inventory_reading_outside_semantic.py --check`: exit 0.
- `dotnet test tests/Baxy.Integration.Tests -c Release --filter "…ComputerUse|…OperationFloor|…M107|…MindShellEndToEnd"`:
  593 tests; 590 en la corrida final y los 3 restantes
  (`IndependentRequestSupersedesUnstartedConfirmationWithoutReclassifying`, ~45 s cada uno, con pytest corriendo a la
  vez) pasan solos (7/7). La primera corrida dio 587 + los 6 casos que fijaban que el clic sin app iba a la ventana de
  delante, cambiados con la seguridad extra.
- `tests/Baxy.Kernel.Tests`: **364/364**; `tests/Baxy.Contracts.Tests`: **70/70**.
- `tests/Baxy.Providers.Windows.Tests --blame-hang-timeout 120s`: **1415/1416**. El rojo,
  `UserInputPauseTests.EveryInjectorUnderSrcCarriesBaxysMark`, viene de la base (`uia-sin-frente`, `f56793c06`), no
  de esta integración: `SendBid` en `DesktopUiaWorker.ps1:663` marca su registro con la constante `BaxyMark`, que el
  censo no reconoce (`MarkMention` = `BaxyInputMark.Value|0x42415859|\bMark\b`), y
  `ComputerUseClickMethodTests` fija el texto `keys[0].Extra = new IntPtr(BaxyMark)`. Los dos tests de la base se
  contradicen; no lo toqué (la rama `regr5` trabaja en el worker).

## Verificación en vivo pendiente

Nada de esta ronda se probó en el escritorio. Además de lo que listan los cuatro informes `r5i`:

- t-menu-1 y t-form-4 sin app: ningún clic ni tecla en la ventana del usuario simulado; paro
  `computer_use_no_application`.
- «en esta ventana escribí hola» con el Bloc de notas delante: escribe ahí (`frontWindow`), y con BAXY o VS Code
  delante sigue `computer_use_window_protected`.
- Una misión sin app que antes acertaba con un clic en la ventana de delante ahora para y pregunta en cuál: medir cuántos
  casos del banco cambian así.
