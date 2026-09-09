# C03 — tramo20: inversión del silencio y diagnóstico del encoder

EN_CURSO. El tramo anterior produjo21adjudicaciones y el Markdown de1759turnos;
cuenta como progreso, no cierre. Sin100frescos, promoción, Fullfinal ni publicación.

Herencia consultada: biblioteca/gemma4-agent/codigo-docs/prompts/tool_rules/audio.md:5
distingue explícitamente mute=true/silencio y false/restauración. Se probó representar
el mismo hecho como estado categórico para el narrador, conservando raw booleano.
Modelo/sampler/instrucciones/verificadores iguales. Captura mute-state:21publicados,
t6 vuelve a afirmar audio desactivado y t4 añade prosa técnica. **Hipótesis descartada**;
se retiraron modificación y tests específicos. No añadir una lista de frases vetadas.
Adjudicación individual en astra-qwen2507-mute-state/ADJUDICACION.md.

Validación del candidato retirado:129Python pass; Ruff0. Fallos intermedios eran
expectativas del formato anterior (3) y fixture de prueba con idioma ambiguo (6),
resueltos antes de medir. Los tests no se usaron para declarar calidad visible.

Investigación independiente: E5 existe, worker aislado ready40,05s (tramo18), pero
capturas siguen lexical. promote_planner_resources espera al TurnEvidenceService
antes de construir catálogo semántico, con deadline185s; no se ha probado fallo.
Diagnóstico real del mismo servicio/caché/routerCPU sin otro LLM:
scratchpad/c03-encoder-service-probe.py y .log, sesión13268 terminó0.
19,05s,7383registros, policy=incompatible. Faltaba tests/data/turn_evidence_runtime.v1.jsonl;
el resolver tomaba historical_messages.jsonl, con otra huella. La política esperaba
8abff5805a93615c6f5a655b9af5559063e34226cfc0db58c5547d97a70ee680.

Se heredó ../BAXY/tests/data/turn_evidence_runtime.v1.jsonl (8421417bytes), hash
exacto esperado. Es dependencia local ignorada por Git; no se publican mensajes
privados. Restauración histórica ya documentada en artifacts/audit/turn_evidence_restoration_r234.json.
No cambiar umbral, política ni hashes para aceptar otro corpus.

También estaba la caché válida en %LOCALAPPDATA%/BAXYRuntime/turn-evidence:
5dd998d3e61866dc136c257d.json/.npy. _load_cache validó esquema, corpus,
identidad, hash de vectores y dimensiones/filas. Se reutilizó por _store_cache
bajo la clave del nuevo path45bbe54a0653f85877b05cdb, sin recalcular embeddings.
encoder-cache-inheritance.json conserva identidad y procesos de diagnóstico.
Sesión64126 se detuvo explícitamente para evitar un recálculo innecesario tras
validar la caché; terminal1, no fallo del producto ni bloqueo. Sólo su árbol propio.

Sesión47970 terminó0: servicio real ready20,09s,25156registros,384dimensiones,
política loaded/compatible, sin errores. Log c03-encoder-service-cache-inherited.log.
Recheck de fuente restaurada:120Python pass, c03-mute-state-restored.log.
Captura integrada astra-qwen2507-corpus-inherited/sesión44083 iniciada con mismos21
mensajes, corpus y política en PREREG, observadores diagnósticos de recursos que
no alteran sus resultados. Recoger y verificar resource-readiness.jsonl y turn-audit.
Registro intacto; no promoción ni Full. Sesión44083 terminó0:42,06s,21pub,
GPU3497,56MiB,RAM5319,66MiB. Servicio25156compatible en27,25s y constructor del
catálogo semántico terminó sin errores en5s; turn-audit aún todo lexical. ADJ21
escrita, sin mejora de calidad declarada. Fixture22780 cerrada, procesos recogidos.

ProductConductorHost.InitializeAsync precede a LoadCommandsAsync, que lee stdin
hasta EOF. Permite una comprobación en caliente sin editar producto: conservar
stdin abierto hasta constructor semántico de catálogo+skills, luego liberar21
comandos preregistrados. Captura corpus-warm/sesión26550 TERMINAL0:179,22s totales,
150,188s de preparación registrada. El observador de skills no contemplaba encoder
posicional y por eso esperó el límite; defecto del diagnóstico, no del producto.
21publicados; GPU3497,56MiB,RAM5225,75MiB. Diez raw_attempt registran retrieval=semantic:
promoción probada en el producto. Journal24/26/28 prueba título y cierrePID14476.
No procesos de esta tanda activos. ADJ21 escrita: naturalidad/spanglish siguen mal,
audio «desmudado» en t2; no se declara mejora de calidad general. No más variantes
del estado de silencio ni repetir21sin causa nueva. La siguiente investigación debe
seguir la narración real y la selección de contexto; E5 ya no es dependencia ausente.
