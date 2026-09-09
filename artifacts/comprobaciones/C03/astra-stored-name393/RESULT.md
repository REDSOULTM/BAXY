# 393 — lecturas del nombre guardado por su ruta privada

Se amplió `NaturalMemoryRequestParser.NameRecallPattern` para las preguntas ES/EN
sobre el nombre guardado. Reutiliza `memory.recall`, scope `exact`, selector
`name`; no introduce prosa, catálogo, caché, permisos ni configuración del modelo.
Las consultas genéricas de nombre mantienen por ahora su comportamiento anterior.

Antes de fuente: **10 fallos, 10 pass, 0 skips, 1m26s**. Fallaban las ocho
construcciones explícitas y las dos consultas nuevas del flujo con almacén.
El flujo inglés llegaba al modelo y negaba la capacidad: “I don't store or save
personal names in private memory.” El valor sí estaba guardado en el perfil de prueba.

Después de fuente: **20 pass, 0 fallos, 0 skips, 1m08s**. Las nueve exclusiones
conservan negación, tercero, traducción, futuro, otra ubicación o composición.
El flujo conserva también la consulta genérica anterior; cada caso crea un nombre
aleatorio, lo guarda mediante confirmación y lo recupera tras abrir otra sesión.

Comandos y evidencia:

- `dotnet test tests/Baxy.Integration.Tests -c Release --nologo -v:minimal --filter
  'FullyQualifiedName~StoredNameQuestionsReadTheExactPrivateName|FullyQualifiedName~OtherNameLanguageDoesNotAuthorizeAStoredNameRead|FullyQualifiedName~ViewModelBindsRequestedNameAndRecallsItAfterANewSession'`:
  baseline.log y focal.log, resultados indicados arriba.
- Seis suites dueñas con `dotnet test ... --no-build` y filtro MemoryAppFlow,
  MemoryTurnSession, MemoryOperationProtection, NaturalMemoryRequestParser,
  NaturalSystemStatusRequestParser y RequestReadingConformance:
  **1996 pass, 0 fallos, 0 skips, 2m59s**, owners-dotnet.log.
- `scripts/test_source_quality.ps1`: **Fast verde entero**, build Release
  **17,97s, 0 warnings, 0 errores**, fast.log. No Full durante reparación.

Esto valida el transporte y el almacén. La prosa real del producto se medirá por
separado en 393b; no se declara resuelto el recuerdo conversacional, quién soy,
UI, voz física ni aceptación fresca. No se promovió ningún runtime.
