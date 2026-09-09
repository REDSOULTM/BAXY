# C03 — checkpoint374/375 — EN_CURSO — 2026-09-08

Goal completo activo; Goal-c03/HEAD2bf3d4c. Preservar WIP/main/evidencia. Sin agentes,
commit/push/Full durante reparación. BAXY manual cerrado; ningún producto/modelo/test
activo. Encuesta742/rev1248 intacta; servidor101140 disponible.16mensajes directos
consolidados, automáticos excluidos. No otro goal. HISTORIA: CHECKPOINT_369_ANTES_374.md,
PREVIOUS_CHECKPOINT y RESULT/PINS de cada tramo. No repetir descartes.

## Fuente vigente y validación

App369: Invalid reutiliza CreateMemoryConfirmationPrompt de misma invocación; conserva
acción/avisos de exportación. En reconciliación incierta, sólo confirmación y acción
pública, nunca argumentos/IDs/tokens. Tests3AppFlow ampliados. Baseline3fail38s;
focal3pass49s; dueñas memoria1926pass0skip4m44s;Fast18,13sverde0warnings/errors.
RESULT/PINS369. Baseline de preparación tuvo variable en otro test, separado.

Python374: _PRESENT_STATE_CLAIM ya no trata cualquier posesivo como estado del PC.
_OBSERVED_MACHINE_CLAIM marca owned_device usando sus sujetos ya existentes y mantiene
rechazo de estados del equipo; cero nombres/lista nueva/prompt. Tests5hechos personales
más chat373 y2estadosPCsin lectura numérica. Baseline6fail45pass2,14s;focal51pass0skip0,71s.
Dueñas1104pass0skip5,43s (turn_policy/compose_contract/llm_transport/price_v8).
Fast3,25sverde0warnings/errors. Initialowners1fail1103pass sólo pinsdeprogramasactuales
V8; seisartefactos+aritmética+veredicto intactos, hashes actuales actualizados con causa.
RESULT/PINS374. Última.NET369, no Full. No cambios tras estas comprobaciones.

## Resultados integrados / diagnósticos

362roles nativos(selector historial12mensajes/6000chars) llevó363a7/7;364generalización
10sintéticosES/EN→3/10+1silencio.365unedeclaración+save explícito;3663/10+1silencio.
369contextoconfirmación lleva370a4/10+1parcial+1silencio, mismo panel366. Inglés explica
activar memoria; español identifica acción pero eco parcial. Cancel no habilita ni
guarda (journal status +2savefail+2recallfail). T3idioma,T8alcance,T5silencio,T9/T10
confunden persistencia y conversación. RESULT/PINS370. No UI/voz/humanos frescos.

367pendingAction/368tambiéncausa:baseline2/4→3/4+1parcial; no más variantes semejantes.
371añadir historial completo al compositorerror2/5→2/5;372sólohumano2/5→2/5.
Rechazados, no fuente. No repetir variantes de historial/prosa de error.

373 pregunta a mente completa antes de forzar ruta privada, catálogo Core169actual,
no ejecución:1/5útil. HTTP1/9 ya responden Your name is Jordan; la guarda rechaza
por your+name+is; HTTP2/10 reintentan sin historial y borran el dato. Primera pérdida
reproducida pura: visible_reply_asserts_an_unread_machine_state=True, demásguardasfalse.
374 corrige esa causa.375 mismos5casos→3/5útiles:Jordan,tercero,conflictohumano/asistente.
T10 español aún añade no puedo recordarlo automáticamente en esta conversación;
persistencia explícita dice no tener acceso a memoria privada. RESULT/PINS372/373/375.
Todosloshandlescerrados:10711/55117/55842/47568/47763 y anteriores.

## Próxima decisión — todavía sin implementar

No cambiar parser sólo porque la mente mejoró3/5. La App sigue forzando memory.recall
para preguntas genéricas como What is my name / cómo me llamo (NaturalMemoryRequestParser
~765/900; MainWindowViewModel~750), antes de consulta contextual. Compositorerror no
conoce historial; añadirlo371/372 fue insuficiente. Reintentochat llm~6650 también
pierde historial: defecto separado, no arreglado por374. ConfirmaciónES/cancelidioma
(cancel sin evidence lingüística se clasificaes)/alcancecancelación siguen abiertos.

375T10 selector nativo primero dice Eres Álvaro / Te llamas Álvaro; luego chat añade
limitación falsa. Native selection descarta content por diseño: llm._post_native_tool_selection
~5900 retorna sólooperaciones; NATIVE_TOOL_POLICY_PROMPT458 exige una etapa separada.
No reutilizar texto como respuesta sin medir su contrato/guardas/idioma. Esa doble
etapa es una candidata a revisar, no cambio decidido ni promptadoptado.

373/375 persistencia: catálogo incluye11memory.*, pero shortlist primario28 no incluye
ninguna. No culpar al GGUF por herramientas ausentes. Investigar PlannerCatalog.shortlist
src/baxy_mind/planner.py:371 y _turn_operation_contract/__main__1958, construcciónshortlist
5918; _catalog_answers_the_request2016 sólo4. Core catalog se obtiene vía helper heredado
scripts.measure_mind_budget.current_core_catalog_snapshot, sin efectos. Aún no causalidad
explicada de esa omisión. No fuente376 ni script376 preparado.

## C03 íntegro pendiente

Ocho rutas, fallos264 y742requisitos (0validaciónindividual registrada),100freshhuman
(0certificados/0congelados,204por auditar335), averías/recuperación, escritorio real,
voz física/ASR/recursos conjuntos≤4GBVRAM, runtime/instalación, continuidadC04–C09sin
susgoals, Fullfinalenteroverde y publicaciónfuera de main. Prosa fija sinchallenge seguro
en MemoryTurnSession.SendPreparedAsync pendiente. Ningún bloqueo externo ni cierre.
Modelo Qwen3.5 sigue override diagnóstico, registro2507 intacto. Mismahashmodelo00fe…11a4,
manifest13b971…d1ed. Recursos históricos no prueban vozconjunta/mínimo/VRAMexclusiva.
