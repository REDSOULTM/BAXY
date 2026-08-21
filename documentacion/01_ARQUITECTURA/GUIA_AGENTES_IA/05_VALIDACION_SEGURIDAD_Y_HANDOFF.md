# Validación, seguridad y handoff

## Qué significa “terminado”

Un cambio está terminado cuando:

- la conducta solicitada existe o el diagnóstico está demostrado;
- el ownership es correcto;
- no se amplió autoridad incidentalmente;
- los fallos son conservadores;
- la prueba adecuada pasó;
- el diff no contiene código, comentarios, flags o assets sin propósito;
- la documentación vigente sigue siendo cierta;
- el estado externo se describe honestamente;
- todo cambio ajeno o preexistente permanece intacto;
- otro agente puede continuar sin reconstruir decisiones.

“Compila” no basta. “Pasó un test focalizado” tampoco demuestra entrega,
hardware, privacidad, idempotencia o compatibilidad.

## Niveles de validación

### Nivel 0: inspección

Para respuesta, auditoría o diagnóstico sin edición:

`git status --short --branch`, `grep` del símbolo acotado a `src tests`, y
`git log --oneline -- ruta`. La shell es PowerShell y no tiene `rg`: buscar y leer
va con las tools del agente.

Reporta evidencia y no implementes una corrección si la tarea solo pidió
diagnosticar.

### Nivel 1: test propietario

Después de una edición local:

- ejecuta el test nuevo o directamente afectado;
- ejecuta la suite del proyecto/módulo dueño;
- ejecuta lint/format del lenguaje tocado;
- inspecciona el diff.

### Nivel 2: compuerta Fast

Para un cambio integrado que toca source:

```powershell
.\scripts\test_source_quality.ps1
```

Cubre estática multilenguaje y build Release.

### Nivel 3: compuerta Full

Para cierre de campaña, contratos compartidos, ejecución, concurrencia,
persistencia, packaging logic o cambios transversales:

```powershell
.\scripts\test_source_quality.ps1 -Mode Full
```

Cubre Fast + todas las suites canónicas no físicas. El baseline vigente y las
omisiones están en
[REGISTRO_DE_MANTENIBILIDAD.md](../REGISTRO_DE_MANTENIBILIDAD.md).

### Nivel 4: publish/gate ambiental

Solo si el riesgo lo exige:

- publish NativeAOT;
- gate de recurso;
- gate de proceso real;
- hardware/voz;
- pipeline de entrega;
- ciclo de instalación.

Cada uno necesita precondiciones adicionales y puede escribir evidencia o
mutar estado. No forma parte implícita de Full.

## Matriz de pruebas por ownership

### .NET

| Cambio | Suite mínima |
|---|---|
| `Baxy.Contracts` | `Baxy.Contracts.Tests` + consumidores si cambia wire |
| `Baxy.Kernel` | `Baxy.Kernel.Tests` |
| `Baxy.Security.Windows` | tests de seguridad en `Baxy.Providers.Windows.Tests` |
| provider/store/adapter | `Baxy.Providers.Windows.Tests` |
| handler/Core | `Baxy.Integration.Tests` |
| App/ViewModel/sidecar/bridge | `Baxy.Integration.Tests` |
| Setup/package consumer | `Baxy.Setup.Tests` + pytest de scripts de package |
| catálogo | Kernel + Core/integración + mind si cambia exposición |
| JSON/source generation | build + tests + publish NativeAOT |

Filtros focalizados:

```powershell
& "$env:USERPROFILE\.dotnet\dotnet.exe" test `
  .\tests\Baxy.Kernel.Tests\Baxy.Kernel.Tests.csproj `
  -c Release --nologo

& "$env:USERPROFILE\.dotnet\dotnet.exe" test `
  .\tests\Baxy.Integration.Tests\Baxy.Integration.Tests.csproj `
  -c Release --nologo `
  --filter 'FullyQualifiedName~NombreDelTest'
```

`InternalsVisibleTo` sigue el ownership:

- Kernel → Kernel.Tests;
- Providers → Providers.Windows.Tests;
- Setup → Setup.Tests;
- App/Core → Integration.Tests.

Security no declara `InternalsVisibleTo`: sus APIs públicas se prueban desde la
suite de Providers. No expongas una API pública solo para facilitar una prueba.

### Python mind

| Frontera | Pruebas principales |
|---|---|
| protocolo/framing | `test_protocol.py` |
| control plane/lifecycle | `test_sidecar_lifecycle.py`, `test_process_lifecycle.py` |
| deadlines | `test_time_budget.py` |
| LLM/transporte | `test_llm_transport.py`, `test_turn_policy.py` |
| router | `test_router.py`, `test_router_bank_builder.py` |
| efectos | `test_effect_intent.py` |
| planner/grounding | `test_planner.py`, `test_planner_corpus.py` |
| skills | `test_skill_registry.py` |
| evidencia | `test_turn_evidence.py`, `test_turn_probe.py`, gates/seals asociados |
| voz | `test_mind_voice_runtime.py`, `test_voice_corrector.py`, `test_wakeword_calibration.py` |
| locks/scripts | `test_python_runtime_lock.py`, `test_python_runtime_scripts.py` |
| build/entrega | `test_build_layout.py`, `test_product_packaging.py`, `test_build_setup.py` |

Ejemplo:

```powershell
$runtime = Get-Content -Raw `
  (Join-Path $env:LOCALAPPDATA 'BAXYRuntime\mind-runtime-v1.json') |
  ConvertFrom-Json
$env:PYTHONPATH = (Resolve-Path .\src).Path
& ([string]$runtime.python) -X utf8 -m pytest `
  -p no:cacheprovider .\tests\test_sidecar_lifecycle.py -q
```

### FieldUi

Validación de source sin regenerar:

```powershell
Push-Location .\src\Baxy.FieldUi
.\node_modules\.bin\eslint.cmd . --max-warnings 0
.\node_modules\.bin\tsc.cmd --noEmit --incremental false `
  --pretty false -p .\tsconfig.app.json
.\node_modules\.bin\tsc.cmd --noEmit --incremental false `
  --pretty false -p .\tsconfig.node.json
Pop-Location
```

El gate Fast ya ejecuta esos pasos. Si se reabre el sello visual, hacen falta
además build deliberado, hashes, bridge, WebView2 físico, accesibilidad y DPI.

### PowerShell y tooling

`test_source_quality.ps1` analiza source PowerShell y detecta una clase de
helpers no usados. Los scripts críticos también tienen pruebas pytest que
importan, parsean o ejecutan sus contratos.

Para cambios en path safety, build o cleanup incluye:

- target dentro de raíz permitida;
- path absoluto resuelto;
- reparse/ADS/hardlink;
- destino existente;
- fallo a mitad;
- cleanup idempotente;
- preservación de un centinela externo.

## Tests físicos y efectos externos

No se ejecutan por rutina:

| Gate/familia | Qué puede tocar |
|---|---|
| `test_app_open.ps1` | procesos/ventanas reales |
| `test_gpu_status.ps1` | build NativeAOT y hardware local read-only |
| `run_voice_system_gate.py` | micrófono, loopback, altavoz y volumen |
| `run_external_adapter_gate.py` | aplicaciones/cuentas externas; deja un DOCX bajo `Documentos\BAXY` y puede conservar estado de apps/browser/media |
| `run_hardware_effect_gate.py` | dispositivos, impresión, red o settings |
| `run_llm_plan_execution_gate.py` | providers reales según misión |
| `run_steam_launch_gate.py` | cliente/biblioteca Steam |
| `test_gate14_clean_environment.ps1` | instalación/desinstalación en entorno limpio |
| `attest_in_place_upgrade.ps1` | lifecycle de instalación real |

Reglas:

1. Lee el script y sus argumentos.
2. Identifica target exacto.
3. Confirma autorización.
4. Captura baseline para restauración.
5. No uses una cuenta, archivo, dispositivo o destinatario ambiguo.
6. No simules un skip como pass.
7. Registra commit, host, precondiciones y resultados.

`run_external_adapter_gate.py` no es completamente autorrestaurable: además
del DOCX deliberado, navegación y estado de aplicaciones o media pueden
persistir. Haz baseline y cleanup explícitos según los targets autorizados.
8. Restaura solo lo que el gate declara y verifica.

Enviar, borrar, imprimir, emparejar, comprar, instalar, cambiar red/cuenta o
purgar datos siempre requiere una autorización explícita para el objetivo real.

## Checklist de seguridad por frontera

### Catálogo y lenguaje

- [ ] La operación existe una sola vez y su exposición es correcta.
- [ ] Mind consume catálogo; no mantiene autoridad paralela.
- [ ] Prompt, skill, corpus y UI no agregan operaciones.
- [ ] Negación, ambigüedad y fuera de alcance se abstienen.
- [ ] Strings/IDs están grounded.
- [ ] Texto externo permanece datos no confiables.

### Efecto

- [ ] Precondiciones antes del efecto.
- [ ] `started` durable antes de mutar.
- [ ] Target exacto.
- [ ] Postlectura suficiente.
- [ ] Receipt/intención cuando hace falta.
- [ ] No hay fallback tras efecto observado/ambiguo.
- [ ] Cancelación no borra `EffectMayHaveOccurred`.
- [ ] El success describe solo lo comprobado.

### Idempotencia y recovery

- [ ] Mission/invocation sobreviven a retry.
- [ ] Fingerprint liga argumentos.
- [ ] Replay terminal es estable.
- [ ] Conflicto de ID falla.
- [ ] `pending` solo para reintento no terminal.
- [ ] Interrupción en cada frontera tiene recovery.
- [ ] No se afirma exactly-once sin evidencia causal.

### Persistencia

- [ ] Ruta/owner/lifetime definidos.
- [ ] Schema y versión explícitos.
- [ ] Límites antes de asignar o escribir.
- [ ] Escritura atómica/flush acordes a la garantía.
- [ ] Corrupción, truncado, rollback y versión futura probados.
- [ ] Checksum no se describe como MAC.
- [ ] Cifrado no se describe como integridad completa de todo el store.
- [ ] Secretos y payload privado no aparecen en logs.
- [ ] Migración y rollback están definidos.

### Procesos y concurrencia

- [ ] Un owner crea, cancela, espera y dispone cada recurso.
- [ ] Queue y backlog tienen capacidad.
- [ ] Deadlines usan monotonic y presupuesto restante.
- [ ] Resultado tardío no se reutiliza.
- [ ] Shutdown es terminal y ordenado.
- [ ] Cleanup secundario no oculta el outcome principal.
- [ ] No se introdujo paralelismo sobre efectos seriales por perfil.

### UI y respuesta

- [ ] La UI no ejecuta providers.
- [ ] Bridge valida origen/shape/método/route.
- [ ] Navegación y red externa siguen bloqueadas.
- [ ] Usuario ve lenguaje natural, no JSON/traza.
- [ ] Error incluye código estable sin filtrar internals.
- [ ] Foco, rollback y disposal de superficie están probados.

### Entrega

- [ ] HEAD limpio y versión explícita.
- [ ] Toolchain y tools externas identificadas.
- [ ] Payload exacto.
- [ ] Manifest, hashes, content-id y ZIP revalidados.
- [ ] A/B exacto en el entorno declarado si se hace ese claim.
- [ ] `NotSigned` no se presenta como autenticidad.
- [ ] Build/package/install se distinguen en el reporte.

## Estándar de mantenibilidad y código vivo

Cada línea nueva debe aportar una de estas funciones:

- contrato;
- comportamiento;
- protección/invariante;
- observabilidad acotada;
- prueba;
- explicación de una decisión no obvia.

Antes del handoff:

- elimina variables, imports, helpers, flags y branches sin consumidor;
- elimina duplicación en la capa dueña, no mediante un helper global ambiguo;
- no agregues abstracciones por una variante hipotética;
- no dejes comentarios que repiten el código;
- explica el “por qué” de carreras, seguridad o compatibilidad;
- no añadas `TODO` sin registrar owner, condición de cierre y razón;
- no suprimas analyzer/lint sin justificación estrecha;
- conserva funciones pequeñas cuando tienen una sola responsabilidad, pero no
  fragmentes un flujo crítico hasta ocultar sus invariantes;
- evita booleanos que mezclen estados; prefiere tipos/estados cerrados;
- mantiene errores estables y contextuales;
- revisa nombres desde la perspectiva del dominio, no de la implementación.

Las compuertas estáticas encuentran imports y helpers no usados, pero no
demuestran por sí solas cero código muerto semántico. Completa la revisión con
call sites, manifests, reflection/source generation, scripts invocados,
migraciones y tests.

## Revisión del diff

```powershell
git diff --check
git diff --stat
git diff --name-status
git diff -- ruta\relevante
git status --short --branch
```

Comprueba:

- solo archivos dentro del scope;
- ningún secreto, corpus privado o binario accidental;
- ningún cambio incidental de EOL/encoding;
- locks/manifests solo si eran parte del cambio;
- `dist/` intacto salvo reapertura explícita;
- artefactos preexistentes no mezclados;
- docs y tests en el mismo cambio cuando corresponden.

Si hay otros agentes en el mismo worktree, vuelve a leer un archivo justo antes
de parchearlo. Asigna ownership de archivos disjunto o usa auditorías
read-only; no sobrescribas una edición concurrente.

## Commits

Un commit debe ser:

- atómico por contrato;
- nombrado por outcome;
- libre de evidencia no relacionada;
- basado en tests ejecutados;
- reversible sin borrar trabajo ajeno.

Ejemplos:

```text
docs: add canonical AI maintainer handbook
fix: preserve ambiguous external effect state
refactor: isolate mind process lifecycle ownership
test: cover durable plan recovery conflict
```

Antes de `git add`, enumera rutas explícitas. No uses `git add -A` en un árbol
con artefactos o cambios de terceros.

## Plantilla de handoff

```text
Objetivo:
- Qué se pidió y qué quedó resuelto.

Cambios:
- Archivo/componente y conducta observable.

Contratos/invariantes:
- Qué se preservó o cambió deliberadamente.

Validación:
- Comando exacto → resultado exacto.
- Publish/gate físico → entorno y evidencia, si se ejecutó.

No ejecutado:
- Gate omitido y razón concreta.

Estado externo:
- Ninguna mutación, o detalle exacto de instalación/dispositivo/cuenta.

Trabajo preexistente preservado:
- Rutas sucias ajenas que no se incluyeron.

Pendiente:
- Solo deuda real con owner/condición, no ideas vagas.

Git:
- Rama y commit local; push/PR solo si fue autorizado.
```

No digas “todo funciona” si solo pasó una parte. Usa:

- “suite X: N pass, M skips ambientales”;
- “publish local completado; no se empaquetó ni instaló”;
- “gate no ejecutado por falta de target físico”;
- “efecto no verificado; no se afirma realizado”.

## Errores comunes de agentes

- empezar de cero o copiar el proyecto;
- usar `legacy/`, `experiments/` o `artifacts/` como runtime;
- tratar una ruta ignorada como prescindible;
- editar el binario instalado;
- duplicar catálogo, models o schemas;
- arreglar lenguaje con frases hardcoded en App;
- conceder autoridad a skills/corpus/E5;
- ejecutar LLM/planner en paralelo sin lifecycle;
- cancelar y soltar un recurso nativo que sigue activo;
- reintentar después de un efecto ambiguo;
- pasar texto web/OCR libre a grounding;
- regenerar `dist` o un sello como efecto secundario;
- actualizar solo un extremo de un protocolo;
- cambiar un formato durable sin migración;
- contar skips como pass;
- afirmar autenticidad porque existen hashes;
- ejecutar un gate sensible sin target/autorización;
- limpiar cambios que no pertenecen a la tarea;
- declarar “cero deuda” sin enlazar pruebas y límites vigentes.

La deuda abierta y las condiciones de cierre viven en
[REGISTRO_DE_MANTENIBILIDAD.md](../REGISTRO_DE_MANTENIBILIDAD.md). No la copies
en otro inventario paralelo.
