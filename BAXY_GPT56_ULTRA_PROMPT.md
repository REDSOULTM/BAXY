# Prompt maestro — reconstrucción definitiva de BAXY

Copia desde la siguiente línea hasta el final en una sesión nueva de GPT-5.6
Sol Ultra.

---

Actúa como arquitecto principal de producto e ingeniero principal de BAXY.
Tienes que investigar, reconstruir, probar e iterar hasta dejar un BAXY
realmente utilizable. No entregues solamente un plan, un esqueleto, una demo ni
una colección de funciones aisladas: implementa el producto, úsalo en misiones
reales, mide los resultados, corrige las causas raíz y vuelve a probar.

## 1. Misión de producto

BAXY es un asistente local para Windows al que una persona le habla o escribe.
BAXY entiende la intención, realiza la tarea en el computador, verifica el
estado final y responde como un asistente humano:

El alcance funcional de BAXY 1.0 se define por todos los mensajes históricos
dirigidos a Carter y BAXY desde el inicio del proyecto hasta el cutoff
documentado al comenzar esta reconstrucción. El producto terminado debe poder
resolverlos mediante capacidades generales y componibles, no mediante una lista
reducida de ejemplos ni un parche por frase.

- Usuario: “Baxy, pon música”.
- BAXY: “Listo, puse Billie Jean de Michael Jackson en Spotify”.

La interfaz normal jamás debe responder mostrando un visor de comandos, JSON,
IDs de invocación, trazas o contratos internos. Esos datos pueden existir en
logs privados y en un modo de diagnóstico opcional y apagado por defecto. La
respuesta de producto siempre es lenguaje natural, breve y suficiente.

BAXY debe sentirse como un amigo competente: amigable, directo, emocional y
adaptable a la persona. Recuerda preferencias y contexto útil de forma local,
aprende hábitos con prudencia y puede proponer alternativas o temas nuevos. No
finge éxito: solo afirma lo que verificó.

## 2. Ubicaciones y estado inicial

Repositorio nuevo:

C:\Users\usuario\Desktop\ETC\Programacion\BAXY

El producto anterior está preservado en:

C:\Users\usuario\Desktop\ETC\Programacion\BAXY\legacy

Trata legacy como referencia de solo lectura. No lo modifiques, no lo borres,
no lo promociones en bloque y no restaures su arquitectura por inercia. El
último árbol completo también está disponible en Git en el commit ee06786.

Antes de inspeccionar las fuentes masivas o escribir código, lee íntegramente:

- documentacion\00_LEEME.md
- documentacion\01_CONTRATO_PRODUCTO.md
- documentacion\02_INDICE_FUENTES.md
- documentacion\03_HALLAZGOS_AGENTES.md
- documentacion\04_ARQUITECTURA_TECNOLOGICA.md
- documentacion\05_FALLOS_Y_REGRESIONES.md
- documentacion\agentes\README.md
- documentacion\agentes\INDICE.md
- documentacion\agentes\manifest.json

Esta carpeta contiene el handoff ya recuperado de la etapa anterior. Úsalo para
evitar redescubrimiento, pero conserva la procedencia: una síntesis no sustituye
la evidencia primaria. Amplía estos documentos conforme recorras Carter,
FunctionGemma, Probando Gemma 4, BAXY, Git, conversaciones y artefactos.

### Archivo recuperado de subagentes

El trabajo de los subagentes de la etapa anterior ya no depende de las tarjetas
de la interfaz. El export reproducible reconstruyó 322 sesiones descendientes:
302 hijas directas y 20 anidadas. La vista versionada y sanitizada está en
documentacion\agentes. La copia local privada está en:

documentacion\agentes\privado

Contiene el hilo raíz comprimido, un segmento task-specific por sesión,
manifest_private.json e informes_finales.jsonl. Está ignorada por Git porque
incluye comandos, outputs, rutas y contexto potencialmente sensible. No la
subas, no la copies a servicios externos y no vuelques sus 322 sesiones de una
vez al contexto. Primero consulta el índice; después abre únicamente los
informes y segmentos relevantes para cada decisión.

Si el archivo falta o el hilo ha cambiado, regénéralo desde la raíz con:

python scripts\export_codex_subagents.py --force

Recuperable no significa verdadero: cada afirmación de un agente debe quedar
ligada a session_id, agent_path y segment_sha256, contrastada con fuente
primaria, código o prueba, y clasificada como corroborada, contradicha,
obsoleta o pendiente. El prompt exacto puede estar cifrado en algunos JSONL y
el razonamiento interno oculto no se recupera; no intentes inferirlos ni
inventarlos. Sí están disponibles informes finales, mensajes publicados,
resúmenes de razonamiento expuestos, tools y outputs persistidos.

### Genealogía completa que debes reconstruir

No estudies BAXY como si hubiera comenzado en este repositorio. Reconstruye la
línea evolutiva completa, cronológica y causal:

Carter
→ primeros prototipos de voz y herramientas
→ Probando Gemma 4
→ FunctionGemma y su catálogo de más de 500 tools
→ arquitecturas de routing, memoria, computer-use y accesibilidad
→ experimentos Gemma 4/Qwen/llama.cpp
→ BAXY y Tool Ecosystem v2
→ auditorías, gates físicos, fallos de integración y decisiones actuales
→ BAXY definitivo.

Para cada etapa identifica:

- qué problema intentaba resolver;
- qué prometía al usuario;
- qué tecnologías y arquitectura utilizó;
- qué funcionó de verdad y con qué evidencia;
- qué solo funcionaba en mocks o demos;
- qué se rompió en uso físico;
- qué complejidad se acumuló;
- qué decisiones se corrigieron después;
- qué conocimiento, corpus, prueba o primitiva merece reutilizarse;
- qué no debe volver a implementarse.

Genera docs/evolution_carter_to_baxy.md con esta cronología, enlaces a las
fuentes y una tabla de “heredar, rediseñar o descartar”. La nueva arquitectura
debe poder explicar cómo cada fracaso histórico influyó en una decisión o test
actual. No empieces de cero en conocimiento: empieza de cero en diseño.

Fuentes históricas obligatorias:

1. Visión y tesis:
   C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\_tesis_curso\entregables
2. Repositorio histórico Gemma/Carter:
   C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4
3. Ecosistema histórico de más de 500 herramientas y router:
   C:\Users\usuario\Desktop\ETC\Programacion\FunctionGemma
4. Conversaciones, decisiones y evidencia del BAXY recién archivado:
   - legacy\ContextoFable.md
   - legacy\Codex.md
   - legacy\README.md
   - legacy\docs
   - legacy\tests
   - legacy\data y sus manifiestos/logs legibles
   - legacy\Experimentando
   - historial de Git
5. Historial adicional del repositorio anterior:
   - ContextoGPT.md
   - documentacion
   - gemma4_agent
   - scripts, evaluaciones, misiones, corpus y grabaciones existentes
6. FunctionGemma:
   - README_TOOLS.md
   - INTEGRATION_HANDOFF.md
   - KVA_GATE_HANDOFF.md
   - router, tools, domain_tools, corpus, evaluaciones y scripts de extracción

### Conocimiento ya descubierto que debes reutilizar y revalidar

Los agentes y auditorías de la etapa anterior dejaron hallazgos que reducen
trabajo repetido. Búscalos en legacy, Git, documentos, artefactos y
conversaciones, y conviértelos en requisitos de regresión. No los aceptes
ciegamente: comprueba que la fuente y la evidencia coincidan.

1. El último checkpoint completo antes del archivo es ee06786. La rama de
   reconstrucción comenzó en d3b92a3. Usa Git para consultar cualquier archivo
   que no esté cómodo de leer desde legacy.
2. Tool Ecosystem v2 llegó a un inventario estable declarado de 94
   capacidades registradas, 91 seguras, 3 en cuarentena y 39 workflows. El
   perfil experimental de Spotify declaraba 95/92/3/39. Esos números sirven
   para localizar evidencia, no son una meta de producto ni prueban utilidad.
3. Una auditoría final de diferencias reportó 0 P0 y 0 P1 en la separación
   entre el perfil estable y Spotify experimental: identidades, contratos,
   epochs, counts y attestation eran incompatibles a propósito. Conserva el
   principio de perfiles imposibles de confundir, aunque rediseñes su forma.
4. El preview de misiones compuestas fue diseñado para no producir efectos:
   solo dividir, groundear, compilar, validar y proyectar. La ejecución,
   ledger, locks, providers e idempotencia quedaban fuera del preview. Conserva
   esta separación entre plan visible y efecto real.
5. Los resultados privados estaban ligados a request, operación y result ID,
   y el resultado público debía quedar redactado. Reutiliza la protección de
   datos, pero no el visor técnico como experiencia del usuario.
6. La idempotencia física de Spotify exigía resultado verificado, ledger
   completed, prueba SMTC independiente y conservación del invocation ID sin
   repetir el efecto. Generaliza esta idea a todas las mutaciones.
7. El gate de Spotify podía ser totalmente inerte sin el flag de ejecución y
   exigir identidad experimental exacta cuando ejecutaba. Conserva gates
   explícitos que no produzcan efectos por accidente.
8. En una prueba física, Gemma encaminó correctamente spotify.play_exact y
   produjo una invocación válida, pero el proveedor no verificó el resultado.
   Esto demostró que routing correcto no significa misión cumplida.
9. La causa física incluyó dos supuestos incorrectos del proveedor:
   - inventariar siete procesos de Spotify podía superar un timeout de 8 s en
     frío;
   - Spotify clásico firmado por Spotify AB podía devolver AUMID None y nunca
     pasar una regla escrita solo para la versión Store.
   Se corrigieron el presupuesto temporal y la atestación de Spotify Win32 con
   pruebas contra identidades falsas. Recupera esas pruebas y principios; no
   copies la implementación sin revisar.
10. Otro intento de promover Gemma 4 unificado terminó con 0/11 activaciones,
    STT vacío y visión vacía. La hipótesis principal fue servidor equivocado o
    wiring roto. La nueva versión debe probar identidad, modelo, parent, puerto
    y camino de datos de punta a punta antes de atribuir una salida al modelo.
11. El mensaje “BAXY core listo · 0 capacidades registradas” expuso que una GUI
    abierta no prueba que el producto esté conectado. El arranque debe fallar
    de forma visible o degradarse honestamente si no hay capacidades reales.
12. Hubo carreras del harness en Windows al reemplazar heartbeat.json mientras
    otro lector lo tenía abierto, además de reinicios e interrupciones del
    soak. Preserva la escritura atómica con reintentos y separa fallos del
    harness de fallos del producto.
13. El soak consumió atención antes de que el asistente completara suficientes
    tareas reales. En esta reconstrucción va al final; primero se construye y
    usa BAXY.
14. Qwen-VL 2B tuvo un costo medido cercano a 2713 MiB y fue rápido, pero
    confundió juegos; 4B rondó o superó 4140 MiB y 8B fue demasiado pesado.
    Trátalo como evidencia histórica para perfiles opt-in, no como conclusión
    definitiva sin repetir mediciones.
15. El visor de resultados privados/JSON terminó siendo técnicamente riguroso
    pero incorrecto como UX. La privacidad y trazabilidad se conservan detrás
    de escena; la conversación natural reemplaza el visor en el producto.

Reutiliza de los agentes anteriores:

- mapas de dependencias y decisiones;
- corpus y casos de routing;
- contratos y pruebas de seguridad;
- gates que distinguen preview de ejecución;
- verificadores físicos;
- reglas de identidad y pertenencia de procesos;
- sanitización, cleanup y control de servidores;
- casos adversariales y causas raíz;
- evidencias de VRAM, latencia y estabilidad;
- diseños de privacidad e idempotencia.

No reutilices automáticamente:

- el número de tools como KPI;
- aliases que inflen cobertura;
- confirmaciones excesivas;
- viewers técnicos como respuesta;
- arquitectura fragmentada solo porque ya existe;
- proveedores que declaren éxito sin verificar;
- defaults experimentales;
- tests que solo demuestren mocks;
- documentación que contradiga el comportamiento real.

Lee primero las fuentes Markdown canónicas de la tesis; usa PDF/DOCX/PPTX solo
cuando contengan información que no esté en sus fuentes Markdown. Busca en
todo el historial cada petición real hecha a BAXY o Carter, cada ejemplo,
misión, fallo, expectativa, caso de voz, herramienta, decisión y corrección.
No te limites a los nombres de archivos que enumero.

Las cifras, modelos y conclusiones antiguas son evidencia histórica, no verdad
actual. Contrástalas con el código, pruebas locales y fuentes primarias
vigentes a la fecha de ejecución. Para Gemma, llama.cpp, Windows, UI
Automation, navegadores y demás dependencias, prioriza documentación oficial,
papers, releases e issues técnicos reproducibles. Las experiencias de usuarios
sirven como señales, no como autoridad.

## 3. Descubrimiento histórico obligatorio antes de diseñar

Antes de implementar la arquitectura definitiva, crea un inventario trazable
de requisitos. No leas la historia de manera anecdótica: extráela a un corpus
estructurado y deduplicado.

Ese corpus completo es el alcance funcional de BAXY 1.0. Recorre todas las
fuentes disponibles desde Carter hasta el BAXY actual y extrae **cada mensaje
del usuario dirigido a Carter o BAXY**: órdenes, preguntas, conversaciones,
correcciones, preferencias, ejemplos, quejas y misiones compuestas. Incluye
repositorios, logs, historiales de conversación, adjuntos, corpus, tesis,
FunctionGemma, Probando Gemma 4, legacy, Git y el hilo Codex actual.

Al iniciar la extracción fija en el ledger una fecha/hora de corte, commits y
hashes de las fuentes. Ese corte hace finito el alcance: todo mensaje existente
hasta entonces pertenece a 1.0. Las aclaraciones del usuario durante la
construcción que corrijan el contrato también se incorporan; capacidades nuevas
pedidas después del congelamiento solo cambian 1.0 si el usuario lo indica
explícitamente.

Genera como mínimo:

- docs/product_contract.md
- docs/evolution_carter_to_baxy.md
- docs/historical_requirement_ledger.md
- docs/historical_source_map.md
- docs/architecture_decision.md
- docs/technology_tournament.md
- docs/agent_evidence_ledger.md
- docs/risk_and_confirmation_policy.md
- docs/tool_ecosystem_design.md
- docs/tool_coverage_matrix.md
- tests/data/historical_messages.jsonl
- tests/data/historical_missions.jsonl
- tests/data/historical_message_mapping.jsonl

Puedes consolidar los documentos nuevos dentro de documentacion en vez de
crear una segunda jerarquía docs. No dupliques información: evoluciona el
handoff existente y mantén un único índice canónico.

Cada caso histórico debe registrar:

- ID estable del mensaje original y del caso canónico;
- clase: misión real de usuario, conversación/pregunta, requisito de producto,
  preferencia, feedback/fallo o instrucción puramente de ingeniería;
- fuente y ubicación;
- texto literal cuando esté disponible, redactando únicamente secretos, más
  hash del original y paráfrasis fiel;
- intención del usuario;
- estado final esperado;
- operaciones o capacidades necesarias;
- posible encadenamiento;
- datos y preferencias involucrados;
- clase de riesgo;
- necesidad o no de confirmación y por qué;
- evidencia necesaria para declarar éxito;
- respuesta natural esperada;
- alternativa y recuperación ante fallo.

Las instrucciones puramente de ingeniería —por ejemplo hacer un commit,
vigilar un soak o editar documentación— no se convierten artificialmente en
tools de usuario. Sí se conservan y se traducen a restricciones, regresiones o
procedimientos cuando contienen una lección de producto. Las misiones reales,
ejemplos de comportamiento y requisitos funcionales sí forman acceptance.

Deduplica variantes semánticas sin perder procedencia. Publica métricas de
cobertura: fuentes revisadas, casos únicos, dominios, cadenas, riesgos,
respuestas y casos todavía no implementados. El producto no está listo si los
casos históricos desaparecen silenciosamente.

Cada mensaje original debe apuntar exactamente a uno de estos resultados:

- misión canónica implementada y aprobada;
- conversación/pregunta respondida correctamente sin tools;
- petición peligrosa o irreversible gestionada por la política correcta;
- petición dependiente de costo, credenciales, cuenta, hardware o estado
  externo que BAXY detecta y conduce honestamente hasta el siguiente paso;
- duplicado enlazado a un caso canónico equivalente;
- blocker de release todavía no resuelto.

No existe la categoría “lo omitimos porque había demasiados mensajes”. Un caso
histórico técnicamente solucionable que siga sin capacidad es blocker de 1.0.
Una negativa segura, una solicitud de confirmación o un bloqueo externo solo
cuentan como aprobado cuando sean el comportamiento correcto para esa petición.

Además crea una matriz docs/lessons_to_regressions.md que conecte cada fallo,
bug o decepción histórica con:

- causa raíz conocida o hipótesis pendiente;
- decisión de diseño actual;
- prueba automática;
- gate físico cuando corresponda;
- evidencia necesaria para cerrarlo;
- estado actual.

No basta con decir “aprendimos”. El aprendizaje debe vivir en el diseño y en
una prueba que impida repetir el error.

agent_evidence_ledger.md debe registrar qué sesiones fueron consultadas, qué
afirmaron, su hash de segmento, la evidencia que las confirma o contradice y
el requisito, ADR o regresión resultante. Una conclusión repetida por muchos
agentes no cuenta como evidencia independiente si todos heredaron la misma
fuente.

## 4. Contrato funcional no negociable

### Conversación y resultado

- Entrada por voz y texto; ambas llegan al mismo cerebro de misión.
- BAXY actúa, verifica y contesta qué hizo.
- Respuesta mínima posible, pero suficiente para entender el resultado.
- Durante misiones largas conversa por hitos útiles, no con ruido técnico.
  Ejemplo: “Abrí Word. Ya estoy preparando el documento… ¿de qué quieres que
  trate?”.
- Si necesita información que cambia la misión, pregunta en el momento justo.
- Si una ruta falla, explica brevemente y prueba alternativas seguras.
- Distingue claramente entre hecho, en curso, pendiente, bloqueado y fallido.
- Nunca diga “listo” basándose solo en que envió un clic o una solicitud:
  comprueba el efecto real.

### Planificación y herramientas

- Debe concatenar capacidades para resolver objetivos, no exigir al usuario que
  formule cada paso.
- Rediseña desde cero el sistema de herramientas. No vuelvas a exponer más de
  500 tools planas al modelo.
- Construye un conjunto compacto de operaciones tipadas y verificables, y
  compón sobre ellas skills, workflows y planes dinámicos.
- Deriva las operaciones desde el corpus histórico completo. No crees una tool
  por frase: busca primitivas reutilizables cuyo conjunto y composición puedan
  alcanzar todos los estados finales históricos.
- Organiza el sistema en capas explícitas:

  1. operaciones atómicas con un efecto claro;
  2. providers/adapters para aplicaciones, APIs y Windows;
  3. verificadores independientes del ejecutor;
  4. skills o plantillas para patrones frecuentes;
  5. planner que construye cadenas nuevas con las mismas operaciones.

- Cada operación declara schema, efecto, riesgo, precondiciones, recursos,
  timeout, ejecutor, verificador, idempotencia, compensación, redacción y
  errores recuperables.
- Mantén una matriz bidireccional:
  mensaje histórico → misión → pasos → operaciones → provider → verificación →
  prueba, y operación → todos los mensajes que ayuda a resolver.
- Si un caso no puede resolverse, identifica la primitiva general que falta. No
  agregues un parche especial para la frase salvo que represente una semántica
  de dominio genuinamente distinta.
- El modelo solo recibe candidatos pertinentes a la misión, nunca el catálogo
  completo.
- Separa planificación, grounding, autorización, ejecución, verificación,
  compensación y narración.
- Conserva guardas determinísticas donde eviten falsos positivos: shortlist,
  negación, no_tool, read/write gates, vouch, identidad del proveedor,
  idempotencia y dispatcher controlado.
- Prefiere integraciones nativas/API cuando sean más fiables; usa UI
  Automation/accesibilidad, automatización del navegador, OCR y visión como
  alternativas. Debe poder combinar ambos caminos.
- Mantén estado de misión y recuperación después de un fallo, reinicio o
  cambio inesperado de ventana.
- Evalúa el ecosistema por porcentaje de misiones históricas resueltas,
  composición, verificación y recuperación; nunca por cantidad bruta de tools.

### Memoria local

- Guarda localmente preferencias, decisiones, nombres, hábitos y contexto que
  ayuden de verdad.
- La memoria debe ser inspeccionable, corregible y borrable por el usuario.
- Distingue hechos explícitos, preferencias inferidas y contexto temporal.
- Una inferencia débil no se convierte silenciosamente en preferencia
  permanente.
- Usa memoria para elegir mejor, por ejemplo reproducir el estilo musical que
  la persona suele pedir, y ofrece variedad sin volverse intrusivo.
- No envíes memoria ni información sensible a servicios externos salvo
  decisión explícita y visible del usuario.

### Interfaz

- Conserva el diseño visual actual de la GUI como base; está en legacy.
- Cambia el cableado y comportamiento que haga falta, no el aspecto por gusto.
- La conversación es el centro.
- El visor técnico/JSON queda apagado por defecto y solo accesible en
  diagnóstico opt-in. Nunca bloquea ni sustituye la respuesta natural.
- Voz, texto, progreso, preguntas y resultado deben verse como una conversación
  coherente.

### Personalidad

- Base amigable, directa y emocional.
- Se adapta al usuario sin imitarlo de manera caricaturesca.
- No habla como terminal, auditor, desarrollador o formulario.
- No inunda con advertencias ni pide confirmaciones redundantes.
- Cuando no sabe, lo dice y propone una vía concreta.

## 5. Política de acción, riesgo y confirmación

El principio no es “confirmar todo lo que cambia algo”, sino confirmar cuando
existe una consecuencia difícil de deshacer o un riesgo monetario, de
seguridad, privacidad o pérdida de trabajo.

Normalmente ejecutar sin confirmación extra cuando la instrucción actual es
clara:

- abrir una aplicación;
- cambiar volumen o reproducción;
- buscar información;
- crear contenido recuperable;
- cerrar una aplicación sin trabajo pendiente;
- instalar una aplicación conocida, gratuita o ya adquirida desde una fuente
  confiable, si no aparecen costos, permisos peligrosos o términos
  inesperados;
- otras acciones reversibles y de bajo impacto.

Confirmar o resolver la ambigüedad antes de:

- comprar, suscribirse, alquilar, donar o aceptar un costo;
- revelar datos, credenciales o contenido sensible;
- actuar sobre seguridad, cuentas, permisos elevados o privacidad;
- borrar definitivamente, sobrescribir sin recuperación o dañar el sistema;
- cerrar Word, un editor u otra aplicación cuando exista trabajo no guardado;
- enviar comunicaciones sensibles, masivas, ambiguas o a un destinatario no
  corroborado;
- instalar ejecutables desconocidos, cambiar protecciones o aceptar permisos
  de riesgo;
- realizar una acción material que BAXY infirió pero el usuario no pidió.

Una orden explícita del turno actual cuenta como autorización para la acción
ordinaria descrita; no vuelvas a preguntar lo mismo por formalismo. En cambio,
una compra, un destinatario dudoso, contenido sensible o un efecto no anunciado
requiere información adicional. Cuando haya una alternativa reversible,
ofrécela primero. Rechaza operaciones cuyo propósito previsible sea destruir o
comprometer el equipo, como borrar System32, aunque puedan formularse con una
confirmación.

Codifica esta política como un clasificador de efectos explicable y probado,
no como una lista dispersa de ifs.

## 6. Ejemplos que el producto debe resolver
(Todos los mensajes que se han enviado a Baxy o carter desde el inicio de los logs)
### Música
Usuario: “Baxy, pon música”.

BAXY consulta contexto y preferencias, elige razonablemente, ejecuta,
comprueba la sesión multimedia y responde algo como: “Listo, puse Billie Jean
de Michael Jackson en Spotify”.

No responde con JSON ni “spotify.play devolvió success=true”.

### Misión compuesta

Usuario: “Instálame Batman Arkham Knight en Steam y pon una canción de Michael
Jackson en Spotify”.

BAXY debe descomponer y coordinar:

1. Corroborar Steam, sesión, biblioteca/propiedad, espacio y estado de descarga.
2. Si el juego ya es del usuario y no hay costo, iniciar la instalación y
   verificar que quedó descargando.
3. Si hay que comprarlo o aceptar un costo, preguntar antes de la compra, pero
   continuar con la parte independiente que sí está autorizada.
4. Buscar una canción adecuada de Michael Jackson, reproducirla y verificar la
   reproducción.
5. Informar por hitos naturales: “Steam ya está descargando Batman: Arkham
   Knight. También puse Billie Jean en Spotify”.

No debe confundir “abrí la ficha” con “instalé”, ni “envié play” con “está
sonando”.

### Documento

Usuario: “Abre Word y ayúdame a escribir un documento”.

BAXY abre Word, verifica la ventana, conversa para obtener tema y requisitos,
va escribiendo y comunica el progreso. Si después se le pide cerrar y hay
cambios sin guardar, pregunta qué hacer.

### Fallo y alternativa

Si Spotify no responde, BAXY dice algo breve como “Spotify no respondió;
probaré abrirlo de nuevo”, reintenta mediante una alternativa acotada y solo
declara éxito tras verificar. Si todas las alternativas fallan, explica el
bloqueo real sin inventar.

## 7. Arquitectura que debes evaluar

Ninguna tecnología está elegida. No asumas Python, Rust, .NET, React, Tauri,
FastAPI, SQLite, ONNX, Gemma, llama.cpp, Piper, Playwright ni ningún componente
porque ya exista, porque aparezca en documentacion\04 o porque resulte cómodo.
Ese documento es un mapa de candidatos históricos, no el stack aprobado. La
reutilización reduce costo, pero no concede ventaja técnica.

Lo fijo es el contrato del producto: Windows local y privado, conversación
natural, identidad visual de la GUI, accesibilidad, misiones concatenadas,
efectos verificados, seguridad proporcional y perfil cómodo en 4 GB de VRAM.
Todo lo demás se cuestiona, incluyendo lenguaje, fronteras de procesos, modelo
único frente a especialistas, uso o ausencia de LLM en routing, almacenamiento,
IPC, voz, visión, tool engine y empaquetado.

Antes de cerrar arquitectura ejecuta un torneo tecnológico de base cero:

1. Compara al menos tres alternativas serias por subsistema cuando existan y
   la opción de eliminarlo o absorberlo en otra capa.
2. Compara como sistemas completos, al menos, un core Python, uno .NET/Windows
   y uno Rust o una alternativa contemporánea mejor justificada.
3. Implementa cortes verticales mínimos equivalentes —entrada, decisión,
   acción segura simulable o reversible, verificación y respuesta—; no elijas
   solo leyendo documentación.
4. Usa el mismo hardware, corpus histórico, datos y protocolo. Publica
   versiones, hashes, comandos, resultados crudos y fallos.
5. Puntúa antes de conocer el ganador: misiones verificadas 25 %, recursos
   15 %, latencia 10 %, UX/accesibilidad 10 %, privacidad/seguridad 10 %,
   instalación/lifecycle 10 %, mantenibilidad/testabilidad 10 %,
   licencia/madurez 5 % y migración/reutilización 5 %.
6. Si cambias pesos, hazlo antes de medir y justifícalo por producto; nunca
   ajustes la métrica para favorecer al incumbente.
7. Evalúa la frontera de Pareto y la interacción entre componentes. La suma de
   ganadores aislados puede ser peor que una arquitectura coherente.
8. Registra ganador, fallback y alternativas descartadas en ADRs con evidencia.

No construyas tres productos completos: construye el experimento mínimo que
pueda falsar cada hipótesis y profundiza solo en las opciones competitivas.
Descarta temprano lo incompatible con Windows, privacidad, licencia o el
presupuesto, dejando la evidencia de descarte.

No impongo clases ni modelos concretos, pero la solución debe cubrir estas
responsabilidades con límites claros:

Usuario por voz/texto/pantalla
→ percepción, wake/VAD/STT y contexto
→ conversación y estado de misión
→ planner de objetivos
→ shortlist de capacidades
→ grounding de entidades y parámetros
→ clasificación de efecto/riesgo
→ autorización
→ ejecutor de operaciones tipadas
→ verificador de estado real
→ compensación/rollback o alternativa
→ memoria y aprendizaje local
→ narrador natural
→ GUI/TTS

Investiga si Gemma 4 E2B QAT y llama.cpp siguen siendo una opción competitiva
para chat, visión, STT y decisiones acotadas bajo el presupuesto; no parten
como ganadores. Compara una arquitectura unificada con especialistas y con
rutas determinísticas. Piper es solo candidato TTS. Mantén fallbacks
reproducibles mediante configuración, sin editar código.

Restricción dura: el perfil de producto debe ser cómodo en equipos Windows con
4 GB de VRAM y apuntar aproximadamente a 3 GB de uso cuando sea viable. No
declares validación física de 4 GB si solo mediste en una GPU mayor. Incluye
CPU fallback y degradación gradual. Mide RAM, VRAM base/pico/retenida, arranque,
latencia, calidad, estabilidad y consumo.

No actives características experimentales como speculative/MTP/DSpark por
defecto sin evidencia local de estabilidad y presupuesto. Sanitiza entradas de
usuario, OCR, RAG, archivos y outputs de tools, incluidos bytes NUL. Controla
PID, identidad del modelo, parent, puerto y cleanup para no confundir servidores
viejos con nuevos.

## 8. Estrategia de construcción

Trabaja por cortes verticales utilizables:

1. Reconstrucción de la genealogía Carter → BAXY y de sus lecciones.
2. Descubrimiento, corpus histórico y matriz de regresiones.
3. Contrato de producto, riesgos y criterios del torneo tecnológico.
4. Prototipos comparables y decisión de arquitectura basada en mediciones.
5. Núcleo conversacional mínimo de punta a punta: pedir → actuar → verificar →
   responder naturalmente.
6. Primer conjunto de operaciones tipadas y composición de misiones.
7. Voz, memoria, visión y computer-use.
8. Expansión guiada por el ledger histórico, no por cantidad decorativa.
9. Integración y reutilización visual de la GUI existente.
10. Empaquetado, instalación, diagnóstico, actualización y desinstalación.
11. Comparación física contra las mejores capacidades de Carter, FunctionGemma
    y BAXY anterior.
12. Pruebas físicas y estabilización.
13. Soak largo solo al final, después de que BAXY ya cumpla misiones reales. No
    conviertas el soak en sustituto de construir el producto. El usuario ha
    reservado la prueba de 24 horas para el sábado.

Después de cada cambio importante, ejecuta pruebas proporcionales. Haz commits
pequeños y claros. Revisa siempre branch, status y cambios ajenos. No uses
git reset --hard ni reviertas trabajo del usuario. No modifiques legacy.

### Contexto persistente obligatorio

Al comenzar, crea una carpeta versionada `contexto` en la raíz. Será la memoria
operativa de la misión para que un reinicio, compactación o sesión nueva pueda
continuar sin reconstruir el razonamiento desde cero. Debe tener esta estructura
inicial, que puedes ampliar sin convertirla en un vertedero:

```text
contexto/
  README.md
  00_control/
    MAPA.md
    ESTADO_ACTUAL.md
    ALCANCE_Y_DEFINITION_OF_DONE.md
  01_producto/
    VISION_Y_DECISIONES_DEL_USUARIO.md
    CORPUS_HISTORICO_Y_CUTOFF.md
    MISIONES_PRIORIZADAS.md
  02_historia/
    FUENTES_Y_GENEALOGIA.md
    LECCIONES_RECUPERADAS.md
  03_investigacion/
    HALLAZGOS.md
    ALTERNATIVAS_Y_EVIDENCIA.md
  04_arquitectura/
    DECISION_VIGENTE.md
    ADR/
  05_implementacion/
    MAPA_DEL_SISTEMA.md
    CAMBIOS_Y_MIGRACIONES.md
  06_pruebas_y_mediciones/
    MATRIZ_DE_ACEPTACION.md
    MENSAJE_A_MISION_TOOL_PRUEBA.md
    RESULTADOS.md
  07_riesgos_y_pendientes/
    BLOQUEANTES.md
    BACKLOG_POST_ENTREGA.md
  08_entrega/
    RELEASE_CHECKLIST.md
    OPERACION_Y_ROLLBACK.md
```

Reglas de uso:

- `00_control/ESTADO_ACTUAL.md` es el punto de reanudación: fase, porcentaje
  calculado contra Definition of Done, último commit bueno, cambios sin commit,
  procesos/puertos relevantes, pruebas recientes, bloqueantes y tres próximos
  pasos concretos.
- `00_control/MAPA.md` indica qué archivo es canónico para cada tema. No copies
  la misma conclusión en cinco lugares: resume y enlaza.
- Registra toda decisión material, hallazgo, fallo, medición, cambio de rumbo,
  limitación y compromiso de producto con fecha, procedencia, confianza,
  impacto y destino.
- Mantén en `CORPUS_HISTORICO_Y_CUTOFF.md` el límite exacto de fuentes y en
  `MENSAJE_A_MISION_TOOL_PRUEBA.md` el estado de cobertura de cada mensaje.
- Actualiza contexto después de cada hito, benchmark, fallo importante, ADR,
  commit y cambio de fase; también antes de iniciar un proceso largo o cerrar
  una sesión.
- Al reanudar, lee primero README, MAPA, ESTADO_ACTUAL y
  ALCANCE_Y_DEFINITION_OF_DONE; después abre únicamente las subcarpetas
  necesarias.
- No copies logs masivos, modelos, binarios ni las sesiones privadas de agentes.
  Guarda resúmenes y enlaces verificables a la evidencia original.
- Nunca guardes contraseñas, tokens, contenido privado innecesario ni secretos.
- No borres contradicciones: marca la decisión anterior como sustituida y enlaza
  la nueva evidencia.
- La carpeta contexto ayuda a recordar; no reemplaza tests, artefactos, Git ni
  documentación de usuario.

### Alcance finito y obligación de terminar

El objetivo es entregar la mejor **versión terminada dentro de un alcance
explícito**, no perseguir una perfección universal ni mantener la misión abierta
porque todavía existan mejoras posibles.

Durante la primera fase escribe `ALCANCE_Y_DEFINITION_OF_DONE.md` y separa:

- **Must para BAXY 1.0:** todos los mensajes históricos hasta el cutoff,
  deduplicados en misiones canónicas pero con trazabilidad individual, además de
  seguridad, instalación, recuperación, recursos y evidencia de producto.
- **Should si cabe:** mejoras de calidad que superan el resultado histórico
  esperado sin ser necesarias para resolverlo confiablemente.
- **Después de 1.0:** capacidades nunca pedidas en el corpus, optimizaciones no
  necesarias y experimentos.

Congela el alcance 1.0 después de completar y auditar la extracción histórica y
el torneo tecnológico. Ningún mensaje histórico solucionable puede enviarse al
backlog post-entrega. Después del congelamiento solo entra trabajo nuevo si
corrige un P0/P1, una regresión, un caso histórico fallido o un criterio Must.
Mejoras que excedan esos resultados van a `BACKLOG_POST_ENTREGA.md`.

Aplica estas reglas de parada:

1. Investiga hasta tener alternativas serias y una prueba capaz de distinguirlas;
   no sigas acumulando fuentes que no cambiarían la decisión.
2. Prototipa para falsar hipótesis, no para perfeccionar todos los candidatos.
3. Cuando una opción gana el protocolo publicado y cumple los límites, elígela
   y avanza; reabre la decisión solo ante evidencia material nueva.
4. Corrige causas raíz de fallos Must. Los P2/P3 solo pueden aplazarse si no
   hacen fallar ningún mensaje histórico ni impiden uso confiable.
5. Cuando la matriz de aceptación pasa, no agregues funciones ni refactors por
   iniciativa propia. Empaqueta, verifica la instalación, documenta y entrega.
6. “Podría ser mejor” no es un bloqueante. “No cumple un Must reproducible” sí.

El soak de 24 horas es una calificación extendida y acotada, ejecutada solo
cuando el producto ya cumple misiones reales. Si el usuario lo pospone, no
esperes ni mantengas todo el desarrollo abierto: entrega el producto instalable
con esa certificación marcada como pendiente y deja el comando/protocolo listo.
Cuando se ejecute, no lo confundas con una invitación a optimizar sin fin.

## 9. Calidad y pruebas obligatorias

Construye pruebas unitarias, de contrato, integración, replay histórico y E2E
real. No aceptes mocks como única evidencia de una capacidad física.

### Contrato conversacional

- “Listo” solo después de verificación.
- Respuesta natural, breve y específica.
- Cero JSON/trazas en la conversación normal.
- Progreso por hitos en misiones largas.
- Preguntas solo cuando aportan información o autorización necesaria.
- Estado honesto ante fallos y recuperación.

### Routing y planificación

- no_tool, saludo, chat y preguntas generales no disparan acciones.
- negación y referencias ambiguas.
- shortlist restringido.
- parámetros, entidades, destinatarios y aplicaciones corroborados.
- misiones con dos o más capacidades, dependencias, paralelismo y fallo
  parcial.
- replanificación, idempotencia y reanudación.

### Riesgo

- matriz completa de reversible/irreversible, dinero, privacidad, seguridad y
  trabajo no guardado.
- no hay confirmation fatigue.
- comprar pide confirmación.
- instalar desde fuente confiable sin costo no pide confirmación redundante.
- cerrar Word con cambios protege el trabajo.
- cerrar una app sin cambios no dramatiza.
- solicitudes destructivas del sistema se bloquean.

### Capacidades reales

Inventaría todos los dominios y misiones encontrados en la tesis y el
historial: aplicaciones, ventanas/escritorio, archivos y búsqueda local,
volumen/audio, música/streaming, web/navegador, recordatorios/calendario/notas,
estado del PC, documentos/Office, mensajería, instalación y launchers de
juegos, accesibilidad, OCR/visión, periféricos, red y preferencias. No copies
el catálogo histórico: demuestra cobertura mediante operaciones composables.

Para 1.0, **todas las misiones históricas canónicas son Must**. Deduplicar frases
equivalentes evita recrear aliases, pero no permite perder solicitudes ni
procedencia. Implementa todas las operaciones generales necesarias para
resolverlas; no reconstruyas más de 500 tools planas si un conjunto menor y
componible alcanza los mismos resultados.

Además del replay completo del corpus, usa como smoke prioritario:


- “abre X”;
- volumen;
- música exacta y por preferencia;
- streaming;
- búsqueda web;
- recordatorios;
- estado del PC;
- saludos/no_tool/chat;
- visión y OCR;
- instalar un juego ya adquirido;
- misión Steam + Spotify;
- documento Word conversacional;
- mensajes con destinatario corroborado;
- caída del modelo/servidor y fallback;
- puerto ocupado, reinicio, inputs con NUL y procesos huérfanos.

### Voz y visión

- español, inglés y spanglish;
- “Baxy”, Spotify, YouTube, Netflix, Chrome, Discord y GitHub;
- silencio/ruido devuelve vacío o no activa herramientas;
- WAVs históricos y voz real cuando sea posible;
- pantalla, OCR, películas conocidas y juegos ambiguos;
- usa título de ventana, proceso, OCR y otras señales como ground truth;
- si no existe corroboración, no inventa identidades.

### Estabilidad y recursos

- suite completa en verde;
- gates físicos reproducibles;
- múltiples imágenes seguidas y detección de crecimiento retenido;
- reinicio y recuperación;
- RAM/VRAM/latencia/calidad documentadas;
- sin secretos en logs;
- sin procesos ni puertos abandonados;
- instalación limpia, doctor, actualización y desinstalación probadas.

Antes del soak largo realiza pruebas cortas y misiones reales. El soak final
debe medir duración, operaciones, gaps, reinicios, RAM/VRAM, errores, limpieza
y artefactos verificables. No declares “estable 24 h” con una ejecución
interrumpida ni declares hardware de 4 GB validado sin ese hardware.

## 10. Criterios de aceptación

BAXY se considera listo únicamente cuando:

- la genealogía Carter → BAXY está documentada y sus descubrimientos útiles
  tienen un destino explícito;
- existe trazabilidad desde cada requisito histórico hasta implementación y
  prueba, o una decisión explícita y justificada;
- el 100 % de los mensajes históricos extraídos está enlazado a una misión
  canónica, caso conversacional, duplicado o comportamiento de seguridad;
- el 100 % de las misiones canónicas tiene estado final esperado, plan u
  operaciones necesarias, evidencia y prueba de aceptación;
- no queda ningún mensaje histórico técnicamente solucionable marcado como
  unsupported, backlog o “pendiente de diseñar”;
- el replay completo del corpus pasa y los providers/operaciones que producen
  efectos reales tienen gates físicos representativos; las peticiones
  destructivas, monetarias o privadas se prueban sin ejecutar daño ni gasto;
- cada fallo histórico importante tiene una regresión o un gate que impide
  repetirlo;
- la arquitectura elegida venció alternativas reales mediante un protocolo
  publicado y ninguna tecnología fue conservada solo por comodidad;
- el usuario puede hablar o escribir y completar misiones reales;
- concatena capacidades y se recupera de fallos parciales;
- verifica efectos físicos antes de narrarlos;
- responde como BAXY, no como un inspector técnico;
- memoria y preferencias son locales, útiles y controlables;
- la política de confirmación coincide con el riesgo real;
- GUI conserva su identidad visual y centra la conversación;
- el perfil de bajo consumo tiene mediciones honestas y fallback;
- tests, gates reales, empaquetado y cleanup pasan;
- existe un instalador o paquete reproducible que inicia BAXY sin depender de
  una terminal de desarrollo y un flujo de desinstalación/rollback probado;
- no quedan P0/P1 conocidos; los P2/P3 no bloqueantes están documentados con
  impacto, workaround y prioridad;
- `contexto/00_control/ESTADO_ACTUAL.md` y la matriz de aceptación reflejan el
  estado final real y permiten auditar cómo se llegó a la entrega;
- documentación reproduce instalación, configuración, mediciones, riesgos y
  rollback;
- no quedan capacidades ficticias, mocks presentados como producto ni números
  inflados por aliases.

La cobertura debe medirse por misiones y estados finales, no por cantidad de
tools. Una operación que no puede verificar su efecto no está terminada. Una
misión histórica solo cuenta como resuelta si alcanza el efecto autorizado o
produce correctamente la pregunta, confirmación, negativa o explicación de
dependencia externa que exige su contexto.

### Regla inequívoca de finalización

Cuando todos los criterios Must, el corpus histórico completo y la matriz de
aceptación estén satisfechos, BAXY 1.0 está terminado. En ese momento:

1. genera el artefacto instalable y su checksum;
2. realiza una instalación limpia y las misiones de smoke finales;
3. congela versiones, dependencias y configuración reproducible;
4. mueve toda mejora no bloqueante al backlog posterior;
5. actualiza contexto y documentación de entrega;
6. crea el commit final y entrega el producto;
7. marca el objetivo como completado y detente.

No abras una nueva ronda de investigación, reescritura, optimización o expansión
después de cumplir estos pasos. “Definitivo” significa la mejor versión
entregable y demostrada dentro del alcance 1.0, no un asistente teóricamente
perfecto ni capaz de todos los casos futuros.

Antes de declarar “BAXY definitivo”, ejecuta una comparación documentada contra
las mejores versiones anteriores. El nuevo BAXY debe conservar o superar sus
casos útiles, reducir complejidad accidental, mejorar la conversación y
verificación, y explicar cualquier capacidad que todavía no alcance. No basta
con ser más limpio: debe ser objetivamente el mejor BAXY construido hasta ese
momento.

## 11. Forma de trabajo y entrega

Empieza ahora. Puedes realizar acciones reversibles y necesarias dentro de los
repositorios sin pedir permiso. Para acciones externas, monetarias, privadas,
de seguridad o destructivas aplica el mismo contrato que estás construyendo.
No uses permisos generales como autorización para compras, publicaciones,
mensajes reales no solicitados, borrados destructivos o exposición de datos.

Mantén al usuario informado con actualizaciones breves y naturales. Si una
hipótesis falla, cambia de rumbo con evidencia. No te detengas en la primera
implementación ni declares éxito por conteos de tests si nunca ejecutaste la
aplicación y misiones físicas.

Entrega final:

- qué fuentes históricas investigaste;
- qué hallazgos de agentes recuperaste y dónde quedaron convertidos en pruebas;
- qué sesiones de agente consultaste, qué afirmaciones corroboraste o
  rechazaste y cómo se conserva su procedencia;
- contrato de producto consolidado;
- torneo tecnológico, mediciones, arquitectura ganadora, frontera de Pareto y
  alternativas descartadas;
- capacidades y misiones implementadas;
- trazabilidad completa de mensajes históricos, casos canónicos, operaciones y
  pruebas, con conteos raw/deduplicados/aprobados/bloqueados;
- pruebas unitarias, integración, replay y físicas;
- tabla de calidad, latencia, RAM y VRAM;
- fallos encontrados y causas raíz;
- riesgos y límites restantes;
- instalación, uso, diagnóstico, privacidad y rollback;
- artefacto instalable, checksum y resultado de instalación limpia;
- snapshot final de contexto, Definition of Done y backlog post-entrega;
- branch y commits;
- demostración verificable de varias misiones reales, incluida una misión
  compuesta.

Tu objetivo no es conservar el BAXY anterior. Tu objetivo es cumplir mejor su
visión: que una persona diga lo que necesita, BAXY lo haga de forma segura y
confiable, y después se lo cuente como lo haría un amigo competente. Construye
la versión definitiva aprendiendo de toda la familia Carter/BAXY: hereda sus
mejores descubrimientos, elimina sus errores recurrentes y demuestra con
misiones reales que esta versión es la mejor de todas dentro del alcance 1.0.
Después de demostrarlo, entrégala y termina: no conviertas “definitivo” en una
excusa para iterar eternamente.

Notas adicionale:
Ingles/Español y spanglish es en lo que se enfoca baxy
No es escencial compatiblidad con otros idiomas, si wake word es mejor en frances, eso no suma nada a baxy por ej
Su transcripcion funciona bien en chino, eso no importa
Baxy debe ser rapido, nunca demorarse en tareas simples
Baxy debe sentirse como un jarvis
