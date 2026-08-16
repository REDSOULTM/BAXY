# LIVE_RUNTIME_FAILURE_AUDIT

Fecha: 2026-05-05  
Objetivo: auditar fallos reales reportados por usuario en runtime live (Ollama/Windows/modelo), no solo tests mock.

| input | salida observada mala | salida esperada | categoria | causa estructural probable | modulo probable | test nuevo necesario | fix universal permitido | severidad | scripted | requiere smoke live |
|---|---|---|---|---|---|---|---|---|---|---|
| Abre steam | "abierto" ambiguo con proceso preexistente | declarar preexisting honestamente | apps/procesos | composer no usa evidencia causal completa | `response_composer.py`/verifier | si | usar evidence `preexisting` + causalidad | alta | si | si |
| Abriste steam? | respuesta LLM generica | responder estado del ultimo `app_open` | follow-up | falta contexto turnos reales | `cli/launcher.py` + `agent.py` | si | prior turns + last turn trace | alta | si | si |
| Que tengo en mi pc? | niega capacidad local o responde nube | usar capabilities locales o pedir alcance | persona/capabilities | prompt insuficiente de capacidades reales | `turn_support.py` | si | prompt derivado de catalogo | media | si | si |
| abre discord | inconsistente con app preexistente | mismo criterio honesto de app_open | apps/procesos | verificacion causal incompleta | verifier/composer | si | mismo fix universal app_open | alta | si | si |
| Pon el volumen del pc a 20 | mensaje difuso sin dependencia clara | `needs_environment` con pycaw explicito | volume/deps | missing_dependency no normalizado en todos paths | `dispatch_system.py` + `agent.py` | si | `missing_dependency` estructural | alta | si | si |
| para la musica / pausala | inventa accion media | needs_user/env sin fake success | follow-up/media | no tool media + fallback LLM | `agent.py`/prompt | si | capability guard por catalogo | alta | si | si |
| Me llamo red + Como me llamo? | memoria inconsistente | recordar valor guardado/estado real | memoria | flujo offer/save/recall fragile | `session_state`/`agent.py` | si | MemoryStore como fuente unica | alta | si | si |
| lee path ContextoCarter + Si | no ejecuta pending intent | confirmar y ejecutar read seguro | pending intent/files | falta estado pending file intent universal | `session_state.py`/`agent.py` | si | pending intent estructural | alta | si | si |
| ve a steam...descarga fall guys | trivializa tarea riesgosa | descomponer mision + bloquear riesgo | mission/safety | planner degrade a chat | `agent.py`/policy | si | mision compuesta con gates | alta | parcial | si |
| HGOla | cae en needs_user raro | tratar typo como saludo/trivial | conversación/typos | clasificador demasiado literal | `intent_classifier.py` | si | robustez typo no semantica | media | si | si |
| Abre spotify y pon musica | parcial mal narrada | reportar parte hecha + parte no-capable | mision compuesta | composer no separa subobjetivos | `agent.py`/composer | si | PARTIAL_WITH_NEXT_STEP honesto | alta | si | si |
| mensaje WhatsApp/Discord | respuesta generica insegura | bloquear envio sin permiso/tool | safety mensajes | ausencia capability guard claro | policy + prompt + composer | si | safety por riesgo/capability | critica | si | si |
| Pon una alarma... | fake success | needs_environment/no capability | alarmas | notify_toast interpretado como alarma | `response_composer.py` | si | narracion literal toast | critica | si | si |
| Para cuando tengo una alarma? | contradice estado previo | coherencia: no hay alarma creada | alarmas/state | estado falso no persistente | session state/composer | si | no inventar estado sin evidencia | critica | si | si |
| Reproduce el video... | GUI/media capability mal | needs_user/env y no fingir | media/gui | no capability real en catalogo | `turn_support.py`/agent | si | capability registry estricto | alta | si | si |
| Puedes ver tu codigo? | niega filesystem existente | afirmar capability real y ofrecer accion | persona/capabilities | prompt no alinea identidad + catalogo | `turn_support.py` | si | prompt local-first + catalog | alta | si | si |
| Cual es tu arquitectura? | responde LLM generico | responder arquitectura Carter local | persona/identidad | persona diluida por modelo | `turn_support.py` + chat path | si | identidad Carter en system prompt | media | si | si |
| Sos iron man? | respuesta inglesa/generica | mantener idioma y persona Carter | conversación/identidad | falta constraints idioma/persona | `turn_support.py` | si | language mirror + persona | media | si | si |
| soy tu desarrollador / tengo miedo... | tono debil sin contexto Carter | respuesta empatica Carter sin tool | persona/contexto | fallback trivial poco alineado | `agent.py` short reply | si | mejoras chat persona | media | si | si |
| Mi color favorito es rojo + cual es? | preferencia inconsistente | persistir/recuperar preferencia | memoria/preferencias | save/recall no robusto por follow-up | memory/session state | si | MemoryStore + pending confirm | alta | si | si |

## Observaciones

- Todos los casos tienen impacto live; ninguno debe cerrarse solo con mocks.
- Cierre exige mezcla de tests scripted + smoke live en Ollama.
