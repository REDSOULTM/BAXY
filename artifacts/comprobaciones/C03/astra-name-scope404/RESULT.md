# 404 — el nombre actual conserva su contexto de conversación

MainWindowViewModel deja de forzar memory.recall para una consulta genérica del
nombre cuando los últimos doce mensajes contienen una presentación del usuario.
NaturalMemoryRequestParser reconoce ese alcance reutilizando su patrón de
consulta y el de presentación. Sólo consulta mensajes con rol humano; no extrae
un nombre, no crea caché ni concede permiso de escritura. La mente interpreta
las declaraciones y correcciones completas. Las preguntas explícitas sobre lo
guardado y las sesiones sin ese contexto conservan la ruta privada.

403 demuestra la causa con la mente real: ÁlvaroES/EN, Renata y Priya frente a
hermanaCasey correctos; el producto402b había sustituido Álvaro por Jordan guardado.
Los controles de cuentaWindows403 fallan antes del modelo, quedan registrados.

- Baseline App:3failed,3passed,0skips,27s. Los tres recuerdos conversacionales
  hacían una lectura persistente y no llegaban a la mente.
- Primer focal:3failed,3passed,25s. Las garantías de ruta ya pasaban; fallaba una
  comprobación de test que abría un outbox inexistente. Se exige ahora que no
  exista tras conversación sin operaciones; las ramas privadas exigen outbox vacío.
  La lengua de la respuesta del fixture se liga a la presentación inicial.
- Focal final:6passed,0skips,25s.
- `dotnet test tests/Baxy.Integration.Tests -c Release --nologo -v:minimal
  --filter 'FullyQualifiedName~MindShellEndToEndTests|FullyQualifiedName~MemoryAppFlowTests|FullyQualifiedName~NaturalMemoryRequestParserTests|FullyQualifiedName~MemoryTurnSessionTests|FullyQualifiedName~RequestReadingConformanceTests'`:
  1905passed,0skips,5m31s.
- `scripts/test_source_quality.ps1 -Mode Fast`: verde entero, build17,78s,
  0 advertencias/errores. No Full durante reparación.

El fixture de contratos comprueba la ruta y el journal, no la calidad del modelo.
403 conserva esa medición real; producto404b se registra aparte. FuentePython397
intacta; sin cambio del runtime ni promoción. C03 permanece EN_CURSO.
