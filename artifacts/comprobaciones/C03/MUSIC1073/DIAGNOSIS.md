# MUSIC1073 — reanudación del contenido cargado

Fuente medida/base fb4d5c528b64517daf5866efefb90bcdf0798a9e. Sólo propuestas externas effect_intent.py y __main__.py; llm y1072 intactos. H0110 ya pasó en MUSIC1071; aquí se estudian únicamente sus dos variantes.

Evidencia exacta: C:/Users/usuario/AppData/Local/BAXY/C03-music1071-proposal/private/run-06 y run-07. ES request8: media.control falta entre28 candidatos; raw streaming.play.named pasa explicit_contract y domain_grounding lo retira. raw-replies conserva la incapacidad declarada; no hubo media.control. EN request8 termina directamente explicit_clarification, intent_operations=[media.control], cero efectos; final observado por raíz pregunta la app. Los hashes se conservan en IDENTITY.json.

ES primera discrepancia estática: seguir/seguí no forma parte de la autoridad de reanudación ni de resume_existing_media (:11786). La selección no rescata la operación existente. Reparar sólo eso es insuficiente: _explicit_media_control_arguments en main:4332 considera el sustantivo «pausa» una acción pause y no reconoce seguí como play.

EN primera discrepancia: named_resume_without_provider (:2509–2526) exige source_app ante resume…where…stopped incluso cuando el objeto es track, que el control SMTC puede resolver en la sesión actual. No necesita que el conductor invente una plataforma; si falta sesión real el proveedor debe informar ese resultado.

## Cambio

Se extrae _resume_existing_media a función compartida y se retira su bloque inline anterior. Reutiliza los dominios multimedia ya presentes; añade las flexiones generales de continuar/seguir al vocabulario de reanudación y canción/song/pista/track al dominio, sin nombres de artistas/pistas ni frases de panel. La autoridad para nuevas cabezas exige ese mismo dominio; no convierte un «continúa» aislado en control.

La cobertura de cláusulas usa el vocabulario compartido. El lector de operaciones recupera media.control mediante el predicado existente, y el aclarador source_app se abstiene de pedirlo cuando ya existe esa referencia de transporte. Una obra nombrada sin dominio de sesión no obtiene esta excepción. Se conserva _append, la exclusión de grabación/micrófono y los vetos externos de negación, cita, futuro, dispositivo ajeno y conservación de compuestos.

Main reutiliza el mismo vocabulario para play. Sólo en una reanudación acreditada por ese lector deja de contar «en pausa» como verbo de pausa; _fold normaliza los espacios antes del lookbehind. Un pause/pausa/pausar independiente o deja/dejar en pausa sigue contando y conserva la abstención si hay acciones incompatibles. Las pausas que ya pasaron conservan su extracción anterior, pues resuming=false.

No se construye query, cliente, título, posición temporal ni cola. La vinculación sourceApp explícita existente se mantiene sin cambios; no se añade soporte para otros clientes. Los hechos de sesión/postestado siguen correspondiendo al proveedor real y la aprobación de raíz. La propuesta no garantiza la disponibilidad de SMTC ni acredita los pares.

Revisión manual del diff y llamadas: helper→_request_head no llama _is_direct_request, evitando recursión; el bloque inline sustituido se elimina. Sin tests, importaciones, AST, build, Core, GPU, acciones, cambios canónicos/registro ni commits. Reanudación: raíz integra/revisa ambos dueños y mide las dos variantes originales contra la sesión propia observada; no repetir H0110 sin decisión de raíz.
