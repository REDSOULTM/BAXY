# CLARIFY1044 — el historial bruto impide alcanzar el aclarador

ROOT_ADJUDICATION1044:25casos completos,6pass19fail0créditos. Heredados DIAGNOSIS1006 y propuesta1044; no se repite análisis global ni se atribuye toda la categoría a este fallo.

## Primera pérdida de los not_complete

H0694/request8 y clarify1043-dev-03 («margen aproximado.»)/request75 registran knowledge, cero efectos, action_grounding conservado, conversation_effect_shape=not_complete y conversation_presentation=unsupported. Sus raw chat ya son negativas: «No puedo trabajar como se pidió.» / «No puedo determinar el margen aproximado tal como fue pedido.»

La nueva rama exigía `and not history`, pero ese no es el contrato del producto:

1. MainWindowViewModel.cs:710 llama BeginTurnPresentation antes de decidir. :236–238 añade el mensaje actual a Messages como usuario.
2. BuildMindHistory:2381–2397 copia esos Messages, incluido el turno actual, y puede incluir la bienvenida de session.new.
3. :2060 pasa ese historial a DecideMindTurnAsync; MindSidecarClient.cs:468–484 lo serializa íntegro como history.
4. __main__.py:5852 conserva message.history. Así una sesión nueva carece de antecedente pero NO tiene un contenedor vacío.
5. El raw `history_users=0` no contradice esto: llm.chat:6867–6880 primero quita el usuario actual al construir su historial de presentación, y el contador se calcula después. Es otro objeto/instante.

Por cortocircuito, history no vacío basta para impedir la llamada al aclarador y a _recovery_question_is_valid en esa rama. No es evidencia de que el aclarador generara una pregunta rechazada: nunca pudo alcanzarse con esa condición. Las trazas no capturan cada booleano ni el payload completo original; esta conclusión combina el estado registrado con la construcción concreta del mensaje en fuente, no inventa un valor de pregunta faltante.

## Parche mínimo externo

HISTORY_GATE.patch, un owner __main__.py: reemplaza la comprobación del contenedor por `_previous_user_request(history, objective) is None`. Ese helper existente (:2669) excluye el turno actual si coincide y busca un usuario anterior real; no redefine historia ni borra mensajes. Añade paso de pendingClarification del contrato y `_history_has_pending_clarification` existente: el bool del shell manda; si falta, conserva el fallback legado. La bienvenida sola no se trata como aclaración pendiente cuando el contrato explícito dice false.

Todos los demás filtros, el audit not_complete, catálogo, validación de pregunta y cero efectos quedan intactos. Esto corrige una condición inalcanzable, no declara útiles las preguntas futuras ni elimina los riesgos de calibración not_complete. Otro filtro podría seguir descartando un caso: medir subset afectado tras integración con1046, no repetir25casos. No prueba arreglo de cinco casos ni30abiertos.

## H0271 es otra pérdida, en dos owners

H0271/request14 tiene raw knowledge. Primer intento genera «¿Qué tipo de potencial de rendimiento te refieres? Por ejemplo, en un proyecto, un equipo o algo más específico?» y falla PlannerContractError/turn_preparation _prepare_turn_result:6752 por el veto de explicación formada sólo por preguntas. No fue el gate not_complete: el intento completo posterior registra no_effect.

Segundo intento genera «¿En qué contexto o área estás hablando de "potencial de rendimiento"? (por ejemplo, trabajo, estudios, deporte, tecnología, etc.)». El audit de mente final conserva esa aclaración visible como conversation/knowledge; por tanto sí salió de Python. capture/events.jsonl:42 registra posterior mindReplyRejection=echoes_request; shell-trace t2 después de decision.ready=conversation entra a compose y publica la definición genérica que raíz rechazó.

UserMessagePolicy.cs:1297–1305 declara eco si el pedido normalizado tiene≥10 caracteres, la respuesta contiene? y contiene el pedido entero. Eso confunde citar el tema para pedir el contexto faltante con devolver una pregunta autocontenida sin contestar. Es una segunda transformación errónea, separada del veto Python. No se corrige aquí cambiando palabras o prohibiendo repetir «potencial de rendimiento»: hace falta distinguir contrato de aclaración necesaria y contrato de respuesta ya contestable. El primer veto y el segundo deben revisarse por ownership, sin desactivar globalmente protecciones contra eco. HISTORY_GATE.patch no los modifica ni promete rescatar H0271.

## Entrega

HISTORY_GATE.patch + __main__.py.PROPOSAL + IDENTITY.json. Revisión textual completa, una iteración. Ninguna ejecución de helper, imports de producto, AST, tests, build, GPU, fuente canónica, registro o adjudicación. Patch para raíz después de la tanda activa, no candidato ejecutable ni autorización de nueva corrida.
