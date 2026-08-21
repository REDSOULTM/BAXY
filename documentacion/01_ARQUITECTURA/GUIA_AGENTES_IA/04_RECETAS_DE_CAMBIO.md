# Recetas de cambio

Estas recetas describen el camino completo. No todos los pasos producen una
edición en toda tarea, pero todos deben revisarse antes de concluir que el
cambio está cerrado.

## Antes de implementar

Responde por escrito, aunque sea en tus notas:

1. ¿Es un comportamiento ya existente, una corrección o una capacidad nueva?
2. ¿Qué capa es dueña de la regla?
3. ¿Cambia una operación pública, un protocolo o datos persistidos?
4. ¿Cruza un efecto externo o una frontera privada?
5. ¿Cuál será la evidencia de éxito y qué significa efecto ambiguo?
6. ¿Cómo se cancela, limita y recupera?
7. ¿Qué prueba falla antes y pasa después?
8. ¿Qué documentación deja de ser cierta?

Si la respuesta exige cambiar autoridad pública, formato durable, dependencia
mayor, instalación o un efecto real sensible, obtén la autorización
correspondiente antes de materializarlo.

## Encontrar el ownership correcto

| Cambio | Primer lugar que inspeccionar |
|---|---|
| DTO o wire JSON del core | `Baxy.Contracts` |
| catálogo, riesgo, confirmación, replay | `Baxy.Kernel` |
| cifrado, DPAPI, ruta privada | `Baxy.Security.Windows` |
| lectura/efecto Windows o store | `Baxy.Providers.Windows` |
| handler/composición/narración | `Baxy.Core` |
| turno, plan, recovery, UI o proceso hijo | `Baxy.App` |
| conversación/router/planner/voz | `baxy_mind` |
| instalación/rollback/paquete embebido | `Baxy.Setup` y scripts de entrega |
| presentación histórica | `Baxy.FieldUi`, bridge y ADR-0008 |
| build/gate/corpus | `scripts`, tests y artefactos del gate |

Busca el símbolo y sus pruebas:

Busca `NombreExacto|operacion\.exacta` con la tool `grep` acotada a `src tests`, y
luego `git log --oneline -- ruta\propietaria`.

No muevas una regla a la capa que resulta más cómoda para el caso feliz.

## Modificar una operación existente

1. Busca el nombre exacto en `ProductCatalog.cs`.
2. Identifica descriptor, riesgo, verifier y schema actuales.
3. Sigue el handler registrado desde `Baxy.Core/Program.cs`.
4. Sigue el provider o adapter y su postlectura.
5. Busca narración/proyección en Core y App.
6. Busca reconocimiento/argumentos en mind solo si el cambio es lingüístico.
7. Revisa persistencia, idempotencia y effect ambiguity.
8. Cambia primero una prueba del ownership que exprese el nuevo contrato.
9. Implementa la modificación mínima.
10. Ejecuta pruebas focalizadas y luego el gate proporcional.

No cambies el schema para acomodar un bug interno si el contrato público puede
permanecer igual.

## Añadir una operación pública

### 1. Demostrar que la operación es necesaria

Comprueba que:

- no existe una operación equivalente;
- no es solo una nueva formulación natural;
- no puede componerse con operaciones existentes;
- tiene un target y una postcondición observables;
- su riesgo puede clasificarse;
- no crea un proxy genérico o autoridad abierta.

### 2. Definir el descriptor

En `src/Baxy.Kernel/Operations/ProductCatalog.cs`:

- nombre exacto, estable y ordenado;
- schema cerrado y acotado;
- requeridos explícitos;
- enums preferibles a strings libres cuando el dominio es cerrado;
- límites UTF-8/tamaño;
- `OperationRisks.*` correcto;
- verifier versionado y específico;
- `ToolExposure.Public` o `Internal`;
- descripción orientada a capacidad y evidencia.

No uses la descripción como policy ni como parser.

### 3. Implementar la frontera de plataforma

Para un dominio propio:

- contratos y records cerca del provider;
- interfaz si hay una costura de test o más de una implementación;
- validación defensiva;
- lock/ownership de recurso;
- intent/receipt si el efecto puede interrumpirse;
- postlectura;
- error estable;
- `EffectMayHaveOccurred` cuando corresponda;
- path safety, cuota y atomicidad si persiste.

Para una operación externa, sigue además la receta de adapter de la sección
siguiente.

### 4. Crear el handler

En `src/Baxy.Core/Operations`:

- `Definition = ProductCatalog.CreateDefinition("nombre")`;
- adapta `OperationInvocation` al provider;
- no vuelve a decidir riesgo;
- distingue cancelación solicitada de excepción;
- convierte resultado verificado en `OperationOutcome.Success`;
- conserva fallo y efecto ambiguo sin reintento.

### 5. Registrar la composición

Añade el handler en `Baxy.Core/Program.cs`. Para familias, usa una factory
cerrada como las existentes.

`ProductCatalog.ValidateAgainst(registry)` debe seguir probando igualdad
exacta. No desactives esa validación para avanzar.

### 6. Exponer a Mind

Mind recibe automáticamente las operaciones públicas mediante
`catalog.configure`; no mantengas un segundo catálogo manual.

Solo si la operación necesita reconocimiento/grounding nuevo:

- actualiza reviewers o fuentes semánticas;
- conserva efectos explícitos;
- añade negativos y composiciones;
- regenera artefactos acoplados mediante sus builders.

### 7. Presentar y narrar

- añade narración/proyección si el resultado introduce una forma nueva;
- redacta detalles internos;
- mantiene códigos estables para diagnóstico;
- confirma que UI no muestra JSON;
- no declares éxito sin el verifier.

### 8. Probar

Como mínimo:

- test de descriptor/schema/risk/exposure;
- test de registry exacto;
- tests unitarios del provider;
- fallo antes del efecto;
- éxito con postlectura;
- cancelación;
- replay mismo fingerprint;
- conflicto de idempotencia;
- efecto ambiguo sin fallback;
- handler;
- integración App→Core;
- routing/argumentos ES, EN y spanglish si aplica;
- narración humana;
- test NativeAOT si añade serialización o reflexión potencial.

## Añadir un adapter externo

Los adapters implementan `IExternalOperationAdapter` y se ordenan en
`WindowsExternalCapabilityProvider.CreateDefaultAdapters`.

Checklist:

1. `CanHandle` acepta solo nombres exactos.
2. Toda precondición se comprueba antes del efecto.
3. Argumentos y targets permanecen acotados.
4. Tokens se leen de configuración, nunca se registran.
5. Se evita texto externo como instrucciones.
6. El resultado incluye operación exacta.
7. `Verified=true` solo después de postlectura suficiente.
8. `EffectObserved` se marca al cruzar el efecto.
9. `EffectMayHaveOccurred` se marca si una excepción deja incertidumbre.
10. Cancelación se propaga si aún es segura; no borra incertidumbre.
11. El orden con otros adapters que aceptan la misma operación es deliberado.
12. Nunca se intenta el adapter siguiente tras efecto observado o ambiguo.

Añade también la operación a
`Baxy.Core/Operations/ExternalCapabilityHandlers.Operations`. Su ausencia hace
que el catálogo y registry no coincidan.

Pruebas:

- sin precondición → error específico y ningún efecto;
- éxito → receipt y postlectura;
- excepción read-only → fallo sin efecto;
- excepción mutante → efecto potencial;
- primer adapter no aplicable → siguiente;
- primer adapter ambiguo → no siguiente;
- secreto/PII ausente de logs y outcome.

Una prueba física se separa, se marca `Explicit` o usa un gate dedicado y
declara target/autorización.

## Añadir un provider o store local

1. Ubícalo bajo el dominio de `Baxy.Providers.Windows`.
2. Define quién posee el directorio, lock y lifetime.
3. Rechaza rutas relativas inseguras, UNC/device, ADS y reparse points según la
   frontera.
4. Acota cantidad, bytes, profundidad, nombres y páginas.
5. Escribe a un temporal propio, flush si la garantía lo requiere y reemplaza
   atómicamente.
6. Diseña backup/recovery antes de implementar el happy path.
7. Diferencia checksum de corrupción, MAC de integridad y cifrado.
8. Versiona el documento/envelope.
9. Define migración y qué sucede ante versión futura, truncado o duplicados.
10. Añade tests de power-loss simulado, corrupción, cuota, concurrencia y ruta
    hostil.

No reutilices el store de memoria privada para datos no privados ni un JSON en
claro para payloads que el contrato declara privados.

## Añadir o cambiar lenguaje natural

Primero confirma que la operación exacta ya existe.

### Efectos explícitos

`src/baxy_mind/effect_intent.py` contiene reviewers deterministas por dominio.
Una ampliación debe:

- reconocer semántica, no una frase única;
- conservar orden y cardinalidad de efectos;
- manejar negación y pregunta;
- abstenerse ante ambigüedad;
- no producir operaciones fuera del catálogo;
- incluir ES, EN, spanglish y errores STT relevantes.

### Banco semántico

Fuentes canónicas:

```text
src/baxy_mind/tools/router_bank_sources.py
src/baxy_mind/tools/data/router_cases.jsonl
```

Artefactos acoplados:

```text
src/baxy_mind/data/intent_bank.jsonl
src/baxy_mind/data/intent_bank.embeddings.json
src/baxy_mind/data/intent_bank.embeddings.npy
```

Regenera con el Python aprobado y `PYTHONPATH=src`:

```powershell
$runtimeManifest = Join-Path $env:LOCALAPPDATA `
  'BAXYRuntime\mind-runtime-v1.json'
$runtime = Get-Content -Raw -LiteralPath $runtimeManifest |
  ConvertFrom-Json
$env:PYTHONPATH = (Resolve-Path .\src).Path
& ([string]$runtime.python) -X utf8 `
  -m baxy_mind.tools.build_bank
```

`build_router_pool.py` existe, pero hoy carga `SentenceTransformer` sin fijar
`revision`, sin `local_files_only=True` y no registra la revisión en metadata.
Por tanto, no regeneres ni promociones los embeddings con ese builder hasta
corregir y probar esas tres propiedades contra el snapshot verificado que usa
`router.py`. Revisa juntos filas, metadata, shape, modelo/revisión y hashes. No
edites a mano el `.npy` ni mezcles un banco nuevo con embeddings antiguos.

El banco y `IntentRouter` son exclusivamente una regresión offline. El worker
productivo es encoder-only y `ProcessIntentRouter.route()` falla
deliberadamente: regenerar el banco no entrena ni concede autoridad al routing
vivo, que pertenece a `turn.decide`.

### Evidencia de turnos

Solo puede reforzar conversación o abstenerse. Cambiar su corpus, cache,
sonda, policy o sello requiere el workflow específico de promoción y holdout.
No uses el holdout final para iterar ni publiques texto histórico.

### Lo que no se hace

- regex/substring fast path en WPF como router general;
- inventario manual de verbos como autoridad;
- ejemplo recuperado copiado al prompt como instrucción;
- texto web/OCR convertido en operación;
- fallback de un timeout a una acción más permisiva.

Pruebas habituales:

```text
tests/test_effect_intent.py
tests/test_router.py
tests/test_router_bank_builder.py
tests/test_turn_policy.py
tests/test_planner.py
tests/test_planner_corpus.py
```

## Añadir o modificar un skill de producto

Estos skills son archivos de guía consumidos por `baxy_mind`; no son skills del
agente que desarrolla (las de `.agents/skills/`) ni plugins.

Ruta:

```text
src/baxy_mind/skills/<id>/SKILL.md
```

Frontmatter cerrado:

```yaml
---
name: identificador
description: Descripción breve.
operations:
  - operacion.publica
priority: 50
---
```

Reglas:

- máximo 32 KiB por archivo;
- solo operaciones públicas ya presentes;
- nunca `memory.*`;
- instrucciones advisory/read-only;
- ningún secreto, endpoint personal o ejemplo privado;
- máximo tres skills y 12.000 caracteres seleccionados en un turno;
- el body explica composición y verificación, no añade una tool.

Actualiza `tests/test_skill_registry.py` y casos de selección/ambigüedad.

## Cambiar planner o grounding

Conserva:

- DAG máximo de 16;
- shortlist acotado;
- dependencias solo hacia atrás;
- operaciones requeridas explícitas;
- schema por paso;
- `memory.*` excluido;
- observaciones estructuradas;
- strings ligados a evidencia literal;
- replan limitado;
- pausa ante efecto ambiguo.

Añade pruebas de:

- ciclo;
- dependencia futura/desconocida;
- operación privada;
- required inventado;
- string no grounded;
- número no observado;
- expected operation omitida/sustituida;
- recovery después de un paso;
- presupuesto agotado.

## Cambiar LLM o transporte

Separa tres contratos:

1. lifecycle de `llama-server`;
2. transporte loopback;
3. schema/canonicalización del resultado.

Checklist:

- bind exclusivamente loopback;
- modelo/servidor resueltos desde runtime validado;
- contexto e historial acotados;
- timeout hijo dentro del presupuesto;
- respuesta ligada al request actual;
- JSON Schema cerrado;
- salida inválida → abstención/fallo, nunca ejecución libre;
- un timeout HTTP se descarta o reintenta dentro del presupuesto sin matar el
  servidor por request;
- `llama-server` se reapea al cerrar o si muere durante startup;
- el worker de router, que es otro contrato, sí se retira/reapea ante
  fault/timeout de protocolo;
- ningún prompt contiene secretos o corpus histórico literal.

`llm.py` es un hotspot; extrae módulos solo por ownership coherente y con
pruebas que congelen la frontera. Dividir por longitud sin eliminar
acoplamiento no mejora mantenibilidad.

## Cambiar voz

Identifica la etapa exacta:

| Etapa | Owner |
|---|---|
| KWS/manifest/calibración | `wakeword.py` |
| captura/VAD/STT/estado | `voice.py` |
| AEC/loopback y primitiva `AudioDucker` | `voice_aec.py` |
| TTS SAPI: cola/worker/cancel | `voice_output.py` |
| coordinación de ducking/TTS/captura/cleanup | `voice.py` |
| corrección | `corrector.py`, `phonetic_es.py` |
| control protocol/lifecycle | `__main__.py` |

Toda extensión debe:

- ser opcional/degradable si el asset lo es;
- no cargar ASR continuo como sustituto del KWS;
- conservar Parakeet como final mientras el contrato no cambie;
- mantener un único owner del stream/worker;
- responder a cancel/shutdown;
- retener jobs de cleanup hasta completarlos;
- acotar buffers, hotwords y duración;
- separar evento parcial de transcript final;
- probar ausencia de dispositivo y dependencia.

Validación:

- tests unitarios/runtime;
- `scripts/test_mind_voice.py` para SAPI → STT/VAD/corrector headless; usa
  `IntentRouter` offline como oráculo y no acredita `turn.decide` productivo;
- `scripts/run_voice_system_gate.py` solo cuando el host y la autorización
  permiten micrófono/loopback/salida física; tampoco acredita por sí solo el
  recorrido Core/turn end-to-end;
- calibración de wake con corpus suficiente y reporte promocionable.

No presentes una onda sintética como voz humana ni un transcript como prueba de
audio audible.

## Añadir una superficie de App

Para una vista nativa nueva, usa la costura WPF separada:

1. crea `UserControl` bajo `Baxy.App/Presentation`;
2. si posee recursos, encapsula lifetime en `AppSurfaceSession`;
3. añade un ID lowercase estable en `AppSurfaceIds`;
4. registra una factory lazy en `AppSurfaceCatalog.CreateDefault`;
5. navega mediante `AppSurfaceNavigator`;
6. conserva una sola sesión activa, rollback y disposal;
7. vuelve al mismo Field histórico correlacionado;
8. añade tests en `AppSurfaceNavigatorTests`.

No metas la lógica de la pantalla en `MainWindowViewModel`.

Para cambiar React:

1. reabre ADR-0008 explícitamente;
2. modifica source, bridge y contrato como unidad;
3. versiona `baxy.field.v1` si cambia shape o semántica;
4. bloquea navegación/red/tool proxy;
5. regenera `dist` deliberadamente;
6. actualiza hashes/procedencia/pruebas;
7. valida WebView2 físico, accesibilidad y DPI.

Cambiar solo `dist/` o solo `src/` no es una entrega válida.

## Cambiar un protocolo

Aplica a `baxy.local.v1`, `baxy.mind.v1` o `baxy.field.v1`.

1. Especifica productor, consumidor y compatibilidad.
2. Decide si el cambio es aditivo compatible o requiere nueva versión.
3. Actualiza constants/hello/capability advertisement.
4. Actualiza DTO/schema/contexto JSON en ambos extremos.
5. Rechaza properties/tipos desconocidos según el contrato.
6. Conserva límites de bytes y framing.
7. Añade tests de versión anterior, futura, mensaje truncado, duplicados,
   oversized y orden/correlación.
8. Actualiza README del componente y este manual.
9. Publica ambos extremos juntos; no dejes una implementación oculta que el
   hello no anuncia.

## Cambiar un formato persistido

No edites solo el serializer. Define:

- nombre y versión del schema;
- owner y ruta;
- límite de bytes/entradas/profundidad;
- confidencialidad;
- integridad autenticada o checksum;
- atomicidad y flush;
- backup/anchor;
- migración desde cada versión admitida;
- rechazo de versión futura;
- recovery tras interrupción;
- rollback del producto;
- redacción y exportación;
- tests hostiles.

Para paquete/Setup, recuerda actualizar productor PowerShell, consumidor C#,
manifest, attestation, content-id y ambos conjuntos de tests.

## Cambiar Setup o el paquete

1. Determina si afecta payload, manifest, ZIP, attestation o lifecycle.
2. Actualiza la definición exacta y helpers de canonicalización en
   `scripts/product_build_common.ps1`.
3. Actualiza `scripts/build_product.ps1`, owner del payload y su manifest.
4. Actualiza `scripts/package_product.ps1`, owner del ZIP, sidecar y timestamps.
5. Actualiza validación/embedding en `scripts/build_setup.ps1`.
6. Actualiza `src/Baxy.Setup/PackageContract.cs`,
   `src/Baxy.Setup/ProductPackageVerifier.cs`, modelos y tests consumidores.
7. Conserva paths relativos seguros, no ADS/hardlinks/reparse.
8. Mantén outputs deterministas y `SOURCE_DATE_EPOCH`.
9. Prueba corrupción de cada capa y conjuntos extra/faltantes.
10. Publish payloadless para AOT.
11. Ejecuta pipeline A/B solo sobre HEAD limpio y el entorno declarado.
12. Instala/rollback/uninstall únicamente con autorización y entorno apto.

No confundas hashes/content-id con firma del editor.

## Retirar código muerto

Antes de borrar:

Busca `Símbolo|archivo|operación` con `grep` sobre todo el árbol —aquí sí, porque
un resto puede estar en cualquier sitio— y mira `git log --oneline -- ruta`.

Clasifica el elemento:

- runtime activo;
- test helper;
- builder offline;
- evidencia;
- compatibilidad/migración;
- reflexión/source generation;
- script invocado por otro script;
- histórico deliberado;
- realmente no alcanzable.

Después de retirar:

- elimina pruebas y docs que solo describían la ruta obsoleta;
- conserva una regresión del comportamiento vigente;
- revisa manifests, csproj, JSON contexts y listas cerradas;
- verifica que no rompiste packaging ni assets;
- ejecuta Ruff/analyzers/TypeScript y pruebas propietarias;
- no borres `legacy/`, artefactos o corpus por llamarlos “muertos”: no son
  producto activo, pero tienen política de conservación propia.

Una compuerta estática reduce deuda, pero no demuestra por sí sola cero código
muerto semántico en todos los lenguajes. La prueba final es ownership claro,
referencias justificadas, contratos y cobertura.

## Actualizar documentación

| Tipo de cambio | Documentos |
|---|---|
| baseline/conteos/hallazgo | `REGISTRO_DE_MANTENIBILIDAD.md` |
| decisión de autoridad/tecnología | ADR + `DECISION_VIGENTE.md` |
| proceso/topología/ownership | `MAPA_DEL_SISTEMA.md` + esta guía |
| build/dependencia/entrega | página 02 |
| protocolo/persistencia | página 03 |
| receta de extensión | esta página |
| runtime mind | `src/baxy_mind/README.md` |
| UI histórica | `src/Baxy.FieldUi/README.md`, `ORIGIN.md`, ADR-0008 |
| activo privado/restauración | `AGENT_HANDOFF.md` |

No copies el último conteo de tests a todas las páginas. Enlaza al registro
vigente.
