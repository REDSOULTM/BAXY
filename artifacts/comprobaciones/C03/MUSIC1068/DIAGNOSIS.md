# MUSIC1068 — pausa, propuesta externa

Base 44aa529da3b9df6cad0f193fcbfa60cbf71e658c. Herencia exacta: MUSIC1065 segmentos 08/09; hashes de los ocho archivos consultados en IDENTITY.json. No se reconstruye una ejecución desde el estado posterior de la cola.

| Caso | Primera pérdida observada | Evolución posterior |
|---|---|---|
| 9, music1037-dev-02 | run-09/turn-audit.jsonl, request_id 8: media.control ausente entre 28 candidatos; raw conversation/knowledge, cero operaciones; explicit_contract no recupera control. | conversation_presentation termina unsupported. raw-replies conserva «I cannot pause the current track for a moment as requested.»; compose t1 recibe cause outside what I do y publica «I can't pause tracks on this PC.» |
| 8, music1037-dev-01 | run-08/turn-audit.jsonl, request_id 8: media.control ausente; raw propone media.play.query; explicit_contract conserva esa operación equivocada. | domain_grounding retira play.query; respuesta unsupported «No puedo dejar en pausa lo que está sonando.» |

Las rutas anteriores pertenecen a C:/Users/usuario/AppData/Local/BAXY/C03-music1065-proposal/private/. La ausencia en recuperación es observada; la razón interna de puntuación lexical no está capturada. La discrepancia determinista sí es visible en fuente: effect_intent.py:11902–11945 exige vocabulario audio/media/música para transporte; el fallback :11960–11978 reconoce sonando/playing pero omite track/pista y exige cabeza pausa/stop, excluyendo el estado solicitado con dejar en pausa. No se atribuye el avance automático a BAXY.

## Cambio mínimo

DIFF.patch modifica sólo ese fallback, reutilizando vocabulario de objetos canción/song/pista/track que ya existe en navegación multimedia :11989. Incorpora el predicado verbal dejar en pausa bajo su cabeza correspondiente; conserva evidencia original y _append (:6966) con veto de negación local. No añade otro selector, nombres de pistas, respuesta visible ni proveedor.

El caller de selección __main__.py:6254 usa el contrato explícito cuando existe; su binder _explicit_media_control_arguments :4310–4355 ya distingue pause y pausa y exige una sola acción. No necesita cambiar main ni llm. «For a moment» no se convierte en duración ni reanudación automática: esta propuesta sólo conserva el pedido de pausa y el contrato existente.

## Revisión estática y límites

Permanecen los filtros globales de solicitud directa, cita/meta, futuro, otra máquina y coordinación contradictoria (resolve_explicit_effects :14047–14093), además de exclusión de alarma/grabación/micrófono en el propio fallback. Un nombre de pista sin una orden de transporte no gana autoridad. Negaciones siguen pasando por _append; no se elimina el cuerpo de la petición. El parche no hace que un control verifique por sí solo el estado ni garantiza una composición útil.

Compatible por hunks disjuntos con 1067: éste cambia autoridad de resume en :7069 y :8006; 1068 sólo :11960–11978. Ambos derivan de la misma base. Sin cambios canónicos, importaciones, AST, pruebas, build, Core, GPU ni efectos; revisión manual del diff únicamente. Siguiente medición corresponde a raíz sobre las dos variantes originales de pausa, con sesión propia observada vigente. Cero créditos otorgados aquí.
