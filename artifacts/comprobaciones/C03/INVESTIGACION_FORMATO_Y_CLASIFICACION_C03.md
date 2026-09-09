# C03 — formato, interpretación y herencia nativa

Consulta y medición:2026-09-06. ModeloQwen3-4B-Instruct-2507Q4_K_M, servidorllama.cppb9980,
registro intacto; no se extrapola a otros modelos o backends.

## Fuentes contrastadas

- [Let Me Speak Freely?](https://arxiv.org/abs/2408.02442) estudia deterioro bajo
  restricciones de formato en sus tareas/modelos. Aporta una hipótesis, no prueba
  de que el JSON perjudique este Qwen ni razón para quitar validación.
- [Réplica de los implementadores de dotTXT](https://blog.dottxt.co/say-what-you-mean.html)
  cuestiona comparaciones con prompts/plantillas diferentes y reproduce mejoras
  con generación estructurada. Por eso aquí se conservan mensajes, sampling,
  template y presupuesto al comparar GBNFcompacto con JSONSchema y formato libre.
- [CRANE](https://arxiv.org/abs/2502.09061) estudia razonamiento con generación
  restringida. Motiva separar interpretación y formato, sin convertirlo en receta
  probada para BAXY ni habilitar thinking en una revisión Instruct que no lo ofrece.
- [Ficha oficial del modelo exacto](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)
  conserva la distinción Instruct/sin thinking; recomienda instrucciones de formato
  para evaluaciones. Su template nativo admite tools. Se mantiene la investigación
  de sampling33; no se atribuye una receta de otro modelo a esta cuantización.
- [Qwen function calling](https://qwen.readthedocs.io/en/stable/framework/function_call.html),
  ya contrastado34, respalda usar su protocolo de herramientas y devolver resultados;
  la sintaxis válida no acredita selección, autorización ni ejecución.

## Herencia concreta

biblioteca/gemma4-agent/documentacion/02_router/research/1_toolcalling.md distingue
sintaxis de decisión semántica, pero sus recomendaciones son paraGemma4E4B y no
se copian como configuraciónQwen. llm._compact_structured_grammar ya advierte
que la serialización influyó enGemma: se midió enQwen, no se asumió el resultado.
astra-context-contracts35 conserva una pruebaAUTO distinta de la selección forzada
required rechazada históricamente; sus fallos de fecha/prohibición tienen cambios
upstream posteriores. Se reutiliza ese selector y el formato nativo.

La fuente anterior ProbandoGemma4/gemma4_agent/agent_core/agent.py:2189 distingue
conocimiento paramétrico de estado local a partir del plan; el booleano
needs_pc_action no bastaba. Es evidencia contra confundir cualquier consulta
científica con lectura externa. No se copia su catálogo abierto ni su modelo.

## Evidencia local y decisión

astra-guard-format:onceclasificaciones idénticas aGBNFcompacto. Formato libre no
resuelve y trunca2a64tokens. Spans literales previos no corrigen etiquetas. No
promover estas variantes. El problema observado no queda explicado por whitespace.

astra-native-scope:AUTO conserva los11conjuntos de operaciones esperados en catálogo
reducido. astra-native-scope-guarded:el guardia de tipo retira las2lecturas españolas
correctas y convierte conocimiento del aire enunsupported. Se localiza degradación
en el ecosistema. Todavía no hay promoción ni prueba deproducto conAUTO.

Cambio40independiente:un veto compuesto levanta fallo de interpretación y usa
recuperación, en lugar de autorizar prosa paramétrica sobre un hecho no observado.
Pruebas y literales:PRUEBAS_CLASIFICACION_Y_RECUPERACION_C03.md.

## 406–410 — búsqueda de operaciones y cuenta de Windows (2026-09-08)

Herencia: biblioteca/gemma4-agent/documentacion/02_router/research/
07_SKILL_RETRIEVAL_research.md:1–62 y evidencia retrieval270. Se separa selección
de disponibilidad de herramientas. [TinyAgent](https://arxiv.org/abs/2409.00608)
aporta el mecanismo de recuperación local de herramientas; sus cifras no son
resultados de BAXY. La [ficha E5](https://huggingface.co/intfloat/multilingual-e5-small/raw/main/README.md)
mantiene query/passage en recuperación asimétrica y vectores normalizados, ya
usados por router.py. Snapshot614241f6/manifest e1ab2f71 verificado en406b.

407 refuta la hipótesis de promoción bloqueada: semántica disponible24,438s;
antes, lexical.408 demuestra2/4→4/4cuentas visibles al reutilizar descriptor387;
40911/13→13/13decisiones útiles con E5cargado. Se adopta410 descriptor y abstención
de recursos ante cuenta/usuario. No nueva capa/clasificador, catálogo alternativo
ni espera impuesta al usuario. UsernameENfrío permanece fuera del top4: producto411
lo mide. RESULT/PINS406–410 conservan configuración, límites y controles.
