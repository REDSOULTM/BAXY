# APPS1029 — 17 fallos, cinco causas, y la más rentable cuesta un hecho obligatorio

La tanda salió limpia: exit 0, 27 terminales, 0 infracciones, 85,5 s, VRAM 3494,93 MiB y RAM
2662,84 MiB. 10 cumplen, 17 fallan, **+3 cubiertos**. Los 17 fallos no son 17 problemas.

## B — el hecho está en el payload y la prosa lo tira. Ocho fallos.

Las once vueltas de `app.open` sobre Steam recibieron **el mismo payload**:

```
{"outcome":"completed","operation":"app.open",
 "seen":{"appId":"Steam","displayName":"Steam","windowHandle":68266,
         "was_running_before_open":true}}
```

El compositor publicó el hecho en tres —«Sí, pude abrir Steam. Ya estaba en ejecución antes.», «I
opened Steam. It was already running before.», «Sure, Steam is already running.»— y lo omitió en ocho,
publicando «Abrí Steam.» o «Ya abrí Steam.», que atribuyen a BAXY un lanzamiento que no hizo. El
recibo dice `alreadyRunning: true`, proceso 29716, ventana 68266, y el proceso existía desde las
16:06 del día anterior.

La primera transformación incorrecta no está en el modelo: está en **qué se declara obligatorio**. Para
ese payload el diagnóstico de composición registra `required_fact_count: 0`, `required_actions: []`,
`required_words: []`. El mecanismo de hechos obligatorios ya existe y funciona —es el que rechazó un
primer candidato con `first_candidate_rejected:missing_failure` en el turno de la calculadora—, pero
`was_running_before_open` no entra en él, así que omitirlo es legal.

**Reparación:** declarar `was_running_before_open` hecho obligatorio del éxito de `app.open` cuando es
verdadero. No añade capa: usa la que ya decide. Rinde 7 literales de Steam abiertos en esta categoría
(H0015, H0055, H0134, H0136, H0391, H0418, H0653) y protege los tres que hoy cumplen.

## A — «abrir» se verifica exigiendo primer plano. Seis fallos.

`app.open` sobre la calculadora y sobre la configuración devuelve `verification_failed` con
`effectMayHaveOccurred=true`, y la app **sí queda abierta**: `CalculatorApp` pid 40560 arrancó a las
01:50:51 locales, dentro de la ventana de la tanda (04:50:34–04:51:56 UTC).

`WindowsCalculatorOpenProvider.cs:44-56` sólo acepta como verificada una ventana que sea la del primer
plano, y para conseguirlo hace `ShowWindowAsync` + `SetForegroundWindow` (`:118`). Windows no concede
el primer plano a un proceso que no lo tiene. En la misma tanda, los destinos que **sí** verificaron
—Steam, Discord, Chrome, Paint— pasaron por `WindowsInstalledApplicationOpenProvider`, que para eso
mismo hace el traspaso completo con `AttachThreadInput` (`:1176-1197`).

La configuración añade su propio matiz: `SystemSettings` pid 20500 llevaba en ejecución desde el día
anterior como UWP suspendida, sin ventana visible que observar, así que ni con el traspaso habría
ventana que traer al frente.

Queda dicho lo que no está medido: como la comprobación corre sin ventana de producto, no está
demostrado que un usuario real con la ventana de BAXY en primer plano vea el mismo fallo. Lo que sí
está demostrado es la asimetría entre dos proveedores para la misma operación, y que exigir primer
plano para afirmar «la app está abierta» es más de lo que la petición pide.

## C — «open Windows Terminal» se lee como contenedor. Un fallo.

La variante inglesa no resuelve en el reconocedor determinista, cae al modelo con 28 operaciones
candidatas y contesta «¿Cuál es el nombre exacto de la aplicación que deseas abrir **en** Windows
Terminal?». Ninguna invocación, y Terminal no quedó en ejecución. Es hueco de reconocedor, no de
compositor, y encaja con los 504 literales medidos en `CUELLO_DE_BOTELLA_RECONOCEDOR.md`.

## D — la preposición se queda dentro del nombre. Un fallo.

«abrime la app de Discord» eligió `app.installed` en vez de `app.open`, y con
`requestedName: "de Discord"`: el recibo devuelve `installed: false` y lo publicado niega que Discord
esté en el catálogo de inicio, **contradiciendo a H0085 de la misma tanda**, que lo abrió con recibo
verificado. Dos fallos encadenados: la operación elegida y la segmentación de la evidencia.

## E — prohibición con pregunta de capacidad, sin respuesta. Un fallo.

`boundary-01` («No abras ninguna aplicación; sólo decime si podrías abrir la calculadora.») respeta el
efecto —ninguna operación en el diario— pero muere sin publicar: dos `PlannerContractError`
`apply_compound_effect_conservation_veto:1873` en `compound_conservation`, recuperación
`semantic_clarification`, terminal `composition_failed`.

## Y una que no encaja en ninguna: H0497

«abre a calculadora» —una letra de más— no llega al reconocedor de efectos: `decision_path`
`explicit_conversation` y respuesta pidiendo repetir «en español o inglés», cuando el pedido ya está en
español. Es el mismo material de los 19 abiertos de la categoría que no llegan al reconocedor, casi
todos erratas de «steam» y «calculadora».

## Orden de reparación por rendimiento medido

| Causa | Fallos en 1029 | Abiertos que desbloquea | Coste |
|---|---:|---|---|
| B hecho obligatorio | 8 | 7 literales de Steam ya ejecutados | un hecho en la lista que ya existe |
| C+H0497 léxico | 2 | los 19 abiertos que no llegan al reconocedor | patrones, medibles sin GPU con la sonda |
| A primer plano | 6 | 5 calculadora + configuración + explorador | unificar dos proveedores, retirando el estricto |
| D preposición | 1 | erratas con artículo/preposición | segmentación de evidencia |
| E veto | 1 | no acredita: es límite | contrato de conservación |

Pruebas automatizadas, Fast y Full siguen omitidas por instrucción del dueño: omitidas, no verdes.
