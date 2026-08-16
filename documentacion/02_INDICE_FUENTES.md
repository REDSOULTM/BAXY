# Índice de fuentes históricas

## 1. BAXY archivado

Ruta:

C:\Users\usuario\Desktop\ETC\Programacion\BAXY\legacy

Puntos de entrada:

- legacy\README.md
- legacy\Codex.md
- legacy\ContextoFable.md
- legacy\docs
- legacy\tests
- legacy\data
- legacy\scripts
- legacy\Experimentando
- historial de Git hasta ee06786

Inventario comprobado:

- 916 archivos versionados del checkpoint están preservados en legacy.
- 27 documentos bajo legacy\docs.
- 97 archivos contienen marcadores asociados con agentes, auditorías, Gemma,
  Spotify, perfiles o soak.

Prioridad:

1. decision_log, dependency_map, backlog e inventory;
2. contratos de seguridad y cobertura de Tool Ecosystem v2;
3. pruebas de misión y routing;
4. scripts y artefactos de gates físicos;
5. conversaciones Codex/ContextoFable;
6. implementación, únicamente para comprender causas y primitivas.

## 2. Probando Gemma 4 y Carter

Ruta:

C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4

Contiene la historia más extensa de Carter, Gemma, voz, visión, routing,
computer-use, memoria, recursos y estabilidad.

Inventario observado:

- 852 archivos Markdown.
- más de 2.000 archivos JSON, JSONL o TSV.

Directorios prioritarios:

- documentacion\00_producto
- documentacion\01_arquitectura
- documentacion\02_router
- documentacion\03_voz_stt
- documentacion\04_computer_use
- documentacion\05_vision_camara
- documentacion\06_vram_estabilidad
- documentacion\07_latencia
- documentacion\08_memoria_jarvis
- documentacion\09_finetune
- documentacion\10_auditorias
- documentacion\11_research_recibido
- documentacion\_backlog
- documentacion\_historico
- ContextoGPT.md
- gemma4_agent
- evaluaciones, corpus, grabaciones y datos crudos

## 3. Visión de tesis

Ruta:

C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\_tesis_curso\entregables

Las fuentes Markdown son canónicas. Los PDF, DOCX y PPTX se consultan cuando
añaden información no presente en Markdown.

Documentos clave:

- INFORME_FINAL_COMPLETO.md
- PORTAFOLIO_COMPLETO.md
- README de entregables
- objetivos, alcance, solución, escenarios y conclusiones

La tesis define la misión y los resultados esperados, no obliga a conservar sus
tecnologías históricas.

## 4. FunctionGemma

Ruta:

C:\Users\usuario\Desktop\ETC\Programacion\FunctionGemma

Inventario observado:

- 227 módulos Python.
- 550 archivos JSON, JSONL, YAML o YML.
- 27 documentos Markdown.

Puntos de entrada:

- README_TOOLS.md
- INTEGRATION_HANDOFF.md
- KVA_GATE_HANDOFF.md
- router\README_ROUTER.md
- router\data
- tools\domain_tools
- corpus, evaluaciones y scripts de extracción de historial

Dominios históricos incluyen accesibilidad, audio, backups, Bluetooth,
calendario, contactos, contenedores, creatividad, datos, bases de datos,
desarrollo, escritorio, dispositivos, documentos, archivos, formularios,
juegos, hábitos, búsqueda local, mantenimiento, multimedia, red, notas,
Office, periféricos, fotos, impresión, rutinas, estudio, watchers, WhatsApp y
Wi-Fi.

No deben reconstruirse como cientos de tools planas. Se usan para recuperar
misiones y diseñar operaciones composables.

## 5. Conversaciones e informes de agentes

La recuperación local del hilo raíz
019f5027-c684-75a1-a47b-5af2edd2339b examinó 424 sesiones y reconstruyó 322
descendientes: 302 directas, 19 de profundidad 2 y una de profundidad 3. La UI
mostró 315 tarjetas; la diferencia puede incluir reintentos, sesiones anidadas,
interrupciones o criterios de agrupación. El grafo de sesión es la referencia
reproducible, no el contador visual.

Puntos de entrada versionados:

- documentacion\agentes\README.md;
- documentacion\agentes\INDICE.md;
- documentacion\agentes\manifest.json;
- scripts\export_codex_subagents.py.

Archivo local privado, ignorado por Git:

- documentacion\agentes\privado\hilo_raiz.jsonl.gz;
- documentacion\agentes\privado\sesiones, con 322 segmentos comprimidos;
- documentacion\agentes\privado\manifest_private.json;
- documentacion\agentes\privado\informes_finales.jsonl.

Los segmentos comienzan en la asignación NEW_TASK propia de cada agente, por lo
que eliminan la mayor parte del contexto heredado duplicado. Conservan mensajes
publicados, resúmenes de razonamiento expuestos, tool calls, outputs, patches,
finales y hashes. La materia prima referenciada suma 5,10 GiB; los segmentos
propios suman 386,18 MiB sin comprimir y 131,15 MiB comprimidos.

Además de este archivo recuperado, las conclusiones materializadas se buscan
en:

- legacy\Codex.md;
- legacy\ContextoFable.md;
- docs y decision logs archivados;
- commits y mensajes de Git;
- tests añadidos como consecuencia de auditorías;
- scripts y artefactos de acceptance;
- adjuntos de sesiones;
- resúmenes visibles en el hilo actual.

Limitaciones:

- el prompt exacto puede estar cifrado; se conserva el ciphertext, no se rompe;
- no se recupera razonamiento interno oculto;
- 19 sesiones quedaron clasificadas como interrumpidas y pueden carecer de
  informe final;
- una conclusión de agente sigue siendo evidencia secundaria y puede estar
  equivocada, obsoleta o repetida desde un mismo contexto heredado.

Para regenerar el archivo:

python scripts\export_codex_subagents.py --force

## Protocolo de extracción

Para cada fuente:

1. registrar ruta, fecha y tipo;
2. extraer misión, estado esperado y respuesta natural;
3. extraer fallo, causa raíz e intervención;
4. localizar prueba o evidencia;
5. clasificar como vigente, histórica, contradictoria o pendiente;
6. deduplicar conservando procedencia;
7. convertir el resultado en ledger y regresión.

Para evidencia de agentes se añade:

8. registrar session_id, agent_path y segment_sha256;
9. contrastar cada afirmación con fuente primaria, código o prueba;
10. clasificarla como corroborada, contradicha, obsoleta o pendiente;
11. no contar reiteraciones del mismo contexto como corroboración independiente.
