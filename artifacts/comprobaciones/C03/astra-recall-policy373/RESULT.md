# recall-policy373

Mente completa:1/5 útil (tercero). T5/conflicto pierden Jordan; T10 añade falsa limitación de memoria; consulta explícita de persistencia niega una capacidad disponible. No se ejecutó operación ni se cambió parser. Primera pérdida T5: HTTP1 responde Your name is Jordan, guarda _PRESENT_STATE_CLAIM rechaza your+name+is; HTTP2 reintenta sin historial y responde desconocimiento. Igual HTTP9→10 en conflicto. La guarda, no ese primer modelo, creó esos errores. Catálogo169 contiene11memory.*, pero HTTP12 preselecciona28 operaciones sin ninguna memory.*; investigar shortlist antes de culpar al modelo por la capacidad ausente.

## t5 / turn.decide

> I don't know your name.

## t10 / turn.decide

> Tu nombre es Álvaro, pero como no tengo acceso a tu memoria privada, no puedo recordarlo automáticamente en esta conversación.

## third-party / turn.decide

> I don't know your name.

## assistant-conflict / turn.decide

> I don't know your name.

## explicit-persistence / turn.decide

> I don't have access to your private memory or saved names.

