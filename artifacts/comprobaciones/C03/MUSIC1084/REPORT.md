# MUSIC1084 revisión2 — navegación y detención inequívocas

Base2741e7d502a65011bbefe87cd3e2881093a5eb19. Propuesta externa sólo effect_intent.py y __main__.py; sin canónico, modelo, provider, pruebas, imports, AST, build ni GPU. Diagnóstico español previo conservado; ninguna cobertura adjudicada.

Inglés1082/case6, «Skip forward to the next track.», request8: raw ya conversation/knowledge/zeroeffects; media.control ausente de28candidatos (sí media.status). explicit_contract no recupera operación; conversation_presentation pasa a unsupported. raw-replies dice «I cannot skip forward to the next track as requested.»; captura final ruta error «This is outside what I do on this PC.». No operación multimedia ni fallo de postlectura.

Precisión de la primera causa: _is_direct_request no admite skip, y el helper nominal tampoco admite skip forward to. La rama fallback de _review_media_and_email_effects:12004 sí reconoce skip/next/track, pero está detrás de la autoridad general. No es correcto atribuir toda la pérdida a ausencia de dominio track. El binder inglés ya liga next; la modificación compartida de binder es necesaria para nuevas construcciones relativas/inversas, no la causa retrospectiva de ese turno inglés.

Stop1082/case9, «Detené la reproducción actual.», request8: raw propone media.status, sin media.control en candidatos; explicit_contract no lo corrige y domain_grounding retira esa lectura incorrecta. Detene falta en autoridad y cabezas de control, y el binder stop sólo contempla stop/deten/detener. No se modifica el veto que rechazó media.status ni se infiere éxito del caso inglés10.

Cambio común: sustituir _media_navigation_request por _media_transport_action, que devuelve una acción única desde una petición completa y objeto musical explícito. Conserva las formas nominales previas y añade tránsito hacia dirección explícita, relativas de posición y detención morfológica detene/para con dominio musical. El mismo lector sirve a autoridad, reconocimiento y argumentos; helper anterior retirado, sin capa adicional.

Binder: para formas completas reconocidas, usa la acción del lector y no vuelve a inferir next del verbo skip ni mezcla esa dirección con previous/stop legacy. El resto de acciones sigue comprobándose y cardinalidad1 sigue siendo obligatoria. Fuera de las formas completas se conserva el fallback anterior. Se mantiene _append con su veto de negación; sólo se amplían los marcadores a la gramática que el lector ya acreditó. No sourceApp nuevo ni sustitución de estado/cliente.

Revisión manual: next nominal y skip forward to next track conservan next; tránsito a canción/pista que viene comparte dirección con binder; skip back to previous track no añade next por mero skip; detene la reproducción actual y para la música sólo autorizan stop por objeto musical explícito. Negación, cita, condición, narración pasada, direcciones contradictorias y sufijos/acciones extra no satisfacen este lector completo; otros contratos vigentes siguen aplicando. Estas son lecturas estáticas, no pruebas ejecutadas ni éxito funcional.

El español case5 «Pasá al tema que viene.» permanece sin resolución automática: no se añadió tema a objetos musicales ni se usa una sesión SMTC como prueba de intención. Requiere contexto real o aclaración. Una aclaración útil no sería pase de este par de avance. La propuesta no garantiza2variantes next ni créditos; la generalización queda pendiente de producto real y raíz.

Previous1082/case8, «Go back one song in the current queue.», request8: también raw knowledge sin efecto y shortlist sin media.control; explicit_contract vacío y presentation unsupported. A diferencia de skip, go ya es autoridad general; aquí falta posición de un elemento en la gramática de dominio. El lector compartido añade desplazamiento explícito forward/back de one objeto musical (nunca dos o cantidad omitida), con contexto queue opcional, y orden nominal objeto+dirección además de dirección+objeto. _append incorpora los marcadores forward/back, evitando una recuperación que luego no emita efecto. No se atribuye pase al literal anterior que raíz todavía mide.

Inglés stop/case10 se mantiene separado: raíz reporta inv50b6e70f-33bc-4f62-8ced-9c141f82b44b failed/smtc_postcondition_not_verified con efecto incierto y reproducción persistente; el trace confirma media.control. Esta propuesta de gramática no repara ni reintenta esa semántica del proveedor. No convertir pause en stop para obtener verde.

## SHA256 de base, propuesta y recibos
- base/effect_intent.py: db79ad14666531dc11ab471eb4a9292a6d3378ceb5e224832d5b6ca39f957001
- proposed/effect_intent.py: 32b3becbdf9b18c459e228b8e4464830cf270aa85e7ba0f2c550c42329a641b5
- base/__main__.py: 7be3cd8e8bce8a45eec8e2031e3189b422c53b9c46df0b62754a289b7760888f
- proposed/__main__.py: d7a19edad4472581288f68adfd31b8d93012e6e051b06cfe0b3a9f84480ace2e
- repair.patch: 731dc32c05ba9fbc7b10a01480630357e34437fe1bbbd46e4b0cb396157bddf9
- C:/Users/usuario/AppData/Local/BAXY/C03-music1082-proposal/private/run-06/turn-audit.jsonl: 26a5f32125f701bb91985d2f9297f3879292b3b566ad3ba74d1703745d09f524
- C:/Users/usuario/AppData/Local/BAXY/C03-music1082-proposal/private/run-06/shell-trace.jsonl: 5dac09e909fd635bd8fa4f716ed33c31b87241e4ffa4823afd635b8e4328d00c
- C:/Users/usuario/AppData/Local/BAXY/C03-music1082-proposal/private/run-06/capture/events.jsonl: 118988c494d88e7597fe3987ee8866ca39a7086c238496fd7246ec9b5b9c976a
- C:/Users/usuario/AppData/Local/BAXY/C03-music1082-proposal/private/run-08/turn-audit.jsonl: 1517a37e070fb0af6e9eb18468c09a86e02a370dec0e25d4e0be8b6d654d3ef8
- C:/Users/usuario/AppData/Local/BAXY/C03-music1082-proposal/private/run-08/shell-trace.jsonl: 7bd163c4c4eafe239a31c07770fedbda560622d484cfce319cc738656dec19f8
- C:/Users/usuario/AppData/Local/BAXY/C03-music1082-proposal/private/run-08/capture/events.jsonl: cb2e328cfb82f35ed3ba1836e219571fe7d5fc622b300a90dda10a35e495561b
- C:/Users/usuario/AppData/Local/BAXY/C03-music1082-proposal/private/run-09/turn-audit.jsonl: 521a99e0c25e9ddac786acec97463051e9ba8e4a43f3a70448aa634843b2f3a1
- C:/Users/usuario/AppData/Local/BAXY/C03-music1082-proposal/private/run-09/shell-trace.jsonl: 04643ada08a4f6dc47fea476a276734ccd9ee2cfea29481da20f8c8b48f7f7fa
- C:/Users/usuario/AppData/Local/BAXY/C03-music1082-proposal/private/run-09/capture/events.jsonl: a6e002a7ee95e73cb07adae63eb10dcffec503f267c9d6558d8dad1c7add8153
