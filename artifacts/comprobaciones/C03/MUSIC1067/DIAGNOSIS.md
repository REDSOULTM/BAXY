# MUSIC1067 — puerta de admisión anterior al arreglo1063

La fuente medida MUSIC1065 sí contiene el arreglo1063. PREPARATION.json fija HEAD44aa529da3b9df6cad0f193fcbfa60cbf71e658c y SHA e3c63ed9a06cca6f760faeca46de8e4ab71ea265fd1e4dbc1881f3ed72476cbf para effect_intent.py; coincide con el archivo leído. runtime.json apunta BAXY_MIND_PYTHONPATH al src de este repositorio. No hay evidencia de una ejecución con fuente antigua ni motivo para repetir el build como hipótesis.

H0110 «reanudá la música», request8, run-01: mismos28candidatos sin media.control; decision_path=model; rawmedia.seek.relative; domain_grounding lo veta y la terminal comunica imposibilidad. Sólo memory.status de arranque, sin efecto multimedia. La raíz observó después Aurora de cobre aún pausada0:09. Este diagnóstico no ejecutó una nueva lectura de esa sesión.

## Primera pérdida concreta

La normalización NFKD/fold conserva el verbo como reanuda; no falta la forma acentuada en el reconocedor multimedia. _request_head podría extraer esa cabeza. El problema sucede antes:

1. _is_direct_request (7943–8036) reconoce play/pause/stop, pero su enum omite reanuda/reanudar/resume.
2. resolve_explicit_effects consulta esa puerta en14065. H0110 es una cláusula, no una excepción contextual admitida; devuelve None en14093. Éste es el primer corte general identificado, previo al reviewer.
3. Incluso al entrar por otra ruta, _resolve_explicit_effects_single exige la misma puerta en12085–12130. Sólo después calcula head12133 y llama _review_media_and_email_effects12207.
4. _COVERAGE_ACTION_HEAD también omite esos tres verbos. Es la entrada de _explicit_desire_request y la segmentación conservacional; dejarla desincronizada mantendría rotos los marcos de deseo y las coordinaciones aunque el imperativo simple pasara.

MUSIC1063 corrigió una condición posterior real: exigir «pausado» cuando reanudar ya expresa continuidad. Sigue siendo necesaria al alcanzar el reviewer. Mi revisión1063 no había seguido estas puertas generales anteriores; por eso el primer hunk no bastó para la ejecución. No se revierte ni se vuelve a proponer el mismo cambio. El recibo SMTC corregido1063 es otra costura independiente y tampoco se altera.

## Propuesta mínima

Un owner, effect_intent.py, dos líneas: admitir los tres verbos que el reviewer y el extractor action=play ya conocen en las listas de entrada de petición y cobertura de cláusulas. No añadir nuevas variantes, traducciones, nombres de apps ni IDs; no cambiar pause/play/stop, el reviewer1063, argumentos, provider, respuesta o compositor. El DIFF parte de la fuente44aa529d integrada, no de la propuesta anterior, y conserva CLOSE1060+MUSIC1063.

La admisión de cabeza no crea por sí sola una operación: dominio, restricciones multimedia y catálogo cerrado siguen decidiendo el efecto. Los vetos de meta/cita/negación, corrección contradictoria, diferimiento y otro dispositivo permanecen. Ampliar la cabeza vuelve alcanzables esas lecturas para los verbos añadidos; no se afirma que toda paráfrasis sea ahora válida. En particular no se promete que «Seguí...» o el objeto «track» de los pares inéditos1037 pasen con este cambio: no se retocan por anticipado.

## Evidencia y límites

IDENTITY.json liga PREPARATION y los archivos exactos del segmento. La causa se obtiene por el flujo del código y es consistente con el audit observado; no se inventa una traza interna de cada función que el producto no emitió. La propuesta requiere adopción y medición de raíz antes de afirmar mejora o crédito. El detector incorrecto media.seek.relative sigue correctamente vetado; no se desactiva el veto para aparentar avance.

Sin pruebas, imports de producto, build, Core, GPU, cambios canónicos o registro. No se modifica ningún panel ni propuesta previa. No se atribuye resultado al segundo caso de pausa que ejecuta raíz en paralelo.
