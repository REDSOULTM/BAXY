# Decisión de arquitectura vigente

Estado: **vigente para el producto activo a 2026-08-01**.

Este documento resume la arquitectura que existe en `src/`. No sustituye los
ADR, no reescribe resultados históricos y no declara terminada la misión de
cimentación. Si una descripción antigua contradice este archivo, debe leerse
como evidencia de su corte y no como mapa del producto actual.

La aplicación operativa de estas decisiones está documentada en
[GUIA_AGENTES_IA/README.md](GUIA_AGENTES_IA/README.md).

## Decisión

BAXY mantiene autoridades separadas:

1. `src/Baxy.App` es el host de escritorio .NET 10 WPF. Sirve el `dist/`
   histórico de BAXY Field dentro de WebView2, controla los procesos hijos y
   presenta conversación, progreso, confirmaciones y voz.
2. `src/baxy_mind` es un sidecar Python local y degradable. Recibe el catálogo
   que App validó contra el proceso Core hijo y el contrato compilado, decide
   entre conversación, aclaración, acción y plan,
   propone argumentos o DAG y opera la entrada/salida de voz. No ejecuta
   providers ni decide riesgo, confirmación o éxito.
3. `src/Baxy.Core` es el proceso .NET 10 NativeAOT que compone el catálogo y
   los handlers. `src/Baxy.Kernel` conserva la autoridad sobre schema, riesgo,
   confirmación, identidad de invocación, journal, replay y estado terminal.
4. `src/Baxy.Providers.Windows` realiza efectos y postlecturas acotadas sobre
   Windows o aplicaciones. Un provider no convierte una solicitud enviada en
   éxito: debe devolver evidencia verificable o un fallo honesto.
5. `src/Baxy.Security.Windows` concentra primitivas Windows de protección
   local. `src/Baxy.Setup` permanece como ejecutable NativeAOT independiente
   para instalación, actualización, rollback y recovery del paquete atestado.

El catálogo público que Core compone y App valida por identidad de proceso y
comparación exacta contiene **169 operaciones tipadas**. Esta validación no es
una firma criptográfica del hello. Texto, corpus, skills, UI y modelos no
pueden agregar una operación ni elevar su autoridad.

## Flujo autorizado

El camino normal es:

```text
texto o voz
  → MissionInput
  → catalog.configure + turn.decide
  → acción tipada o plan DAG ≤ 16
  → validación .NET de catálogo, schema y dependencias
  → política y confirmación ligada a la invocación exacta
  → journal started
  → handler y provider
  → postlectura/verificación
  → completed/failed/rejected terminal o pending reintentable
  → narración natural y, si corresponde, TTS
```

Una acción simple puede omitir la construcción de un plan, pero nunca las
etapas posteriores. En el core, `pending` significa exclusivamente un outcome
reintentable y no terminal. Un efecto externo ambiguo no reintentable se
devuelve como `failed` terminal con `effectMayHaveOccurred:true`; el App aun
así conserva la operación preparada y el checkpoint del plan, y no continúa,
replanea ni repite a ciegas hasta reconciliar el estado. El journal sólo
completa y permite replay de respuestas terminales.

## Runtime de la mente

La instalación descubre el manifest registrado
`%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json`. Ese manifest, o los
overrides explícitos admitidos por cada launcher/gate, son las únicas fuentes
de rutas para Python, `PYTHONPATH`, GGUF, `llama-server`, capas GPU y activos
de voz. No existe descubrimiento heurístico ni fallback desde `legacy/` o
`experiments/`. Los modelos pesados viven fuera del repositorio y del ZIP de
producto.

La selección vigente usa un clasificador atestado de familia para restringir
el catálogo y Qwen3-4B para elegir la operación concreta mediante tool calling
nativo obligatorio. La familia no concede autoridad: `intentOperations`
conserva lo que propuso el modelo para diagnóstico y presentación, mientras
`effectOperations` sigue siendo la única entrada que App puede planificar. Una
selección vetada no ejecuta y la respuesta visible continúa formulada por el
LLM. El registro de mantenibilidad contiene el oráculo, las latencias y la
validación física vigentes.

El desarrollo usa el mismo contrato. `py main.py` recompila sólo el cierre
.NET activo y `scripts/run_baxy.ps1` deja que el manifest sea la fuente de
verdad. `--sin-mente` fija una desactivación explícita que el descubrimiento y
el cliente respetan; no se representa la ausencia del sidecar mediante una
ruta inválida.

## Presentación

ADR-0008 mantiene `src/Baxy.FieldUi` como exportación visual congelada y
`src/Baxy.App/FieldUiBridge.cs` como frontera nativa. El frontend no llama al
core, providers o filesystem por autoridad propia.

El host dispone además de una capa de superficies WPF registrada y perezosa
bajo `src/Baxy.App/Presentation`. Una vista iniciada por el host puede añadirse
sin editar React, `dist` ni `baxy.field.v1`; el navegador mantiene una sola
superficie, conserva vivo el mismo WebView, dispone lifetimes y hace
transiciones correlacionadas bajo exclusión mutua. Una activación iniciada
desde FieldUi sí exige evolucionar deliberadamente el contrato público del
bridge y sus pruebas de seguridad. En ningún caso una vista obtiene autoridad
para ejecutar tools.

## Voz

ADR-0007 mantiene voz y texto convergentes en `MissionInput`. La ruta vigente
usa VAD local, Parakeet para transcripción final, wake acústico sólo con modelo
calibrado, referencia/AEC cuando está disponible, SAPI para TTS, ducking y
barge-in cancelable. Una cancelación o cierre de loop no debe dejar futures,
callbacks ni audio en estado terminal incoherente. La calibración personal
FAR/FRR y barge-in en la sala del usuario sigue fuera de lo certificado.

## Dependencias de autoridad

- UI y mente pueden solicitar; no pueden ejecutar efectos directamente.
- App puede orquestar procesos y UX; no redefine el catálogo.
- Kernel depende de Contracts y no conoce UI, Python ni providers concretos.
- Providers implementa contratos y usa Kernel/Security; no depende de App o
  Core.
- Core es la raíz de composición de ejecución y depende de las capas
  inferiores, nunca de la UI React ni del sidecar Python.
- Setup consume bytes y manifiestos de entrega; no comparte el grafo runtime
  para obtener autoridad.

El detalle del grafo está en
[MAPA_DEL_SISTEMA.md](MAPA_DEL_SISTEMA.md) y las reglas de extensión en
[REGISTRO_DE_MANTENIBILIDAD.md](REGISTRO_DE_MANTENIBILIDAD.md).

## ADR aceptados

| ADR | Decisión vigente |
|---|---|
| [ADR-0001](../../contexto/04_arquitectura/ADR/ADR-0001-arquitectura-base-baxy-1.md) | Host .NET 10 y core .NET 10 NativeAOT en procesos separados |
| [ADR-0002](../../contexto/04_arquitectura/ADR/ADR-0002-estado-gpu-local.md) | GPU local por DXGI y PDH, sin `nvidia-smi` |
| [ADR-0003](../../contexto/04_arquitectura/ADR/ADR-0003-paquete-release-reproducible.md) | Build y paquete reproducibles desde snapshot Git |
| [ADR-0004](../../contexto/04_arquitectura/ADR/ADR-0004-setup-embebido-transaccional.md) | Setup NativeAOT embebido, atestado y transaccional |
| [ADR-0005](../../contexto/04_arquitectura/ADR/ADR-0005-mente-modelos-y-runtime.md) | Sidecar Python, router E5, Qwen3/llama.cpp y STT local |
| [ADR-0006](../../contexto/04_arquitectura/ADR/ADR-0006-planner-hibrido-durable.md) | Planner híbrido, acotado y durable sin autoridad de ejecución |
| [ADR-0007](../../contexto/04_arquitectura/ADR/ADR-0007-voz-local-wake-stt-tts.md) | Voz local, wake verificable y salida cancelable |
| [ADR-0008](../../contexto/04_arquitectura/ADR/ADR-0008-restauracion-field-ui-historica.md) | Restauración literal de BAXY Field dentro del host actual |
| [ADR-0009](../../contexto/04_arquitectura/ADR/ADR-0009-evidencia-corpus-turnos.md) | Evidencia de turnos unilateral: conversación o abstención |

Los scorecards, cortes numerados y mapas anteriores conservan su valor de
procedencia. Sus conteos y frases de “pendiente” describen el momento en que
fueron escritos.

## Límites que permanecen abiertos

Esta decisión no acredita por sí sola:

- instalación inicial, primer inicio y purge en una cuenta o VM desechable;
- firma Authenticode del editor;
- soak de 24 horas;
- accesibilidad física Narrator/NVDA y DPI al 200 % sobre la UI restaurada;
- calibración acústica personal;
- activación de superficies nativas desde el frontend congelado, que requerirá
  una extensión compatible y autorizada de `baxy.field.v1`;
- terminación forzosa e inmediata de un hilo Python bloqueado en CPU o una
  llamada del sistema no interrumpible; el cierre actual es acotado, impide
  publicar estado tardío y mata procesos hijos observables.
