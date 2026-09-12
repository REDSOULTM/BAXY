# WEB1054 — normalización del nombre de sitio, propuesta externa

Dos fallos observados en WEB1045 (candidato15d3a5385db5db8545a0060cfd9bcf0ef4a2957f), con primera pérdida en _symbolic_web_destination, antes del resultado que ve el usuario. No se afirma regresión contra baseline anterior ni cambio medido: diagnóstico de evidencia1045 y propuesta estática sobre HEAD943e937d65d5d7364402d2bb6817b3a3b27f2899.

## Mozilla, web1045-dev-01

Texto exacto «Entrá al sitio web de Mozilla, por favor.», request8. Audit raw: decision_path=model, knowledge,zeroefectos. No recuperación de operación en explicit_contract/domain_grounding/action_grounding. conversation_effect_shape=complete; presentation convierte knowledge→unsupported. Rawconversation después de esa conversión: «No puedo entrar al sitio web de Mozilla tal como fue pedido.»; compose t1 outside what I do/out_of_catalog→«No puedo acceder al sitio web de Mozilla.». No lookup/navegación según adjudicación de raíz.

Primera causa estática concreta: helper11284 reconoce el imperativo con target «sitio web de Mozilla, por favor». _strip_request_envelope sólo quita un cierre social completo (eso es todo/that is all...), no cortesía sola; _symbolic_web_destination quita «sitio » pero deja «web de Mozilla, por favor». _bounded_application_literal4007–4044 rechaza la coma: devuelveNone. Incluso quitar sólo la coma/cortesía dejaría query inadecuada «web de Mozilla». No basta añadir entra al gran _is_direct_request: resolve_explicit_effects13398 YA llama este extractor antes de ese fallback, y la navegación «entrá a la página de wikipedia» ya pasó por la ruta existente. No nueva tabla de verbos ni nuevo clasificador.

La conversión presentation→unsupported es visible pero posterior al fallo de reconocimiento; no se propone evitarla globalmente ni aceptar conversación como navegación cumplida.

## Debian, web1045-dev-02

Texto «Take me to Debian's official website.», request14. Audit decision_path=explicit_effects, planweb.search→browser.navigate; intención correcta retenida. __main__4526 usa el mismo extractor como query literal. Extractor sólo entiende descriptor ANTES del nombre (la página oficial de...), no posesivo inglés al FINAL, y produce «Debian's official website».

Journal seq3/4, invocation86d0a57c-c1ac-469d-9ea9-2f29a3f1d0d4, request7e890618-2ee7-4f1a-ac88-3a9ad65f5705: web.search failed,verifiedfalse,replayedfalse,errorweb_search_results_irrelevant. No navegación observada. Compositor t2 explica fielmente el fallo; no se culpa su prosa.

Diagnóstico privado captures/web-search-rejections.jsonl,13:45:53.2543558Z: queryTerms=[debian,official,website],10 ítems estructuralmente válidos,0omitidos. Primeros resultados son «Debian -- El sistema operativo universal»,https://www.debian.org/index.es.html y «Debian -- The Universal Operating System»,https://www.debian.org/. Los10 tienen missingTerms=[official,website]. Son resultados NO verificados, nunca nueva evidencia de navegación ni acreditación de identidad oficial. Demuestran por qué el provider los descartó; no demuestran que pueda adjudicarse el destino sin navegar.

El filtro de pertinencia aplica el contrato sobre query equivocada. No tocar WebBrowserAdapter ni eliminar términos globalmente del filtro: cambiar el operando del extractor de navegación para que el nombre público sea Debian, conservando solicitud original con requisito de sitio oficial en evidencia. No reformular búsquedas directas generales «busca Debian official website»: ese contrato sigue igual.

## Parche mínimo

Un owner: src/baxy_mind/effect_intent.py, sólo _symbolic_web_destination.
- Cortesía terminal con coma y forma exacta por favor/please se retira únicamente del operando de navegación ya anclado; nunca se modifica entrada original de guardas.
- Descriptor de sitio admite las formas compuestas sitio web/página web antes del nombre.
- Posesivo de nombre seguido de official/main/home opcional ywebsite/site/web site/page pasa el nombre público al resolver existente. No mapa de sitios/dominios/IDs ni URL construida.

Se conservan explicit_non_action_frame, meta/denial,pasado/hipotético,deferred,correcciones,cláusula única,browsernombrado,URLs/localpaths/datosprivados,_bounded_application_literal y_direct_public_search_query. fullmatch de navegación no cambia; negación/cita/condicional no adquieren un imperativo por quitar el sufijo. Cuestiones con sitio sin referente siguen sininventar nombre. No se cambia __main__: ya reutiliza el mismo extractor para reconocimiento/query ydeja URL dependiente de búsqueda verificada.

Límite: la normalización explica el bloqueo medido, pero ningún código/regex de producto fue ejecutado aquí. El buscador podría devolver resultados distintos; ni búsqueda por nombre ni coincidencia de texto garantiza que una URL sea oficial. Debe mantenerse el original completo como objetivo yverificarse pertinencia/identidad yCDP; si no se resuelve, fallo honesto sin navegación ni crédito. No templates de dominios, no whitelistMozilla/Debian.

## Masa y próximo tramo

Cinco literales ya útiles pendientes de pares: H0152,H0206,H0244,H0479,H0692. Dos variantes fallidas1045 impiden pares; potencial5créditos, no≥10 yno5garantizados. Root decide aceptación temporal de literales previos frente a nuevo candidato. Próxima medición dirigida conserva IDs/textos de web1045-dev-01/dev-02 como reejecuciones fallidas, sin retag deoriginales nuevas. Mantener5límites originales1045 para negación,cita,condicional,referente ausente ypregunta deprivacidad; sus2fallos previos no se declaran arreglados por este parche. No repetir toda categoría ni construir provider.

EVIDENCE.json contiene sólo las dos trazas pertinentes yprimeros2resultados rechazados; IDENTITY.json fija fuentes ySHA. DIFF.patch97056f9df82ba582bdbe5c19454e524eef3b10d7f59ef2a4e44ae2c9f787be73. SinGPU/tests/imports/modelo/HTTP/fixtures/ejecución/canónico/registro/commit. Root único adjudicador.
