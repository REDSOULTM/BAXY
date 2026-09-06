# Regresiones anteriores a C03 — comparación histórica

Fecha: 2026-09-05. Encargo: contrastar el recuerdo del dueño de que hace unas
dos semanas BAXY respondía bien en general y hacía lo pedido. No modifica
producto, runtime, perfil ni trabajo de Opus. No inicia otra ejecución de C03.

## Conclusión

**Sí hay una regresión concreta demostrada anterior a C03:** el cambio del
Goal 06 del 23 de agosto retiró una conversión correcta de la hora y perdió
la exigencia de conservar ese dato al aceptar una respuesta. El 1 de septiembre
se añadió otra ruta que podía retirar una respuesta agotada sin final visible.

Esto respalda que determinadas conductas pudieran funcionar mejor antes.
No demuestra que toda la aplicación fuera correcta entonces ni que explique
toda la experiencia recordada. No se conoce la fecha exacta, el perfil, el
binario o los mensajes de aquella prueba del dueño. Hay también defectos
anteriores al periodo investigado.

## Cortes y cambios

| Corte | Commit | Qué representa |
|---|---|---|
| 21 agosto, 18:34 -04 | 4c9804c | Último commit antes del 23; referencia para aproximadamente el 22 de agosto. Goals 01–05. |
| 23 agosto, 11:23 -04 | 046f034 | Goal 06: narradores pasan de preparar frases a emitir hechos JSON. |
| 23 agosto, 14:28 -04 | 44b7c45 | Última tanda de prosa Goal 06 y muestra de cien. |
| 23 agosto, 21:55 -04 | 26d8eab | Final de Goal 09. |
| 31 agosto | 470d4b1, b12f64e, 632a66b | Revalidación, presencia/arranque y reparación de recuperación de memoria. |
| 1 septiembre, 15:03 -04 | 192051f | Goal 10.2.5: recursos, entrada desbloqueada y cola limitada. |
| 2 septiembre, 21:03 -04 | b2505da | Base previa a la auditoría y a la campaña C01–C03. |
| 3 septiembre | auditoría conservada | UI muestra falsedad en hora y contaminación por plan anterior. |
| 4 septiembre | c1ebb79, e7a8ba0 | C03 repara conservación de hechos y limpieza del plan. |

Entre 4c9804c y 26d8eab cambiaron 44 archivos de src/main/manifest
(3761 inserciones, 1806 borrados). Entre 26d8eab y b2505da, 34
(2289 inserciones, 127 borrados). El volumen no atribuye por sí solo una causa.

## 1. Regresión demostrada del contrato de hora — Goal 06

Antes: [ProductOperationNarrator](snapshots/4c9804c/src/Baxy.Core/Operations/ProductOperationNarrator.cs),
líneas 396–424, tomaba utc y localUtcOffsetMinutes, calculaba la hora local y
entregaba una frase al compositor. El modelo YA intervenía en la aplicación:
no era una aplicación completamente determinista que de repente incorporó IA.

El commit 046f034 cambió ese narrador por OperationVisibleFacts.FromOutcome:
los datos seguían como utc/offset, sin convertirlos a la hora local esperada.
En [UserMessagePolicy](snapshots/046f034/src/Baxy.App/UserMessagePolicy.cs),
líneas 433–438 y 608 en adelante, la nueva rama de JSON reemplazó extracción
de literales por steps/reason/title. No exigía conservar la hora de observed.

Se ejecutaron el método original de narración y las políticas C# completas de
4c9804c, 046f034 y 26d8eab, en un proyecto .NET 10 temporal sin efectos.
Sólo se separaron namespaces y se añadieron tipos mínimos para compilar:
no se reimplementó la lógica examinada.

| Prueba sintética: UTC 06:57, offset -240 | Antes, 21 agosto | Primer cambio, 23 agosto |
|---|---|---|
| Hora derivada por el narrador original | 02:57 | El nuevo narrador entrega JSON sin derivarla |
| Literales que la política exige conservar | Fecha y 02:57 | Ninguno para este payload |
| Borrador incorrecto «La hora es 14:30.» | Rechaza: missing_literal_fact | Acepta en la política C# |

Resultado: [dotnet-probe.log](dotnet-probe.log). La aceptación mencionada es
**esa frontera C#**, no una afirmación de publicación E2E ni de que Granite
generara ese texto. Es un contraejemplo real al contrato posterior.

La ejecución de funciones Python históricas confirma que el código del final
del 23 y el del 2 de septiembre enviaban utc/offset sin seen.time. En cambio,
sus datos artificiales localTime=22:10 se convertían en seen.time=22:10.
Resultado: [python-probe.json](python-probe.json).

El recovery que sustituía hechos por un fallo ya existía antes del Goal 06.
En 046f034 cambió la representación de ese fallo a JSON; no corresponde
atribuirle allí la creación de todo el mecanismo. La
[auditoría del 3 de septiembre](../../../documentacion/AUDITORIA_GOALS_01_10_2026-09-03.md)
sí observó Core completed/verified y «No pude: no pude encontrarlo» en pantalla.
No conservó la causa exacta del primer rechazo; no se inventa ahora.

## 2. Por qué los tests no avisaron suficientemente

El [muestreo Goal 06](snapshots/26d8eab/scripts/goal06_voice_sample.py), líneas
167 y 209, fabricaba observed.localTime. Línea 296: llamaba message.compose
directamente con intención y hechos dados. No era una petición del usuario
recorriendo decisión, operación real, datos reales y publicación completa.

La [muestra del 23 de agosto](snapshots/44b7c45/artifacts/development/goal06_cien_respuestas.jsonl)
contiene respuestas coherentes como «Spotify está abierto y reproduciendo»
y «No pude: Spotify no responde». El
[resumen](snapshots/44b7c45/artifacts/development/goal06_prosa_ab.json)
declara n=100, bad=0, p50=0.255 s. Es puntuación de su scorer y latencia de
composición, no éxito de cien tareas reales ni latencia del producto completo.

El [test de catálogo modificado](snapshots/046f034/tests/Baxy.Integration.Tests/CatalogNarrationCoverageTests.cs)
pasó a comprobar JSON no publicable y aceptación de frases preparadas como
«Listo, quedó hecho y verificado». Comprobaba propiedades útiles, pero esa
comprobación no sustituye conservar hechos concretos y generar la respuesta real.

Hay evidencia de prosa correcta en esa época, a la vez que huecos de integración
y validación. No es legítimo concluir que el dueño se lo imaginó.

## 3. Silencio tras agotamiento — Goal 10.2.5

Commit 192051f: el intento de evitar espera indefinida puso
MaximumCompositionAttempts=3 y, al agotarse, RemoveHead + reportFailure +
onSettled; no llamaba publishAsync en esa rama.
[Código histórico](snapshots/b2505da/src/Baxy.App/PendingModelMessageQueue.cs),
líneas 139–159. El callback actualizaba diagnóstico interno y restauraba estado.

Antes la cola reintentaba sin ese límite y podía bloquearse; eso TAMPOCO era
correcto. El cambio mejoraba disponibilidad de entrada pero no garantizaba
una respuesta/error visible al retirar el mensaje. La auditoría anterior a
C03 documenta esa ruta. No se atribuye todo silencio a ella.

El [handoff 10.2.5](../../goal1025/HANDOFF.md) conserva mejoras reales de CPU
y respuesta de entrada. No hay fundamento para revertir esas mejoras enteras.

## 4. Fallos antiguos y estado de sesión

La función histórica de idioma devuelve español para Good afternoon y
define DNS in one sentence ya en 4c9804c, antes del Goal 06; volvió a hacerlo
en 26d8eab y b2505da. Reproducción pura en python-probe.json.
Ese defecto no nació en C03 ni se demuestra como regresión del 23.

El 31 de agosto, 632a66b añadió cancelación a recuperación persistida de memoria.
El 3 de septiembre la auditoría mostró además un plan que interceptaba turnos
y sobrevivía a Nueva sesión; e7a8ba0 lo corrigió en C03. Son mecanismos distintos.
Un perfil limpio puede parecer sano y uno con estado pendiente comportarse mal.
No se establece qué estado tenía la prueba personal de hace dos semanas.

El manifiesto priorizaba Qwen3-4B-Q4_K_M en ambos extremos del periodo.
El registro actual de Granite es posterior. El historial de candidatos no
demuestra qué GGUF resolvió el perfil personal en una ejecución no conservada.

## Autoría y límites

046f034 se identifica con Goal 06 y fecha/hora exactas. Git lo atribuye a
REDUniversitario y otros commits a REDSOULTM, usando la cuenta del repositorio.
Eso no identifica de manera fiable al modelo, agente o sesión que lo escribió.
No se ha inventado una atribución personal ni un ranking de agentes.

No se arrancó una versión antigua en el escritorio, no se cambió main, no se
ejecutaron providers ni se leyó contenido privado de perfiles. Esta revisión
no recrea la experiencia completa del dueño ni certifica el BAXY antiguo.
Se verificó una regresión concreta con código original y se documentaron
otros mecanismos y límites, sin inferir una única causa de todos los fallos.

## Validación y reproducción

[manifest.json](manifest.json): 28 snapshots, commits completos, blobs y hashes.
[analyze.py](analyze.py): exporta historia y prepara el proyecto puro temporal.
[python_probe.py](python_probe.py): ejecuta sólo funciones puras seleccionadas
por AST, sin importar runtime ni cargar modelos.
[verify.py](verify.py): comprueba las salidas guardadas.
[verification.json](verification.json): 9 comprobaciones satisfechas, 0 fallidas.

Comandos desde raíz:
- py artifacts/audit/regresiones_20260822_20260905/analyze.py
- dotnet run --project <project devuelto>/Probe.csproj -c Release --nologo -v:q
- py artifacts/audit/regresiones_20260822_20260905/python_probe.py
- py artifacts/audit/regresiones_20260822_20260905/verify.py

La corrida .NET se hizo en baxy-history-pure-qcx5mojd y produjo exit 0; el script
volvió a generar el mismo código al añadir snapshots de evidencia. verify.py
comprueba los logs conservados; al reproducir guarda la nueva salida .NET en
dotnet-probe.log. No Full: no se cambió código de producto y estas sondas no
constituyen una aceptación C03.

## Consecuencia para continuar

Recuperar garantías perdidas, no restaurar ciegamente 255 frases ni todo el
checkout anterior: la identidad sigue exigiendo prosa formulada por el modelo.
C03 ya reparó parte de la hora y del estado; no repetir esas reparaciones.

Para cada bloqueo actual compara datos reales y candidatos en la primera
frontera donde divergen. Conserva una prueba de contrato con datos reales y
una de recorrido público. Si se sospecha otra regresión y existe un caso
antes/bien después/mal, acota el commit en una copia aislada con mismo
runtime/perfil; no uses la memoria de que «todo funcionaba» como oráculo global.

