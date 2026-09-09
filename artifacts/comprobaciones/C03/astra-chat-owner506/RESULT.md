# La conversación redacta la respuesta

Se retiró por completo el transporte conversation_reply desde el selector nativo hasta chat y el parámetro initial_reply que omitía su generación. La conversación existente conserva identidad, idioma, historial, guardas y reparaciones. El cache de conversación especulativa permanece: ya contiene una respuesta generada por chat, no prosa de selección. No se añadieron prompts, respuestas fijas ni capas.

Baseline2fallos/7pass; final9pass0,83s. Siete suites3404pass y121subtests, cero skips,53,88s. Fast verde; Release3,32s sin warnings/errors. Sesiones38298/16397 recogidas exit0; servidores de build cerrados. La definición inexacta y el recuerdo falso de505 siguen abiertos y no se ocultan tras estas pruebas verdes.
